import hashlib
import hmac
import aiohttp
import aiofiles
import os
import http.client
import uuid
import asyncio
import sentry_sdk
import backoff
from bs4 import BeautifulSoup
import re
from google.api_core.exceptions import TooManyRequests
from fastapi import Request
import openai
import time
from datetime import datetime
import shutil
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urlparse, parse_qs, quote, quote_plus, unquote
import base64
import json
from dotenv import load_dotenv
import requests
from get_text import get_text
from db import (
    get_user_info, save_query, 
    save_products, save_query_products,
    vision_api_call, scraping_api_call,
    update_user_info, error_handler,
    clean_temp_variables,
    save_temp_products, get_max_batch_number, get_temp_products_batch,
    clean_temp_products, update_max_batch_number, get_query_id,
    get_temp_variables, execute_db_operation, insert_temp_variables,
    get_active_model
)
from pathlib import Path
import google.generativeai as genai
from typing import Tuple, Optional


load_dotenv()

REELS_VIDEOS_PATH = os.getenv("REELS_VIDEOS_PATH", "reels/videos")
REELS_FRAMES_PATH = os.getenv("REELS_FRAMES_PATH", "reels/frames")
REELS_AUDIOS_PATH = os.getenv("REELS_AUDIOS_PATH", "reels/audios")
SAVED_IMAGES_PATH = os.getenv("SAVED_IMAGES_PATH", "saved_images")
KEYFRAME_EXTRACTION_THRESHOLD = int(os.getenv("KEYFRAME_EXTRACTION_THRESHOLD", 20))
SUBPROCESS_TIMEOUT = int(os.getenv("SUBPROCESS_TIMEOUT", 10))

#------------------------------------* GEMINI API COST CONSTANTS *------------------------------------
GEMINI_TOKEN_COST = 0.1 / 1_000_000  # $0.7 per 1 million tokens
GEMINI_FRAME_TOKENS = 260  # tokens per frame
GEMINI_SYSTEM_PROMPT_TOKENS = 260  # system prompt tokens
GEMINI_OUTPUT_TOKENS = 50  # output tokens

#------------------------------------* OPENAI API COST CONSTANTS *------------------------------------
OPENAI_TOKEN_COST = 0.15 / 1_000_000  # $0.00015 per 1 million tokens
OPENAI_FRAME_TOKENS = 100  # tokens per frame
OPENAI_SYSTEM_PROMPT_TOKENS = 260  # system prompt tokens
OPENAI_OUTPUT_TOKENS = 50  # output tokens

#------------------------------------* API VERSION *------------------------------------
API_VERSION = os.getenv("APP_VERSION")

#------------------------------------* CLEAN MEMORY *------------------------------------
async def clean_memory_and_temp_variables(user_id, logger):
    video_path = f"{REELS_VIDEOS_PATH}/{user_id}/"
    audio_path = f"{REELS_AUDIOS_PATH}/{user_id}/"
    frames_path = f"{REELS_FRAMES_PATH}/{user_id}/"
    os.makedirs(video_path, exist_ok=True)
    os.makedirs(audio_path, exist_ok=True)
    os.makedirs(frames_path, exist_ok=True)
    try:
        # Clean temp files
        for file in os.listdir(video_path):
            if file.endswith(".mp4"):
                os.remove(os.path.join(video_path, file))
        for file in os.listdir(frames_path):
            if file.endswith(".jpg") or file.endswith(".png"):
                os.remove(os.path.join(frames_path, file))
        
        # Clean temp variables from database
        await clean_temp_variables(user_id, logger)
        
    except Exception as e:
        await error_handler(
            f"Error cleaning memory and temp variables: {e}",
            "error",
            "high", 
            logger
        )

#------------------------------------* ENCODE IMAGE *------------------------------------
async def encode_image(image_path, logger):
    try:
        async with aiofiles.open(image_path, "rb") as image_file:
            image_data = await image_file.read()
            return base64.b64encode(image_data).decode("utf-8")
    except Exception as e:
        await error_handler(
            f"Error encoding image inside encode_image: {e}",
            "error",
            "high",
            logger
        )

#------------------------------------* EXTRACT KEY FRAMES *------------------------------------
async def extract_keyframes(reel_path: str, user_id: int, logger):
    frames_path = f"{REELS_FRAMES_PATH}/{user_id}/"
    os.makedirs(frames_path, exist_ok=True)
    cmd = [
        "ffmpeg", "-i", reel_path, "-vf", "select='eq(pict_type,PICT_TYPE_I)'",
        "-vsync", "vfr", f"{frames_path}frame_%04d.jpg"
    ]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            return False
        return bool(os.listdir(frames_path))
    except Exception as e:
        await error_handler(
            f"Error extracting keyframes inside extract_keyframes: {e}",
            "error",
            "high",
            logger
        )
        return False

#------------------------------------* IS VALID URL *------------------------------------
async def is_valid_url(url, logger):
    try:
        parsed_url = urlparse(url)
        return parsed_url.scheme in ['http', 'https'] and bool(parsed_url.netloc)
    except Exception as e:
        await error_handler(
            f"Error checking if URL is valid inside is_valid_url: {e}",
            "error",
            "high",
            logger
        )
        return False
    
#------------------------------------* DOWNLOAD VIDEO *------------------------------------
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def download_reel(post_url: str, reel_path: str, logger):
    try:
        #logger.info(f"Starting download_reel with post_url: {post_url}, reel_path: {reel_path}")
        
        # Validate inputs
        if not post_url:
            logger.error("post_url is None or empty")
            return False
            
        if not reel_path:
            logger.error("reel_path is None or empty")
            return False
            
        if os.path.exists(reel_path) and os.path.getsize(reel_path) > 0:
            #logger.info(f"Reel already exists: {reel_path}")
            return True
            
        url_valid = await is_valid_url(post_url, logger)
        #logger.info(f"URL validation result: {url_valid}")
        if not url_valid:
            return False

        try:
            #logger.info(f"Attempting to download from URL: {post_url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(post_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    #logger.info(f"Response status: {resp.status}")
                    if resp.status == 200:
                        os.makedirs(os.path.dirname(reel_path), exist_ok=True)
                        #logger.info(f"Created directory: {os.path.dirname(reel_path)}")
                        async with aiofiles.open(reel_path, 'wb') as f:
                            content = await resp.read()
                            #logger.info(f"Downloaded content size: {len(content)} bytes")
                            await f.write(content)
                            #logger.info(f"Successfully saved reel to: {reel_path}")
                            return True
                    else:
                        logger.error(f"HTTP error: {resp.status}")
                        raise aiohttp.ClientError(f"Status {resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp.ClientError in download_reel: {e}")
            await error_handler(
                f"Error downloading reel inside download_reel: {e}",
                "error",
                "high",
                logger
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error in download_reel: {e}, type: {type(e)}")
            await error_handler(
                f"Unexpected error downloading reel: {e}",
                "error",
                "high",
                logger
            )
            return False
    except Exception as e:
        logger.error(f"Outer exception in download_reel: {e}, type: {type(e)}")
        await error_handler(
            f"Outer exception downloading reel: {e}",
            "error",
            "high",
            logger
        )
        return False
        
#------------------------------------* DOWNLOAD IMAGE *------------------------------------
async def download_image(image_url, user_id, logger):
    if not await is_valid_url(image_url, logger):
        await error_handler(
            f"Invalid URL inside download_image: {image_url}",
            "error",
            "high",
            logger
        )
        return False

    save_path = f"{REELS_FRAMES_PATH}/{user_id}/image_{user_id}.jpg"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    for attempt in range(3):  # Retry up to 3 times
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=20) as response:
                    if response.status == 200:
                        with open(save_path, 'wb') as file:
                            file.write(await response.read())
                        return True
                    else:
                        await error_handler(
                            f"Failed to download image around line 198, status code: {response.status}",
                            "error",
                            "high",
                            logger
                        )
                        return False
        except aiohttp.ClientError as e:
            if attempt < 2:  # If it's not the last attempt
                await error_handler(
                    f"Attempt {attempt+1} failed. Retrying...",
                    "error",
                    "medium",
                    logger
                )
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying
            else:
                await error_handler(
                    f"Error downloading image inside else statement around line 215: {e}",
                    "error",
                    "high",
                    logger
                )
                return False
    return False

#------------------------------------* CONVERT QUERY TO URL *------------------------------------
async def convert_query_to_url(user_query: str, country: str, logger) -> str:
    try:
        base_url = "/scrape/google/serp"
        encoded_query = quote_plus(user_query)
        full_url = ""
        if country == "ca":
            full_url = f"{base_url}?q={encoded_query}&location=Canada&deviceType=desktop&domain=google.ca&num=20&tbm=shop"
        elif country == "us":
            full_url = f"{base_url}?q={encoded_query}&location=United+States&deviceType=desktop&domain=google.com&num=20&tbm=shop"
        return full_url
    except Exception as e:
        await error_handler(
            f"Error converting query to URL inside convert_query_to_url: {e}",
            "error",
            "high",
            logger
        )
        return None

#------------------------------------* EXTRACT URL WITH ZYTE *------------------------------------
async def extract_url_with_zyte(google_product_url, logger):
    """
    Uses Zyte to fetch the HTML of a Google Shopping product link, then parses the HTML
    to extract the real product URL from the <a> tag as shown in the provided image.
    """
    try:
        #logger.info(f"google_product_url: {google_product_url}")
        zyte_api_key = os.getenv("ZYTE_API_KEY")
        if not zyte_api_key:
            await error_handler(
                "ZYTE_API_KEY not found in environment variables",
                "error",
                "high",
                logger
            )
            return None

        try:
            api_response = requests.post(
                "https://api.zyte.com/v1/extract",
                auth=("676e5c1d796b4bfe810372313a817d5f", ""),
                json={
                    "url": google_product_url,
                    "browserHtml": True,
                },
                timeout=20
            )
        except Exception as e:
            await error_handler(
                f"Error making Zyte API request: {e}",
                "error",
                "high",
                logger
            )
            return None

        if api_response.status_code != 200:
            await error_handler(
                f"Zyte API returned status code {api_response.status_code}: {api_response.text}",
                "error",
                "high",
                logger
            )
            return None

        try:
            browser_html: str = api_response.json()["browserHtml"]
        except Exception as e:
            await error_handler(
                f"Error decoding Zyte API response JSON: {e}",
                "error",
                "high",
                logger
            )
            return None

        # Zyte returns the HTML in the "httpResponseBody" field
        if not browser_html:
            await error_handler(
                f"Zyte API did not return httpResponseBody for {google_product_url}",
                "error",
                "medium",
                logger
            )
            return None

        # Parse HTML to find the <a> tag with the product link
        try:
            soup = BeautifulSoup(browser_html, "html.parser")
            # Find the <div> with class "UAVKwf"
            div = soup.find("div", class_="UAVKwf")
            a_tag = None
            if div:
                #logger.info(f"div: {div}")
                # Find the <a> tag inside this div with class containing both "UxuaJe" and "shntl"
                a_tag = div.find("a", class_=lambda c: c and "UxuaJe" in c and "shntl" in c)
            if not a_tag:
                await error_handler(
                    f"Could not find product <a> tag in Zyte HTML for {google_product_url}",
                    "error",
                    "medium",
                    logger
                )
                return None

            href = a_tag.get("href")
            # The href is like "/url?q=https://www.example.com/product&..."
            parsed = urlparse(href)
            if parsed.path == "/url":
                qs = parse_qs(parsed.query)
                real_url = qs.get("q", [None])[0]
                if real_url:
                    return unquote(real_url)
            # Fallback: try to extract after "/url?q="
            if href.startswith("/url?q="):
                real_url = href.split("/url?q=", 1)[1].split("&", 1)[0]
                return unquote(real_url)
            await error_handler(
                f"Could not extract real product URL from href: {href}",
                "error",
                "medium",
                logger
            )
            return None
        except Exception as e:
            await error_handler(
                f"Error parsing product URL from Zyte HTML: {e}",
                "error",
                "high",
                logger
            )
            return None
    except Exception as e:
        await error_handler(
            f"Error extracting URL with Zyte: {e}",
            "error",
            "high",
            logger
        )
        return None


#------------------------------------* SEARCH PRODUCTS WITH HASDATA *------------------------------------
async def google_search_with_hasdata(query, product_brand, country, user_id=None, logger=None):
    try:
        product_list = []
        FIRST_PRODUCTS_COUNT = 5  # Number of products to show immediately
        MAX_BATCHES = 2          # Number of extra batches to store
        BATCH_SIZE = 5           # Size of each batch
        start_time = time.time()

        url = await convert_query_to_url(query, country, logger)
        if url is None:
            return []

        #logger.info(f"URL: {url}")

        conn = http.client.HTTPSConnection("api.hasdata.com")
        headers = {
            'x-api-key': os.getenv("HASDATA_API_KEY"),
            'Content-Type': "application/json"
        }
        conn.request("GET", url, headers=headers)
        res = conn.getresponse()
        data = res.read()
        data = json.loads(data.decode("utf-8"))

        logger.info("data fetched from hasdata")

        all_products = data.get('shoppingResults', [])
        if not isinstance(all_products, list):
            all_products = []

        # Sort shopping results if product_brand is provided
        if product_brand and product_brand != "N/A":
            all_products = sorted(
                all_products,
                key=lambda x: product_brand.lower() in x.get("title", "").lower(),
                reverse=True
            )
        #logger.info(f" length of all_products: {len(all_products)}")
        # Prepare all product infos (up to 20 for safety)
        all_product_infos = []
        for product in all_products[:10]:
            store_name = product.get("source", "N/A").strip()
            if "ebay" in store_name.lower() or "etsy" in store_name.lower():
                logger.info(f"skipping ebay or etsy: {store_name}")
                continue
            
            product_info = {
                "id": str(uuid.uuid4()),  # Generate a unique product ID as a string
                "product_title": product.get("title", "N/A"),
                "product_url": await extract_url_with_zyte(product.get("productLink", "N/A"), logger),
                "store_name": store_name,
                "price": product.get("extractedPrice", 0),
                "rating": float(product.get("rating", 0.0)),
                "review_count": int(float(product.get("reviews", 0))),
                "thumbnail_url": product.get("thumbnail", "N/A")
            }
            if not product_info['product_url'] or product_info['thumbnail_url'] == "N/A":
                logger.info(f"skipping product_url or thumbnail_url is N/A: {product_info['product_url']}")
                continue
            all_product_infos.append(product_info)
            if len(all_product_infos) >= 15:
                break

        # Take first 5 for immediate display
        products_to_show = all_product_infos[:FIRST_PRODUCTS_COUNT]
        #logger.info(f" length of products_to_show: {len(products_to_show)}")
        # Store remaining products in temp_products table for future batches
        remaining_products = all_product_infos[FIRST_PRODUCTS_COUNT:]
        if remaining_products and user_id and logger:
            for i in range(0, min(len(remaining_products), MAX_BATCHES * BATCH_SIZE), BATCH_SIZE):
                batch = remaining_products[i:i+BATCH_SIZE]
                batch_number = (i // BATCH_SIZE) + 1  # Start from batch 1
                if batch_number <= MAX_BATCHES:
                    await save_temp_products(user_id, batch, batch_number, logger)
                    logger.info(f"Saved {len(batch)} products to temp_products table (batch {batch_number})")
        logger.info("now scraping api call")
        response_time = time.time() - start_time
        await scraping_api_call(
                endpoint="hasdata",
                response_time=response_time,
                user_id=user_id,
                success=True,
                updated_at=datetime.now(),
                logger=logger
            )
        return products_to_show
    except Exception as e:
        await error_handler(
            f"Error in google_search_with_hasdata: {str(e)}",
            "error",
            "high",
            logger
        )
        return []

#------------------------------------* FETCH DETAILED DATA *------------------------------------
async def fetch_detailed_data(session, url, logger=None):
    try:
        # Add ScrapingDog API key to the URL
        scrapingdog_api_key = os.getenv("SCRAPINGDOG_API_KEY")
        if not scrapingdog_api_key:
            await error_handler(
                "SCRAPINGDOG_API_KEY not found in environment variables",
                "error",
                "high",
                logger
            )
            return None
            
        # Ensure we're using the ScrapingDog API URL
        if not url.startswith("https://api.scrapingdog.com/"):
            url = f"https://api.scrapingdog.com/google_shopping/product?api_key={scrapingdog_api_key}&url={quote_plus(url)}"
            
        async with session.get(url) as response:
            if response.status == 200:
                try:
                    return await response.json()
                except aiohttp.ContentTypeError as e:
                    await error_handler(
                        f"Failed to parse JSON from response for url: {url}: {str(e)}",
                        "error",
                        "high",
                        logger
                    )
                    return None
            else:
                await error_handler(
                    f"Failed to fetch detailed info of product with url: {url}: status {response.status}",
                    "error",
                    "high",
                    logger
                )
                return None
    except Exception as e:
        await error_handler(
            f"Error fetching detailed data of product with url: {url}: {str(e)}",
            "error",
            "high",
            logger
        )
        return None

#------------------------------------* GOOGLE SHOPPING WITH SCRAPING DOG *------------------------------------
async def google_search_with_scrapingdog(query, product_brand, country, user_id=None, logger=None):
    scrapingdog_api_key = os.getenv("SCRAPINGDOG_API_KEY")
    FIRST_PRODUCTS_COUNT = 5

    if not scrapingdog_api_key:
        await error_handler(
            "SCRAPINGDOG_API_KEY not found in environment variables",
            "error",
            "high",
            logger
        )
        return []

    base_url = "https://api.scrapingdog.com/google_shopping"
    params = {
        "api_key": scrapingdog_api_key,
        "query": query,
        "country": country
    }
    
    
    products_list = []
    start_time = time.time()
    sem = asyncio.Semaphore(5)  # Limit to 5 concurrent detailed requests

    async def fetch_with_semaphore(sem, session, url, logger):
        try:
            async with sem:
                result = await fetch_detailed_data(session, url, logger)
                return result
        except Exception as e:
            return None
    try:
        async with aiohttp.ClientSession() as session:
            # Try up to 3 times to get valid shopping results
            max_retries = 3
            shopping_results = []
            
            for attempt in range(max_retries):
                # Fetch initial shopping results (main request)
                async with session.get(base_url, params=params) as response:
                    if response.status != 200:
                        if logger:
                            response_text = await response.text()
                            sentry_sdk.capture_exception(Exception(f"Error fetching Google Shopping results: {response_text}"))
                        continue
                    #------------------------------------* GET SHOPPING RESULTS *------------------------------------
                    data = await response.json()
                    shopping_results = data.get("shopping_results", [])

                    if not shopping_results and attempt == 0 and response.status == 200:
                        payload = await general_payload_message(user_id, get_text("we_are_working_on_it"), logger)
                        await send_message_to_user(payload, user_id, logger)
                    if shopping_results:  # If we got results, break the retry loop
                        break
                    
                    if attempt < max_retries - 1:  # Don't sleep on the last attempt
                        await asyncio.sleep(1)  # Wait 1 second before retrying
            
            if not shopping_results:
                return []

            
            # Sort shopping results if product_brand is provided
            if product_brand and product_brand != "N/A":
                shopping_results.sort(key=lambda x: product_brand.lower() in x.get("title", "").lower(), reverse=True)
                
            # Only fetch details for FIRST_PRODUCTS_COUNT products initially
            initial_products = shopping_results[:FIRST_PRODUCTS_COUNT]
            
            products_to_fetch = [
                (product, product.get("scrapingdog_product_link", "").replace("us", 'ca'))
                for product in initial_products
                if product.get("scrapingdog_product_link")
            ]
            
            if not products_to_fetch:
                await error_handler(
                    "No products with scrapingdog_product_link found",
                    "error",
                    "high",
                    logger
                )
                return []

            # Prepare and fetch detailed data concurrently for initial products only
            detailed_urls = [url for _, url in products_to_fetch]
            
            tasks = [fetch_with_semaphore(sem, session, url, logger) for url in detailed_urls]
            
            try:
                detailed_datas = await asyncio.gather(*tasks)
            except Exception as e:
                detailed_datas = []

            # Process detailed data to collect valid products for initial display
            
            for i, ((product, url), detailed_data) in enumerate(zip(products_to_fetch, detailed_datas)):
                
                if detailed_data is None:
                    continue
                
                store_name = product.get("source", "N/A").split("&")[0].strip()
                
                # Skip if store is eBay
                if "ebay" in store_name.lower() or "etsy" in store_name.lower():
                    continue
                
                # Safely handle reviews count conversion
                reviews = product.get("reviews", "0")
                try:
                    review_count = int(float(reviews)) if isinstance(reviews, (int, float)) else int(reviews)
                except (ValueError, TypeError):
                    review_count = 0
                
                product_info = {
                    "product_title": product.get("title", "N/A"),
                    "product_url": product.get("product_link", "N/A"),
                    "store_name": store_name,
                    "price": float(product.get("extracted_price", 0.0)),
                    "rating": float(product.get("rating", 0.0)) if product.get("rating") else 0.0,
                    "review_count": review_count,
                    "thumbnail_url": "N/A",
                    "description": "N/A",
                }
                
                # Extract seller information
                sellers = detailed_data.get("online_sellers", [])
                for seller in sellers:
                    if seller.get("name", "").lower().strip() == store_name.lower().strip():
                        product_info["product_url"] = seller.get("link", None)
                        break
                
                # Extract thumbnail and description
                product_results = detailed_data.get("product_results", {})
                media = product_results.get("media", [])
                if media:
                    product_info["thumbnail_url"] = media[0].get("link", "N/A")
                product_info["description"] = product_results.get("descriptions", "N/A")
                
                # Parse the real product URL
                try:
                    parsed = parse_qs(urlparse(product_info["product_url"]).query)
                    product_info["product_url"] = parsed['q'][0]
                except (KeyError, IndexError) as e:
                    continue

                if not product_info.get("product_url") or product_info["thumbnail_url"] == "N/A":
                    continue
                
                products_list.append(product_info)
            
            # Store remaining shopping results in temp_products table for future batches
            remaining_shopping_results = shopping_results[FIRST_PRODUCTS_COUNT:]
            
            if remaining_shopping_results:
                # Process remaining results into proper format
                remaining_products = []
                for product in remaining_shopping_results:
                    if not product.get("scrapingdog_product_link"):
                        continue
                    
                    store_name = product.get("source", "N/A").split("&")[0].strip()
                    if "ebay" in store_name.lower() or "etsy" in store_name.lower():
                        continue
                        
                    reviews = product.get("reviews", "0")
                    try:
                        review_count = int(float(reviews)) if isinstance(reviews, (int, float)) else int(reviews)
                    except (ValueError, TypeError):
                        review_count = 0
                        
                    product_info = {
                        "product_title": product.get("title", "N/A"),
                        "product_url": product.get("scrapingdog_product_link", "N/A"),
                        "store_name": store_name,
                        "price": clean_price(product.get("extracted_price", 0.0)),
                        "rating": float(product.get("rating", 0.0)) if product.get("rating") else 0.0,
                        "review_count": review_count,
                        "thumbnail_url": "N/A",
                        "description": "N/A"
                    }
                    remaining_products.append(product_info)
                
                # Split remaining products into batches
                batch_size = FIRST_PRODUCTS_COUNT
                for i in range(0, len(remaining_products), batch_size):
                    batch = remaining_products[i:i+batch_size]
                    batch_number = (i // batch_size) + 1  # Start from batch 1
                    if batch_number <= 2:  # Only store 2 extra batches
                        await save_temp_products(user_id, batch, batch_number, logger)
                        logger.info(f"Saved {len(batch)} products to temp_products table")
        
        end_time = time.time()
        response_time = int((end_time - start_time) * 1000)
        
        await scraping_api_call(
            endpoint="scrapingdog",
            response_time=response_time,
            user_id=user_id,
            success=True,
            updated_at=datetime.now(),
            logger=logger
        )
        return products_list
                
    except Exception as e:
        end_time = time.time()
        response_time = int((end_time - start_time) * 1000)
        
        await error_handler(
            f"Exception in google_search_with_scrapingdog: {str(e)}",
            "error",
            "high",
            logger
        )
        
        await scraping_api_call(
            endpoint="scrapingdog",
            response_time=response_time,
            user_id=user_id,
            success=False,
            updated_at=datetime.now(),
            logger=logger
        )
        return []
#------------------------------------* CALL OPENAI CHAT COMPLETION *------------------------------------
@backoff.on_exception(backoff.expo, openai.RateLimitError, max_tries=5, max_value=60)
def call_openai_chat_completion(client, model, messages, max_tokens, temperature, logger):
    try:    
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
    except Exception as e:
        logger.error(f"Error in call_openai_chat_completion: {str(e)}")
        return None
    
#------------------------------------* GEMINI GENERATE CONTENT WITH BACKOFF *------------------------------------
@backoff.on_exception(backoff.expo, TooManyRequests, max_tries=5, max_value=60)
def call_gemini_generate_content(client, model, contents, response_schema=None):
    if response_schema:
        generation_config = types.GenerationConfig(response_schema=response_schema)
        return client.models.generate_content(
            model=model,
            contents=contents,
            generation_config=generation_config
        )
    else:
        return client.models.generate_content(
            model=model,
            contents=contents
        )

#------------------------------------* FRAMES TO SEARCH QUERY GEMINI *------------------------------------
async def frames_to_search_query_gemini(user_id, gemini_client, reel_caption, user_request, logger):
    frames_path = f"{REELS_FRAMES_PATH}/{user_id}/"
    os.makedirs(frames_path, exist_ok=True)
    image_files = []
    all_images = os.listdir(frames_path)
    total_frame_count = len(all_images)

    prohibited_products = [
        "weapons",  # e.g., guns, gun parts, ammunition, knives, explosives
        "recreational_drugs",  # including drug paraphernalia
        "tobacco_products",  # e.g., cigarettes, e-cigarettes, vaping devices
        "sodium_nitrite",  # due to potential misuse
        "prescription_medications",  # without preauthorization
        "pornography",  # sexually explicit content
        "adult_services",  # e.g., escort services, adult entertainment products
        "online_gambling_services",  # without preauthorization, varies by region
        "lotteries",  # including betting services
        "counterfeit_goods",  # mimicking trademarks without permission
        "hacking_software",  # tools for illegal activities
        "deceptive_products",  # e.g., fake IDs, counterfeit money
        "hate_speech_content",  # or material promoting violence/discrimination
        "inappropriate_content_for_minors",  # e.g., alcohol ads targeting under-18
        "data_misuse_products"  # products collecting sensitive user info without security
    ]

    if user_request is not None and str(user_request).strip():
        focus_instruction = f"""
        The user wants to focus on a specific product in the images: "{user_request}". 
        Your main task is to identify and generate description details for this product, if it appears in the frames. 
        If you find the product, return only its details in the JSON response. 
        If you cannot find the product, return an empty JSON object: {{}}.
        If you are unsure, do your best to match the user's request to the most relevant product in the images.
        """
    else:
        focus_instruction = ""

    system_instruction = f"""
        You are a product recognition expert for online shopping. You are given one or a set of frames from an Instagram reel that features one or more products for recognition. Your task is to identify the **main product(s)** being advertised and generate detailed description for them for a deep research and analysis, along with their BRAND. The main product is the one that is the focus of the advertisement or is being actively promoted.

        {focus_instruction}

        #### Instructions:

        1.  **Identify the Product Type:**
            - First, determine the type of product in the images by analyzing visual characteristics such as shape, color, size, and any visible text or logos. This is the most important step.

        2.  **Generate Product Details for Each Main Product:**
            - For each distinct main product, follow these steps:
                - **Choose a Specific Product Name:** Select a name for the product that is **at most 3 words** and as specific as possible (e.g., "Wireless Earbuds" instead of "Headphones"). This name will be the key in the JSON output.
                - **Create a Detailed Description:** For the `description` field, include the following details:
                    - Brand (if identifiable)
                    - Product model
                    - Color
                    - Name or function
                    - Key design details (e.g., shape, size, material, style)
                    - **If the Brand is Unknown:** Make the query as specific as possible using the other details (e.g., "Red wireless earbuds with charging case").
                    - **For Clothing:** Include specific details such as color, size (if visible), type (e.g., dress, shirt), sex (if applicable), and style or material (e.g., "Blue cotton summer dress for women"), and texture.
                    - **For Beauty:** Include specific details such as color, size (if visible), type (e.g., mask, cream), sex (if applicable), and style or material (e.g., "Face mask with charcoal and clay"), and texture.
                    - Do not include phrases like "search for" or "search" in the description.
                - **Identify Product Brand:** For the `product_brand` field:
                    - If the brand is clearly identifiable from the images or reel caption (e.g., "Nike", "Samsung"), provide its name.
                    - If the brand cannot be identified, explicitly set the value to `'N/A'`.
                - **Check if Product is Prohibited:** For the `not_allowed` field:
                    - Set to `True` if the product matches any category in the following prohibited products list:
                    {json.dumps(prohibited_products, indent=4)}
                    - Set to `False` if the product is allowed

        3.  **Handle Multiple Frames or Products:**
            - If the same product appears in multiple frames or different views, consolidate its information into **one entry**.
            - If multiple different main products are shown, generate **separate entries** for each.

        4.  **Use the Reel Caption:**
            - Consider the reel caption to gather additional information, such as the brand or product name or some description of the product, even if it is in another language. Translate key terms if necessary.

        5.  **Ignore Accessories or Background Items:** Focus only on the main product. If a product is shown with accessories, only generate details for the main product.

        #### Response Format:
        Return a JSON object where each key is a product name (at most 3 words) and the value is an object containing:
        - description: A detailed description for the product for a deep research and analysis
        - product_brand: The brand name or 'N/A'
        - product_name: The product name (same as the key)
        - product_model: The product model
        - not_allowed: Boolean indicating if the product is prohibited

        Exactly follow this format:
        {{
            "Samsung Galaxy Earbuds": {{
                "description": "Samsung galaxy buds 2 pro white wireless earbuds with charging case",
                "product_brand": "Samsung",
                "product_model": "Galaxy Buds 2 Pro",
                "product_name": "Samsung Galaxy Earbuds",
                "not_allowed": False
            }},
            "Electronic Cigarette": {{
                "description": "Vape pen with nicotine cartridge and LED indicator",
                "product_brand": "N/A",
                "product_model": "N/A",
                "product_name": "Electronic Cigarette",
                "not_allowed": True
            }}
        }}
    """

    start_time = time.time()
    for image_name in all_images:
        image_path = os.path.join(frames_path, image_name)
        with open(image_path, "rb") as f:
            local_file_img_bytes = f.read()
            image_files.append({
                "mime_type": "image/jpeg",
                "data": local_file_img_bytes
            })

    usage_tokens = total_frame_count * GEMINI_FRAME_TOKENS + GEMINI_SYSTEM_PROMPT_TOKENS + GEMINI_OUTPUT_TOKENS
    usage_cost = usage_tokens * GEMINI_TOKEN_COST

    try:
        # Create the content list with proper format
        content_parts = [system_instruction]
        content_parts.extend(image_files)
        content_parts.append(f"Reel Caption: {reel_caption}")
        
        response = gemini_client.generate_content(content_parts)
        end_time = time.time()
        response_time = end_time - start_time

        # Check if request was blocked
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            await error_handler(
                f"Request blocked by Gemini API: {response.prompt_feedback.block_reason}",
                "error",
                "high",
                logger
            )
            return 'blocked'

        try:
            # Parse the response text as JSON
            response_text = response.text.strip()
            
            # Handle markdown code blocks if present
            if response_text.startswith('```'):
                # Extract content between code blocks
                content = response_text.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]  # Remove 'json' prefix
                response_text = content.strip()
            
            # Clean up any potential formatting issues
            response_text = response_text.replace('\n', ' ').replace('\r', '')
            response_text = response_text.replace("```json", "").replace("```", "")
            response_text = response_text.strip()

            #logger.info(f"response_text 1: {response_text}")
            
            # Additional JSON cleaning
            response_text = response_text.replace("'", "'")  # Normalize apostrophes to standard ones
            response_text = response_text.replace('"', '"')  # Replace curly quotes with straight quotes
            response_text = response_text.replace('"', '"')  # Replace curly quotes with straight quotes
            response_text = response_text.replace('"', '"')  # Replace curly quotes with straight quotes
            
            # Only add quotes to keys that don't already have them
            response_text = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', response_text)

            #logger.info(f"response_text 2: {response_text}")
            
            # Fix common JSON formatting issues
            response_text = response_text.replace('True', 'true').replace('False', 'false')  # Fix boolean values
            response_text = re.sub(r',\s*}', '}', response_text)  # Remove trailing commas
            response_text = re.sub(r',\s*]', ']', response_text)  # Remove trailing commas in arrays

            #logger.info(f"response_text 3: {response_text}")
            
            # Parse the cleaned JSON
            parsed_response = json.loads(response_text.strip())
            
            # Validate the response structure
            if not isinstance(parsed_response, dict):
                raise ValueError("Response is not a dictionary")
            
            # Validate each product entry
            for product_name, details in parsed_response.items():
                if not isinstance(details, dict):
                    raise ValueError(f"Product details for {product_name} is not a dictionary")
                required_fields = ["description", "product_brand", "product_name", "product_model", "not_allowed"]
                for field in required_fields:
                    if field not in details:
                        raise ValueError(f"Missing required field {field} for product {product_name}")
                    if field != "not_allowed" and not isinstance(details[field], str):
                        raise ValueError(f"Field {field} for product {product_name} is not a string")
                    if field == "not_allowed" and not isinstance(details[field], bool):
                        raise ValueError(f"Field {field} for product {product_name} is not a boolean")
                    if field == "product_model" and not isinstance(details[field], str):
                        raise ValueError(f"Field {field} for product {product_name} is not a string")

            # Log successful API call
            await vision_api_call(
                endpoint="gemini_vision",
                response_time=response_time,
                user_id=user_id,
                usage_tokens=usage_tokens,
                usage_cost=usage_cost,
                success=True,
                frame_count=len(image_files),
                updated_at=datetime.now(),
                logger=logger
            )

            return parsed_response
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {str(e)}")
        except ValueError as e:
            raise ValueError(f"Invalid response structure: {str(e)}")
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        error_message = str(e)

        await error_handler(
            f"Error in Gemini API call: {error_message}",
            "error",
            "high",
            logger
        )

        await vision_api_call(
            endpoint="gemini_vision",
            response_time=response_time,
            user_id=user_id,
            usage_tokens=usage_tokens,
            usage_cost=usage_cost,
            success=False,
            frame_count=len(image_files),
            updated_at=datetime.now(),
            logger=logger
        )

        return None

#------------------------------------* FRAMES TO SEARCH QUERY OPENAI *------------------------------------
async def frames_to_search_query_openai(user_id, openai_client, reel_caption, user_request, logger):
    frames_path = f"{REELS_FRAMES_PATH}/{user_id}/"
    os.makedirs(frames_path, exist_ok=True)
    

    prohibited_products = [
        "weapons",  # e.g., guns, gun parts, ammunition, knives, explosives
        "recreational_drugs",  # including drug paraphernalia
        "tobacco_products",  # e.g., cigarettes, e-cigarettes, vaping devices
        "sodium_nitrite",  # due to potential misuse
        "pornography",  # sexually explicit content
        "adult_services",  # e.g., escort services, adult entertainment products
        "counterfeit_goods",  # mimicking trademarks without permission
        "hacking_software",  # tools for illegal activities
        "deceptive_products",  # e.g., fake IDs, counterfeit money
        "hate_speech_content",  # or material promoting violence/discrimination
        "inappropriate_content_for_minors",  # e.g., alcohol ads targeting under-18
        "data_misuse_products"  # products collecting sensitive user info without security
    ]

    if user_request is not None and str(user_request).strip():
        focus_instruction = f"""
        The user wants to focus on a specific product in the images: "{user_request}". 
        Your main task is to identify and generate description details for this product, if it appears in the frames. 
        If you find the product, return only its details in the JSON response. 
        If you are unsure, do your best to match the user's request to the most relevant product in the images.
        """
    else:
        focus_instruction = ""

    system_instruction = f"""
        You are a product recognition expert for online shopping. You are given one or a set of frames from an Instagram reel that features one or more products for recognition. Your task is to identify the **main product(s)** being advertised and generate detailed description for them for a deep research and analysis, along with their BRAND. The main product is the one that is the focus of the advertisement or is being actively promoted.

        {focus_instruction}

        #### Instructions:

        1.  **Identify the Product Type:**
            - First, determine the type of product in the images by analyzing visual characteristics such as shape, color, size, and any visible text or logos. This is the most important step.

        2.  **Generate Product Details for Each Main Product:**
            - For each distinct main product, follow these steps:
                - **Choose a Specific Product Name:** Select a name for the product that is **at most 3 words** and as specific as possible (e.g., "Wireless Earbuds" instead of "Headphones"). This name will be the key in the JSON output.
                - **Create a Detailed Description:** For the `description` field, include the following details:
                    - Brand (if identifiable)
                    - Color
                    - Name or function
                    - Key design details (e.g., shape, size, material, style)
                    - **If the Brand is Unknown:** Make the query as specific as possible using the other details (e.g., "Red wireless earbuds with charging case").
                    - **For Clothing:** Include specific details such as color, size (if visible), type (e.g., dress, shirt), sex (if applicable), and style or material (e.g., "Blue cotton summer dress for women"), and texture.
                    - **For Beauty:** Include specific details such as color, size (if visible), type (e.g., mask, cream), sex (if applicable), and style or material (e.g., "Face mask with charcoal and clay"), and texture.
                    - Do not include phrases like "search for" or "search" in the description.
                - **Identify Product Brand:** For the `product_brand` field:
                    - If the brand is clearly identifiable from the images or reel caption (e.g., "Nike", "Samsung"), provide its name.
                    - If the brand cannot be identified, explicitly set the value to `'N/A'`.
                - **Check if Product is Prohibited:** For the `not_allowed` field:
                    - Set to `True` if the product matches any category in the following prohibited products list:
                    {json.dumps(prohibited_products, indent=4)}
                    - Set to `False` if the product is allowed

        3.  **Handle Multiple Frames or Products:**
            - If the same product appears in multiple frames or different views, consolidate its information into **one entry**.
            - If multiple different main products are shown, generate **separate entries** for each.

        4.  **Use the Reel Caption:**
            - Consider the reel caption to gather additional information, such as the brand or product name or some description of the product, even if it is in another language. Translate key terms if necessary.

        5.  **Ignore Accessories or Background Items:** Focus only on the main product. If a product is shown with accessories, only generate details for the main product.

        #### Response Format:
        Return a JSON object where each key is a product name (at most 3 words) and the value is an object containing:
        - description: A detailed description for the product for a deep research and analysis
        - product_brand: The brand name or 'N/A'
        - product_name: The product name (same as the key)
        - product_model: The product model
        - not_allowed: Boolean indicating if the product is prohibited

        Exactly follow this format:
        {{
            "Samsung Galaxy Earbuds": {{
                "description": "Samsung galaxy buds 2 pro white wireless earbuds with charging case",
                "product_brand": "Samsung",
                "product_model": "Galaxy Buds 2 Pro",
                "product_name": "Samsung Galaxy Earbuds",
                "not_allowed": False
            }},
            "Electronic Cigarette": {{
                "description": "Vape pen with nicotine cartridge and LED indicator",
                "product_brand": "N/A",
                "product_model": "N/A",
                "product_name": "Electronic Cigarette",
                "not_allowed": True
            }}
        }}
    """

    start_time = time.time()
    frames_path_list = [os.path.join(frames_path, f) for f in os.listdir(frames_path) if f.endswith('.jpg')]
    total_frame_count = len(frames_path_list)
    usage_tokens = total_frame_count * OPENAI_FRAME_TOKENS + OPENAI_SYSTEM_PROMPT_TOKENS + OPENAI_OUTPUT_TOKENS
    usage_cost = usage_tokens * OPENAI_TOKEN_COST

    content_messages = [
        {"role": "user", "content": f"Reel Caption: {reel_caption}"}
    ]
    try:  
        for frame in frames_path_list:
            encoded_image = await encode_image(frame, logger)
            content_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}",
                        }
                    }
                ]
            })
        
        raw_response = openai_client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": system_instruction},
                *content_messages
            ],
            max_tokens=200,
            temperature=0.0,
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        try:
            query = json.loads(raw_response.choices[0].message.content)
            await vision_api_call(
                endpoint="openai_vision",
                response_time=response_time,
                user_id=user_id,
                usage_tokens=usage_tokens,
                usage_cost=usage_cost,
                success=True,
                frame_count=total_frame_count,
                updated_at=datetime.now(),
                logger=logger
            )
        except Exception as e:
            query = None
            await error_handler(
                f"Error in openai_vision for query generation: {str(e)}",
                "error",
                "high",
                logger
            )
            #------------------------------------* LOG API CALL *------------------------------------
            await vision_api_call(
                endpoint="openai_vision",
                response_time=response_time,
                user_id=user_id,
                usage_tokens=usage_tokens,
                usage_cost=usage_cost,
                success=False,
                frame_count=total_frame_count,
                updated_at=datetime.now(),
                logger=logger
            )
        
        return query
        
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time

        await error_handler(
            f"Error in frames_to_search_query_openai: {str(e)}",
            "error",
            "high",
            logger
        )
        
        return None
#------------------------------------* SAVE FRAMES WITH QUERY ID *------------------------------------
async def save_frames_with_query_id(user_id, query_ids, logger):
    try:
        # Source directory where frames are extracted
        source_frames_path = f"{REELS_FRAMES_PATH}/{user_id}/"
        
        # Destination directory for saved images with query_id
        saved_images_path = f"{SAVED_IMAGES_PATH}/"
        os.makedirs(saved_images_path, exist_ok=True)
        
        # Check if source directory exists and has files
        if not os.path.exists(source_frames_path) or not os.listdir(source_frames_path):
            await error_handler(
                f"No frames found in {source_frames_path} for saving",
                "error",
                "high",
                logger
            )
            return False
        
        # Copy each frame with query_id in the filename
        frame_files = [f for f in os.listdir(source_frames_path) if f.endswith('.jpg')]
        for i, frame_file in enumerate(frame_files):
            source_file = os.path.join(source_frames_path, frame_file)
            # Create new filename with query_id
            query_ids_text = ""
            for query_id in query_ids:
                query_ids_text += f"{query_id}_"
            
            new_filename = f"frame_{query_ids_text}{i+1}.jpg"
            destination_file = os.path.join(saved_images_path, new_filename)
            
            # Copy the file
            shutil.copy2(source_file, destination_file)
        return True
    
    except Exception as e:
        await error_handler(
            f"Error saving frames with query_id: {str(e)}",
            "error",
            "high",
            logger
        )
        return False

#------------------------------------* PROCESS INSTAGRAM POST *------------------------------------#
async def process_instagram_post(attachment_url, reel_caption, user_id, client, attachment_type, user_region, logger):
    #logger.info("now in process_instagram_post")
    try:
        start_time = time.time()
        default_url = f"https://{os.getenv('SERVER_URL')}"
        
        #------------------------------------* DOWNLOAD REEL *------------------------------------
        if attachment_type == "ig_reel" or attachment_type == "share":
            #logger.info("now in ig_reel or share")
            reel_path = f"{REELS_VIDEOS_PATH}/{user_id}/reel_{user_id}.mp4"
            
            reel_download_success = await download_reel(attachment_url, reel_path, logger)

            if not reel_download_success:
                return [], "error_downloading_reel", default_url
            
            
            keyframes_success = await extract_keyframes(reel_path, user_id, logger)
            if not keyframes_success:
                return [], "error_extracting_keyframes", default_url
            
            
            reels_search_count = await get_user_info(user_id, ['reels_search_count'], logger)
            
            # Initialize to 0 if None
            current_count = reels_search_count.get('reels_search_count', 0) or 0
            await update_user_info(user_id, logger, reels_search_count=current_count + 1)

        #------------------------------------* DOWNLOAD IMAGE *------------------------------------
        if attachment_type == "image":
            #logger.info("now in image section")
            image_download_success = await download_image(attachment_url, user_id, logger)

            if not image_download_success:
                return [], 'error_downloading_image', default_url
            
            images_search_count = await get_user_info(user_id, ['images_search_count'], logger)
            current_count = images_search_count.get('images_search_count', 0) or 0
            await update_user_info(user_id, logger, images_search_count=current_count + 1)
            
        #------------------------------------* GENERATE QUERY *------------------------------------
        if client['client_type'] == 'gemini':
            user_request = ""
            generated_response = await frames_to_search_query_gemini(user_id, client['client'], reel_caption, user_request, logger)
        else:
            generated_response = await frames_to_search_query_openai(user_id, client['client'], reel_caption, user_request, logger)
        
        if not generated_response:
            return [], 'no_products_found', default_url
        
        if generated_response == 'blocked':
            return [], 'restricted_product_message_sent', default_url

        # Check if any product in the response is not allowed
        all_not_allowed = all(product_details.get('not_allowed', False) for product_details in generated_response.values())
        if all_not_allowed:
            return [], 'restricted_product_message_sent', default_url
            
        # Filter out not allowed products
        filtered_response = {
            product_name: details 
            for product_name, details in generated_response.items() 
            if not details.get('not_allowed', False)
        }
        generated_response = filtered_response
        #------------------------------------* SAVE QUERY *------------------------------------
        query_ids = []

        if len(generated_response) == 1 and generated_response.values()[0]['product_model'] != 'N/A':
            query_id = await save_query(
                user_id=user_id,
                product_name=list(generated_response.keys())[0],
                generated_query=generated_response.values()[0]['description'],
                product_brand=generated_response.values()[0]['product_brand'],
                product_model=generated_response.values()[0]['product_model'],
                feedback=None,
                logger=logger
            )

        elif len(generated_response) == 1 and generated_response.values()[0]['product_model'] == 'N/A':
            return '', 'ask_user_for_product_model', default_url
        
        else:
            #------------------------------------* SAVE QUERY *------------------------------------
            for product_name, details in generated_response.items():
                query_id = await save_query(
                    user_id=user_id,
                    product_name=product_name,
                    generated_query=details['description'],
                    product_brand=details['product_brand'].lower(),
                    product_model=details['product_model'],
                    feedback=None,
                    logger=logger
                )
                if query_id:
                    query_ids.append(query_id)

            
            if len(query_ids) > 1 and all(qid is not None for qid in query_ids):
                list_product_names = list(generated_response.keys())
                list_product_brands = [details['product_brand'] for details in generated_response.values()]
                list_product_models = [details['product_model'] for details in generated_response.values()]
                return "", 'select_product_postback_message_sent', (list_product_names, query_ids, list_product_brands, list_product_models)
        
        #------------------------------------* DEEP SEARCH *------------------------------------
        if isinstance(generated_response, dict) and generated_response.values():
            #logger.info("now in deep search with scrapingdog")
            search_start = time.time()
            detailed_search_result = await deep_search(list(generated_response.values())[0]['description'], list(generated_response.values())[0]['product_brand'], list(generated_response.values())[0]['product_model'], user_id, logger)
            search_time = time.time() - search_start
            logger.info(f"Product deep search time: {search_time:.2f} seconds")
        
        #------------------------------------* SAVE PRODUCTS *------------------------------------
        if not detailed_search_result:
            return '', 'no_detailed_search_result', default_url
        
        await save_deep_search_result(detailed_search_result, user_id, query_ids[0], logger)
        
        
        #------------------------------------* Save Products *------------------------------------
        
        total_time = time.time() - start_time
        logger.info(f"Total processing time: {total_time:.2f} seconds")
        
        return detailed_search_result, query_ids[0], default_url
    
    except Exception as e:
        logger.error(f"Error processing Instagram post: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Error details: {e}")
        
        # Log the full traceback for debugging
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        await error_handler(
            f"Error processing Instagram post: {str(e)}",
            "error",
            "critical",
            logger
        )
        return '', 'no_detailed_search_result', default_url
    
#------------------------------------* CREATE GENERIC TEMPLATE MESSAGE *------------------------------------
async def create_generic_template_message(user_id, top_products, logger):
    dollar_sign = "$"
    default_url = f"https://{os.getenv('SERVER_URL')}"
    try:
        # Use the new validation function to filter products
        valid_products = filter_valid_products(top_products, logger)
        
        if not valid_products:
            logger.warning("No valid products found after filtering")
            return await general_payload_message(user_id, "Sorry, I couldn't find any valid products to show you. Please try a different image or reel.", logger)

        # Properly encode the default URL
        encoded_default_url = quote(default_url, safe=':/?=&')

        payload = {
            "recipient": {
                "id": user_id
            },
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": []
                    }
                }
            }
        }

        # Process only valid products
        for product in valid_products:
            # All validation is already done by filter_valid_products
            product_url = product.get('product_url')
            thumbnail_url = product.get('thumbnail_url') or product.get('image_url', default_url)
            
            # Properly encode the product URL
            encoded_product_url = quote(product_url, safe=':/?=&')
            
            # Use safe get to avoid KeyError
            price = product.get('price', 'N/A')
            store_name = product.get('store_name', 'N/A')
            
            # Ensure thumbnail URL is valid
            if not is_valid_url_basic(thumbnail_url):
                thumbnail_url = default_url
            
            element = {
                "title": product.get('product_title', 'Product'),
                "image_url": thumbnail_url,
                "subtitle": f"Price: {dollar_sign}{price}\nStore: {store_name}",
                "default_action": {
                    "type": "web_url",
                    "url": encoded_default_url
                },
                "buttons": [
                    {
                        "type": "web_url",
                        "url": encoded_product_url,
                        "title": "View Product Details"
                    }
                ]
            }
            
            # Validate element before adding
            if validate_template_data(element, logger):
                payload['message']['attachment']['payload']['elements'].append(element)
            else:
                logger.warning(f"Skipping invalid element for product: {product.get('product_title', 'Unknown')}")
        
        # If no valid elements were added, return a general message
        if not payload['message']['attachment']['payload']['elements']:
            return await general_payload_message(user_id, "Sorry, I couldn't find any valid products to show you.", logger)

        # Log the payload for debugging
        #logger.info(f"[MESSENGER] Payload being sent: {json.dumps(payload, indent=2)}")
        
        return payload
    except Exception as e:
        await error_handler(
            f"Error creating generic template message: {str(e)}",
            "error",
            "high",
            logger
        )
        # Return a fallback general message
        return await general_payload_message(user_id, "Sorry, there was an error creating your product list. Please try again.", logger)

#------------------------------------* SEND SELECT PRODUCT POSTBACK MESSAGE *------------------------------------
async def send_select_product_postback_message(user_id, product_names, query_ids, product_brands, product_models, logger):
    url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
    headers = {
        'Content-Type': 'application/json'
    }

    #print(f"product brands: {product_brands}")

    # Ensure all lists have the same length
    min_length = min(len(product_names), len(query_ids), len(product_brands))
    product_names = product_names[:min_length]
    query_ids = query_ids[:min_length]
    product_brands = product_brands[:min_length]
    product_models = product_models[:min_length]
    # Chunk the lists into groups of 3 (max buttons per template)
    chunked_product_names = [product_names[i:i+3] for i in range(0, len(product_names), 3)]
    chunked_query_ids = [query_ids[i:i+3] for i in range(0, len(query_ids), 3)]
    chunked_product_brands = [product_brands[i:i+3] for i in range(0, len(product_brands), 3)]
    chunked_product_models = [product_models[i:i+3] for i in range(0, len(product_models), 3)]
    # Create elements for each chunk
    elements = []
    for i, (names_chunk, ids_chunk, brands_chunk, models_chunk) in enumerate(zip(chunked_product_names, chunked_query_ids, chunked_product_brands, chunked_product_models)):
        buttons = []
        for name, query_id, brand, model in zip(names_chunk, ids_chunk, brands_chunk, models_chunk):
            # Clean and format the title/payload
            title = name.strip().capitalize()
            payload = f"SELECT_PRODUCT_{query_id}_{name.replace(' ', '_')}_{brand.replace(' ', '_')}_{model.replace(' ', '_')}"
            
            buttons.append({
                "type": "postback",
                "title": title,
                "payload": payload
            })

        elements.append({
            "title": "Select Your Product",
            "buttons": buttons
        })

    payload = {
        "recipient": {
            "id": user_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements
                }
            }
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    await error_handler(
                        f"Error sending message: {response.status}",
                        "error", 
                        "high",
                        logger
                    )
                    return False
                return True
                
    except Exception as e:
        await error_handler(
            f"Error sending message: {str(e)}",
            "error",
            "high", 
            logger
        )
        return False
    
#------------------------------------* SEND REGION POSTBACK MESSAGE *------------------------------------
async def send_region_postback_message(user_id, logger):
    url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "recipient": {
            "id": user_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "Select Your Region",
                            "subtitle": "Choose your region to proceed.",
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "US 🇺🇸",
                                    "payload": "US_REGION_POSTBACK"
                                },
                                {
                                    "type": "postback",
                                    "title": "CA 🇨🇦",
                                    "payload": "CA_REGION_POSTBACK"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        await error_handler(
            f"Error sending message: {str(e)}",
            "error",
            "high",
            logger
        )
        return False


#------------------------------------* SEND FOLLOW POSTBACK MESSAGE *------------------------------------
async def send_follow_postback_message(user_id, logger):
    url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Get the page name from environment variable or use a default
    page_name = os.getenv('PAGE_NAME', '@zeebra.ai')
    
    payload = {
        "recipient": {
            "id": user_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": f"Please follow {page_name}",
                            "subtitle": "Confirm follow to unlock magic features.",
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Confirm Follow",
                                    "payload": "CONFIRM_FOLLOW_POSTBACK"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    response_text = await response.text()
                    await error_handler(
                        f"Failed to send follow message. Status: {response.status}, Response: {response_text}",
                        "error",
                        "high",
                        logger
                    )
                    return False
                return True
    except Exception as e:
        await error_handler(
            f"Error sending follow message: {str(e)}",
            "error",
            "high",
            logger
        )
        return False

#------------------------------------* GENERAL PAYLOAD MESSAGE *------------------------------------
async def general_payload_message(user_id, message, logger):
    try:
        # Make sure we have a valid message
        if not message or not isinstance(message, str):
            logger.warning(f"Invalid message in general_payload_message: {message}")
            message = "Sorry, I couldn't process your request."
        
        # Ensure user_id is valid
        if not user_id:
            logger.error("Missing user_id in general_payload_message")
            return None
        
        payload = {
            "recipient": {
                "id": user_id
            },
            "message": {
                "text": message
            }
        }
        return payload
    except Exception as e:
        logger.error(f"Error creating general payload message: {str(e)}")
        # Create a very basic payload as fallback
        return {
            "recipient": {"id": user_id},
            "message": {"text": "Sorry, I encountered an error."}
        }

                       
#------------------------------------* SEND FEEDBACK POSTBACK MESSAGE *------------------------------------
async def send_feedback_postback_message(user_id, query_id, logger):
    try:
        # First send the feedback message
        url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
        headers = {
            'Content-Type': 'application/json'
        }
        payload = {
            "recipient": {
                "id": user_id
            },
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": [
                            {
                                "title": "How was your experience with these products? 🤔",
                                "buttons": [
                                    {
                                        "type": "postback",
                                        "title": "👍 Good",
                                        "payload": f"FEEDBACK_GOOD_{query_id}"
                                    },
                                    {
                                        "type": "postback",
                                        "title": "👎 Bad",
                                        "payload": f"FEEDBACK_BAD_{query_id}"
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()    
        
        return True
    except Exception as e:
        await error_handler(
            f"Error sending feedback postback message: {str(e)}",
            "error",
            "medium",
            logger
        )
        return False

#------------------------------------* SEND MORE PRODUCTS POSTBACK MESSAGE *------------------------------------
async def send_more_products_postback_message(user_id, query_id, logger):
    try:
        # Check if there are more products available
        max_batch = await get_max_batch_number(user_id, logger)
        logger.info(f"max_batch: {max_batch}")
        if max_batch > 0:
            url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Different message content based on feedback type
            title = "Would you like to see more options? 🛍️"
            show_more_title = "✨ Show More"
            
            payload = {
                "recipient": {
                    "id": user_id
                },
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": [
                                {
                                    "title": title,
                                    "buttons": [
                                        {
                                            "type": "postback",
                                            "title": "✨ Show More",
                                            "payload": f"SHOW_MORE_PRODUCTS_{query_id}"
                                        },
                                        {
                                            "type": "postback",
                                            "title": "❌ No Thanks",
                                            "payload": "NO_MORE_PRODUCTS"
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            return True
        return False
    except Exception as e:
        if logger:
            await error_handler(
                f"Error sending more products postback message: {str(e)}",
                "error",
                "medium",
                logger
            )
        return False

#------------------------------------* HANDLE MORE PRODUCTS REQUEST *------------------------------------
async def handle_more_products_request(user_id, query_id, logger):
    try:
        # Get the next batch number
        current_batch = await get_max_batch_number(user_id, logger)
        logger.info(f"current_batch: {current_batch}")
        if current_batch <= 0:
            no_more_products_text = get_text('no_more_products')
            await send_message_to_user(no_more_products_text, user_id, logger)
            return False
            
        # Get products from the next batch
        products = await get_temp_products_batch(user_id, 1, logger)
        if not products:
            no_more_products_text = get_text('no_more_products')
            await send_message_to_user(no_more_products_text, user_id, logger)
            await clean_temp_products(user_id, logger)
            return False
        
        # Fetch detailed data for products in the batch
        sem = asyncio.Semaphore(5)  # Limit to 5 concurrent detailed requests
        
        async def fetch_with_semaphore(sem, session, url, logger):
            try:
                async with sem:
                    return await fetch_detailed_data(session, url, logger)
            except Exception as e:
                return None
        
        detailed_products = []
        async with aiohttp.ClientSession() as session:
            # Prepare URLs for detailed fetching
            products_to_fetch = [
                (product, product.get("product_url", "").replace("us", 'ca'))
                for product in products
                if product.get("product_url")
            ]
            
            if not products_to_fetch:
                await error_handler(
                    "No products with product_url found",
                    "error",
                    "high",
                    logger
                )
                return []
            
            detailed_urls = [url for _, url in products_to_fetch]
            tasks = [fetch_with_semaphore(sem, session, url, logger) for url in detailed_urls]
            try:
                detailed_datas = await asyncio.gather(*tasks)
            except Exception as e:
                detailed_datas = []
            
            # Process detailed data to enhance product information
            for (product, url), detailed_data in zip(products_to_fetch, detailed_datas):
                if detailed_data is None:
                    continue

                product_info = {
                    "product_title": product.get("product_title", "N/A"),
                    "product_url": product.get("product_url", "N/A"),
                    "store_name": product.get("store_name", "N/A"),
                    "price": float(product.get("price", 0.0)),
                    "rating": float(product.get("rating", 0.0)) if product.get("rating") else 0.0,
                    "review_count": product.get("review_count", 0),
                    "thumbnail_url": "N/A",
                    "description": "N/A",
                }
                
                # Extract seller information
                sellers = detailed_data.get("online_sellers", [])
                for seller in sellers:
                    if seller.get("name", "").lower().strip() == product_info.get("store_name", "N/A").lower().strip():
                        product_info["product_url"] = seller.get("link", None)
                        break
                if not product_info.get("product_url"):
                    continue
                
                # Extract thumbnail and description
                product_results = detailed_data.get("product_results", {})
                media = product_results.get("media", [])
                if media:
                    product_info["thumbnail_url"] = media[0].get("link", "N/A")
                product_info["description"] = product_results.get("descriptions", "N/A")
                
                # Parse the real product URL if it's a Google Shopping URL
                try:
                    parsed = parse_qs(urlparse(product_info["product_url"]).query)
                    product_info["product_url"] = parsed['q'][0]
                except (KeyError, IndexError):
                    logger.warning(f"Error parsing product_url: {product_info['product_url']}")
                    pass
                
                detailed_products.append(product_info)
            
         # Send enhanced products to user
        logger.info(f"len(detailed_products): {len(detailed_products)}")
        
        # Log product details for debugging
        #for i, product in enumerate(detailed_products):
        #    logger.info(f"Product {i}: title={product.get('product_title')}, url={product.get('product_url')}, thumbnail={product.get('thumbnail_url')}")
        
        response = await send_message_to_user(detailed_products, user_id, logger)
        if response:
            # Send feedback postback message after sending products
            await send_feedback_postback_message(user_id, query_id, logger)
         
        # Remove only the sent batch (batch 1) and shift remaining batches down
        try:
            # Remove batch 1 (the sent batch)
            async def remove_sent_batch(conn):
                query = "DELETE FROM temp_products WHERE user_id = $1 AND batch_number = 1"
                await conn.execute(query, user_id)
            await execute_db_operation(remove_sent_batch)
        except Exception as e:
            logger.warning(f"Failed to remove sent batch: {e}")

        # Shift remaining batches down by 1 (batch 2 -> 1, batch 3 -> 2, etc.)
        try:
            async def shift_batches(conn):
                query = """
                    UPDATE temp_products
                    SET batch_number = batch_number - 1
                    WHERE user_id = $1 AND batch_number > 1
                """
                await conn.execute(query, user_id)
            await execute_db_operation(shift_batches)
        except Exception as e:
            logger.warning(f"Failed to shift batches: {e}")
        
        # Update max batch number AFTER shifting (should be current_batch - 1)
        new_max_batch = current_batch - 1
        await update_max_batch_number(user_id, new_max_batch, logger)
        logger.info(f"Updated max batch from {current_batch} to {new_max_batch}")
         
        return True
    except Exception as e:
        await error_handler(
            f"Error handling more products request: {str(e)}",
            "error",
            "medium",
            logger
        )
        return False
        
#------------------------------------* SEND MESSAGE TO USER *------------------------------------
async def send_message_to_user(input_for_payload, user_id, logger):
    try:
        # Handle case where input is a string message identifier
        if isinstance(input_for_payload, str):
            payload = await general_payload_message(user_id, input_for_payload, logger)
        # Handle case where input is a list of products
        elif isinstance(input_for_payload, list):
            #logger.info(f"input type is list")
            payload = await create_safe_message(input_for_payload, user_id, logger)
        # Handle case where input is already a payload
        elif isinstance(input_for_payload, dict) and "recipient" in input_for_payload:
            payload = input_for_payload
        # Handle unexpected input types
        else:
            logger.error(f"Unexpected input_for_payload type: {type(input_for_payload)}")
            payload = await general_payload_message(user_id, "Sorry, I encountered an error processing your request.", logger)
        
        # Check if payload creation failed
        if not payload:
            logger.error("Failed to create payload")
            return False

        # Log the final payload being sent to Facebook
        #logger.info(f"[MESSENGER] Final payload: {json.dumps(payload, indent=2)}")

        url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
        headers = {
            "Content-Type": "application/json",
        }
        
        # Ensure user_id is a string
        if isinstance(user_id, (int, float)):
            user_id = str(int(user_id))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Facebook API Error: Status: {response.status}, Response: {response_text}")
                    
                    # If it's a 400 error (Invalid message data), try fallback
                    if response.status == 400 and "Invalid message data" in response_text:
                        logger.warning("Attempting fallback message due to invalid message data")
                        fallback_payload = await general_payload_message(user_id, "Oops! I encountered an error.\n\nSorry for the inconvenience. Please try again later.", logger)
                        async with session.post(url, json=fallback_payload, headers=headers) as fallback_response:
                            if fallback_response.status == 200:
                                logger.info("Fallback message sent successfully")
                                return False
                            else:
                                logger.error(f"Fallback message also failed: {fallback_response.status}")
                                return False
                    
                    await error_handler(
                        f"Failed to send message. Status: {response.status}, Response: {response_text}",
                        "error",
                        "high",
                        logger
                    )
                    return False
                return True
    except Exception as e:
        await error_handler(
            f"Error sending message to user: {str(e)}",
            "error",
            "high",
            logger
        )
        return False
    
#------------------------------------* CHECK IF USER IS FOLLOWING *------------------------------------
# Asynchronous function to check if user is following
async def is_following(user_id, logger):
    if not user_id:
        await error_handler(
            "Invalid user_id in is_following check",
            "error",
            "high",
            logger
        )
        return False

    graph_api_url = f"https://graph.facebook.com/{API_VERSION}/{user_id}"
    access_token = os.getenv("PAGE_ACCESS_TOKEN")
    
    if not access_token:
        await error_handler(
            
            "Missing PAGE_ACCESS_TOKEN",
            "error",
            "high",
            logger
        )
        return False

    params = {
        "fields": "is_user_follow_business",
        "access_token": access_token
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(graph_api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("is_user_follow_business", False)
                else:
                    await error_handler(
                        f"Follow check failed: {response.status}",
                        "error",
                        "high",
                        logger
                    )
                    return False
    except Exception as e:
        await error_handler(
            f"Error checking follow status: {str(e)}",
            "error",
            "high",
            logger
        )
        return False

#------------------------------------* VERIFY WEBHOOK CALL *------------------------------------
async def verify_webhook_call(request: Request, logger):
    try:
        # Step 1: Get the raw request body for signature verification
        raw_body = await request.body()
        
        # Step 2: Check if this is a Facebook webhook by looking for specific headers/parameters
        signature_header = request.headers.get('X-Hub-Signature')
        if not signature_header:
            await error_handler(
                "Missing X-Hub-Signature header (required for Facebook webhooks)",
                "error",
                "high",
                logger
            )
            return False
        
        if not signature_header.startswith('sha1='):
            await error_handler(
                "Invalid X-Hub-Signature format",
                "error",
                "high",
                logger
            )
            return False
        
        signature = signature_header.split('=')[1]
        
        # Step 3: Get the Facebook app secret from environment variables
        app_secret = os.getenv('APP_SECRET')

        if not app_secret:
            await error_handler(
                "Facebook app secret not configured",
                "error",
                "high",
                logger
            )
            return False
        
        # Step 4: Compute the expected signature using Facebook's method
        expected_signature = hmac.new(
            app_secret.encode('utf-8'),  # Encode secret as bytes
            raw_body,                    # Raw body as bytes
            hashlib.sha1                 # SHA-1 as per Facebook's spec
        ).hexdigest()
        
        # Step 5: Compare signatures securely
        if not hmac.compare_digest(expected_signature, signature):
            await error_handler(
                "Invalid Facebook signature",
                "error",
                "high",
                logger
            )
            return False
        
        # Step 6: Parse the body after verification
        try:
            body = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            await error_handler(
                f"Invalid request body: {e}",
                "error",
                "high",
                logger
            )
            return False
        
        # Step 7: Verify this is specifically a Facebook/Instagram webhook
        # Check for Facebook's specific payload structure
        if not body.get('object') in ['page', 'instagram']:
            await error_handler(
                f"Not a valid Facebook webhook: unknown object type '{body.get('object')}'",
                "error",
                "medium",
                logger
            )
            return False
            
        # Step 8: Verify webhook has proper entry structure
        if not body.get('entry') or not isinstance(body.get('entry'), list):
            await error_handler(
                "Invalid Facebook webhook format: missing or invalid 'entry' field",
                "error",
                "medium",
                logger
            )
            return False
        
        #logger.info(f"Successfully verified Facebook webhook call: {body.get('object')}")
        return body
    except Exception as e:
        await error_handler(
            f"Error verifying Facebook webhook call: {e}",
            "error",
            "high",
            logger
        )
        return False

#------------------------------------* SEARCH AND SAVE PRODUCTS *------------------------------------
async def search_and_save_products(user_id, product_name, product_brand, generated_query, query_id, logger):
    try:
        user_region = 'ca'
        
        # Search for products
        top_products = await google_search_with_hasdata(generated_query, product_brand, user_region, user_id, logger)
        if not top_products:
            return None
        
        # Save products list
        products_list_id = await save_products(top_products, logger)
        if not products_list_id:
            return None
        
        # Save query products
        await save_query_products(products_list_id, user_id, query_id, logger)
        
        return top_products
    except Exception as e:
        await error_handler(
            f"Error in search_and_save_products: {e}",
            "error",
            "high",
            logger
        )
        return None

#------------------------------------* RENDER PRODUCTS TEMPLATE *------------------------------------
async def render_products_template(user_id, products, logger):
    try:
        # Read the template file
        template_path = Path(__file__).parent / "products_template.html"
        with open(template_path, "r") as f:
            template_content = f.read()

        # Format products for the template
        formatted_products = []
        for product in products:
            formatted_product = {
                "id": str(product.get("product_id", "")),
                "title": product.get("product_title", "N/A"),
                "store": product.get("store_name", "N/A"),
                "brand": product.get("product_brand", "N/A"),  # Use product_brand if available
                "price": float(product.get("price", 0)),
                "image": product.get("thumbnail_url", "N/A"),
                "product_url": product.get("product_url", "N/A")
            }
            formatted_products.append(formatted_product)

        # Replace placeholders in the template
        products_js = f"const products = {json.dumps(formatted_products)};"
        rendered_template = template_content.replace("{products_js}", products_js)
        rendered_template = rendered_template.replace("{user_id}", str(user_id))
        rendered_template = rendered_template.replace("{len(additional_products)}", str(len(formatted_products)))

        return rendered_template

    except Exception as e:
        await error_handler(
            f"Error rendering products template: {str(e)}",
            "error",
            "high",
            logger
        )
        return None

#------------------------------------* CLEAN PRICE *------------------------------------
def clean_price(price_str):
    """Clean price string by removing currency symbols and converting to float."""
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if not isinstance(price_str, str):
        return 0.0
    # Remove currency symbols and other non-numeric characters except decimal point
    cleaned = ''.join(c for c in price_str if c.isdigit() or c == '.')
    try:
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0

#------------------------------------* GEMINI MESSAGE PROCESSOR *------------------------------------

async def process_message_with_gemini(
    user_id: str, 
    user_message: str, 
    gemini_client,
    previous_query,
    logger
) -> Tuple[str, Optional[str], str]:
    """
    Process user message using Gemini model to determine message type and generate appropriate response.
    
    Args:
        user_id: The user's ID
        message: The user's message
        gemini_client: The Gemini client instance from zeebra_main
        logger: Logger instance
        initial_query: The initial search query that led to current results (optional)
    
    Returns:
        Tuple[str, Optional[str], str]: (message_type, response, product_name)
        - message_type can be: 'general' | 'search_refinement' | 'needs_details' | 'new_search'
        - response: 
            * general: Answer for general message
            * search_refinement: Enhanced search query
            * needs_details: Question asking for more details
            * new_search: Specific query for reanalyzing frames
        - product_name: Product name for search_refinement (defaults to "N/A" for other types)
    """
    try:


        # Create chat history for Gemini (map roles correctly: assistant -> model, user -> user)
        gemini_history = []

        
        chat = gemini_client.start_chat(history=gemini_history)
        
        # Add conversation history dict to the prompt for Gemini
        response = chat.send_message(f"""
        Analyze the user's message and previous query to determine the appropriate response.

        Here is the user's message:
        {user_message}

        Here is the previous query:
        {previous_query}

        Respond ONLY in the following JSON format (do not include any extra text, markdown, or explanation):

        {{
            "message_type": "general" | "search_refinement" | "needs_details" | "new_search" | "show_more_products",
            "response": "answer user's general message" | "enhanced search query" | "message asking for details" | "specific query for reanalysis" | "message asking for more products",
            "product_name": "product name for search_refinement" | "N/A"
        }}

        STRICT INSTRUCTIONS:
        - Your entire output MUST be a single valid JSON object as shown above, with both "message_type" and "response" fields.
        - Do NOT include any markdown or extra explanation.
        - Do NOT include any text before or after the JSON object.
        - Do NOT use markdown code blocks (no ``` or ```json).
        - Do NOT include any comments.
        - If you cannot determine the type, default to {{"message_type": "general", "response": "Ooops! I got confused. Please tell me with more details what you want."}}

        MESSAGE TYPE DETERMINATION RULES (consider conversation history):

        For general messages:
        - If previous search query exists, message_type probably is search_refinement or new_search or show_more_products or needs_details.
        - First-time users asking about capabilities
        - General questions about how the bot works
        - Thank you messages or positive feedback
        - Users who haven't shared any content yet
        - Be concise, calm, and user-friendly. NO LONG MESSAGES.
        - Use emoji where appropriate.
        - Use new lines for clarity.
        - Let the user know they can share Instagram posts or reels (not stories) for analysis.
        - You can analyze both images and videos, and recognize multiple products in a video.
        - For posts with multiple slides, only the first slide is received. If the user wants to analyze another slide, ask them to send a screenshot.

        For search_refinement:
        - User has previously shared content and received search results
        - User wants to modify or improve the previous search
        - User provides additional details about what they're looking for
        - If there was a previous search query, enhance it with the new details from the user and return the enhanced query.
        - If the user wants something different, create a new focused query.
        - Keep queries concise but specific.

        For needs_details:
        - User has shared content but the search results weren't satisfactory
        - User needs to provide more specific preferences (price, style, color, etc.)
        - Consider that user already sent a post or video for analysis.
        - Return "needs_details" for message_type and ask for the details and not ask to share instagram post or reel.

        For new_search:
        - User mentions a product that wasn't found in the previous analysis
        - User wants to search for a different product from the same content
        - If user used some words like how about, what about, etc., return new_search.
        - Return a specific, focused instruction for vision model that describes the missed product. Vision model (another function) will be used to analyze the post or video again.
        - Include color, style, type, and any other relevant details if provided by the user.
        - Keep it concise but descriptive.

        For show_more_products:
        - If some words like yes, sure, do that, show me more, etc., in conversation history, return show_more_products.
        - User has received search results and wants to see more options
        - User is unsatisfied with current results and asks for alternatives
        - User explicitly asks for "more products" or "show more"
        - Return show_more_products for message_type.

        Examples:
        1. Previous query: "summer dresses floral"
           User: "I want something more casual and in blue"
           Output:
           {{
               "message_type": "search_refinement",
               "response": "casual blue summer dresses comfortable",
               "product_name": "Summer dresses"
           }}

        2. Previous query: "leather boots black"
           User: "These are too expensive"
           Output:
           {{
               "message_type": "needs_details",
               "response": "I understand you're looking for more affordable options. What's your preferred price range for the boots?"
               "product_name": "N/A"
           }}

        3. User: "I also saw a red crossbody bag in the video, can you find that?"
           Output:
           {{
               "message_type": "new_search",
               "response": "red crossbody bag leather shoulder strap"
               "product_name": "Red crossbody bag"
           }}

        4. User: "Thank you, that's exactly what I wanted!"
           Output:
           {{
               "message_type": "general",
               "response": "You're welcome! 😊\n\nFeel free to share another post or reel if you need more products!"
               "product_name": "N/A"
           }}

        5. User: "Can you show me more options?"
           Output:
           {{
               "message_type": "show_more_products",
               "response": "I'll show you more product options from your search."
               "product_name": "N/A"
           }}
        """)

        # Parse response with better error handling
        try:
            response_text = response.text.strip()
            if not response_text:
                raise ValueError("Empty response from Gemini")

            # Remove any markdown code block markers or extra text
            # (Should not be present if model follows instructions, but just in case)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Try to extract JSON object from the text
            # Find the first '{' and last '}'
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
                raise ValueError("No JSON object found in Gemini response")

            json_str = response_text[start_idx:end_idx+1]
            
            # Clean the JSON string to handle common issues
            json_str = json_str.replace('\n', ' ').replace('\r', ' ')
            json_str = re.sub(r'[^\x20-\x7E]', '', json_str)  # Remove non-printable characters
            
            # Try to fix common JSON issues
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays

            # Parse the cleaned JSON
            result = json.loads(json_str)

            # Validate required fields
            if "message_type" not in result or "response" not in result or "product_name" not in result:
                raise ValueError("Missing required fields in response")

            # Add assistant response to history
            #add_to_conversation_history(user_id, "assistant", result["response"])

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse Gemini response: {str(e)}. Response: {response.text}")
            # Return fallback response
            fallback_response = "I'm having trouble processing your request right now. Could you please try sharing an Instagram post or reel with me?"
            #add_to_conversation_history(user_id, "assistant", fallback_response)
            return "general", fallback_response, "N/A"

        # Trim history if too long (keep last 10 messages)
        #conversation_history = get_conversation_history(user_id)
        #if len(conversation_history) > 12:  # 10 messages + system prompt + buffer
        #    logger.info(f"Trimming conversation history. Current length: {len(conversation_history)}")
            # Find system messages and keep them
        #    system_messages = [msg for msg in conversation_history if msg["role"] == "system"]
            # Get last 10 non-system messages
        #    non_system_messages = [msg for msg in conversation_history if msg["role"] != "system"][-10:]
        #    logger.info(f"System messages to keep: {len(system_messages)}")
        #    logger.info(f"Non-system messages to keep: {len(non_system_messages)}")
            # Combine system messages with recent non-system messages
        #    clear_conversation_history(user_id)
        #    for msg in system_messages + non_system_messages:
        #        add_to_conversation_history(user_id, msg["role"], msg["content"])
        #    logger.info(f"Conversation history trimmed. New length: {len(get_conversation_history(user_id))}")

        return result["message_type"], result["response"], result["product_name"]

    except Exception as e:
        await error_handler(
            f"Error processing message with Gemini: {str(e)}",
            "error",
            "high",
            logger
        )
        # Return general message type as fallback
        return "general", "Ooops! I got confused. Please tell me with more details what you want.", "N/A"



#------------------------------------* CLEAR TEMP PRODUCTS *------------------------------------
async def main_brain_message_processor(user_id, user_message, ai_client, logger):
    try:
        temp_vars = await get_temp_variables(user_id, ['initial_query', 'reel_caption'], logger)
        if temp_vars:
            previous_query = temp_vars.get('initial_query')
            reel_caption = temp_vars.get('reel_caption')
        else:
            previous_query = None
            reel_caption = None

        message_type, response, product_name = await process_message_with_gemini(user_id, user_message, ai_client['client'], previous_query, logger)
        logger.info(f"message_type: {message_type}")
        logger.info(f"response: {response}")
        logger.info(f"previous_query: {previous_query}")

        if message_type == "general":
            if response:
                #logger.info(f"sending general message")
                await send_message_to_user(response, user_id, logger)
            else:
                general_message_text = get_text('general_message')
                await send_message_to_user(general_message_text, user_id, logger)
        
        # Search refinement
        elif message_type == "search_refinement":
            refined_query = response
            if not previous_query:
                general_message_text = get_text('general_message')
                await send_message_to_user(general_message_text, user_id, logger)
            else:
                query_id = await save_query(user_id, product_name, refined_query, 'N/A', 'N/A', logger)
                logger.info(f"query_id: {query_id}")
                await insert_temp_variables(user_id, logger, initial_query=refined_query)
                logger.info(f"initial query changed to: {refined_query}")
                refined_top_products = await google_search_with_hasdata(refined_query, 'N/A', 'ca', user_id, logger)
                if refined_top_products:
                    await send_message_to_user(refined_top_products, user_id, logger)
                else:
                    no_products_found_text = get_text('no_products_found')
                    await send_message_to_user(no_products_found_text, user_id, logger)
        
        # Needs details
        elif message_type == "needs_details":
            await send_message_to_user(response, user_id, logger)
        
        # New search
        elif message_type == "new_search":
            if ai_client['client_type'] == 'gemini':
                new_search_query = await frames_to_search_query_gemini(user_id, ai_client['client'], reel_caption, response, logger)
            else:
                new_search_query = await frames_to_search_query_openai(user_id, ai_client['client'], reel_caption, response, logger)

            logger.info(f"new_search_query: {new_search_query}")
            
            if new_search_query and len(new_search_query) > 0:
                for product_name, details in new_search_query.items():
                    await save_query(user_id, product_name, details['search_query'], details['product_brand'], 'N/A', logger)
                    search_query = details['search_query']
                    await insert_temp_variables(user_id, logger, initial_query=search_query)
                    product_brand = details['product_brand']
                    #add_to_conversation_history(user_id, "assistant", f"New search query for {product_name}: {search_query}")
                    logger.info(f"Stored new search query in conversation history: {product_name} - {search_query}")
                
                first_product = list(new_search_query.values())[0]
                search_results = await google_search_with_hasdata(
                    first_product['search_query'], 
                    first_product['product_brand'], 
                    'ca', 
                    user_id, 
                    logger
                )
                if search_results:
                    await send_message_to_user(search_results, user_id, logger)
                else:
                    no_products_found_text = get_text('no_products_found')
                    await send_message_to_user(no_products_found_text, user_id, logger)
            else:
                no_products_found_text = get_text('no_products_found')
                await send_message_to_user(no_products_found_text, user_id, logger)
        
        # Show more products
        elif message_type == "show_more_products":
            query_id = await get_query_id(user_id, previous_query, logger)
            if not query_id:
                internal_error_text = get_text('internal_error')
                await send_message_to_user(internal_error_text, user_id, logger)
                return False
            await send_message_to_user(response, user_id, logger)
            await handle_more_products_request(user_id, query_id, logger)
            #result = await send_more_products_postback_message(user_id, query_id, logger=logger)
            #if not result:
            #    no_more_products_text = get_text('no_more_products')
            #    await send_message_to_user(no_more_products_text, user_id, logger)
        
        else:
            internal_error_text = get_text('internal_error')
            await send_message_to_user(internal_error_text, user_id, logger)
        
        return True
        
    except Exception as e:
        logger.error(f"Error in main_brain_message_processor: {str(e)}")
        internal_error_text = get_text('internal_error')
        await send_message_to_user(internal_error_text, user_id, logger)
        return False

#------------------------------------* GET AI CLIENT BASED ON DASHBOARD SETTINGS *------------------------------------
async def get_ai_client(openai_client, gemini_client):
    active_model = await get_active_model()
    if active_model == 'openai':
        return {'client': openai_client, 'client_type': 'openai'}
    else:
        return {'client': gemini_client, 'client_type': 'gemini'}

#------------------------------------* DUPLICATE MESSAGE CHECK *------------------------------------
message_cache = {}
MESSAGE_CACHE_TTL = 60  # seconds

async def is_duplicate_message(message_id):
    current_time = time.time()
    # Remove expired entries
    expired_keys = [k for k, v in message_cache.items() if current_time - v > MESSAGE_CACHE_TTL]
    for k in expired_keys:
        del message_cache[k]
    if message_id in message_cache:
        return True
    message_cache[message_id] = current_time
    return False

#------------------------------------* URL VALIDATION FUNCTIONS *------------------------------------
def is_valid_url_basic(url):
    """Validate if a URL is properly formatted and accessible"""
    if not url or url == "N/A" or url.strip() == "":
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def is_valid_product_url(url):
    """Check if URL is a valid product URL, not an internal API URL or problematic URL"""
    if not is_valid_url_basic(url):
        return False
    
    # Filter out internal API URLs and problematic domains
    invalid_domains = [
        'api.scrapingdog.com',
        'api.example.com',
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        'internal',
        'dev',
        'staging',
        'test'
    ]
    
    # Filter out URLs with API keys or internal parameters
    invalid_patterns = [
        'api_key=',
        'access_token=',
        'secret=',
        'password=',
        'internal=',
        'debug=',
        'test=',
        'dev=',
        'staging='
    ]
    
    try:
        parsed = urlparse(url)
        
        # Check for invalid domains
        if any(invalid_domain in parsed.netloc.lower() for invalid_domain in invalid_domains):
            return False
        
        # Check for invalid patterns in the URL
        if any(pattern in url.lower() for pattern in invalid_patterns):
            return False
        
        # Check for suspicious query parameters
        if parsed.query:
            suspicious_params = ['api_key', 'token', 'secret', 'key', 'auth']
            query_params = parse_qs(parsed.query)
            if any(param in query_params for param in suspicious_params):
                return False
        
        # Ensure it's a web URL (http/https)
        if parsed.scheme not in ['http', 'https']:
            return False
        
        # Check for minimum domain length (avoid very short domains)
        if len(parsed.netloc) < 5:
            return False
        
        return True
        
    except Exception:
        return False

def debug_url_validation(url, logger=None):
    """Debug function to test URL validation and provide detailed feedback"""
    if not url or url == "N/A" or url.strip() == "":
        return False, "Empty or N/A URL"
    
    try:
        parsed = urlparse(url)
        
        # Check basic format
        if not all([parsed.scheme, parsed.netloc]):
            return False, "Missing scheme or netloc"
        
        # Check for invalid domains
        invalid_domains = [
            'api.scrapingdog.com', 'api.example.com', 'localhost', 
            '127.0.0.1', '0.0.0.0', 'internal', 'dev', 'staging', 'test'
        ]
        
        if any(invalid_domain in parsed.netloc.lower() for invalid_domain in invalid_domains):
            return False, f"Invalid domain: {parsed.netloc}"
        
        # Check for invalid patterns
        invalid_patterns = [
            'api_key=', 'access_token=', 'secret=', 'password=', 
            'internal=', 'debug=', 'test=', 'dev=', 'staging='
        ]
        
        if any(pattern in url.lower() for pattern in invalid_patterns):
            return False, f"Contains invalid pattern: {[p for p in invalid_patterns if p in url.lower()]}"
        
        # Check for suspicious query parameters
        if parsed.query:
            suspicious_params = ['api_key', 'token', 'secret', 'key', 'auth']
            query_params = parse_qs(parsed.query)
            found_suspicious = [param for param in suspicious_params if param in query_params]
            if found_suspicious:
                return False, f"Suspicious query parameters: {found_suspicious}"
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            return False, f"Invalid scheme: {parsed.scheme}"
        
        # Check domain length
        if len(parsed.netloc) < 5:
            return False, f"Domain too short: {parsed.netloc}"
        
        return True, "URL is valid"
        
    except Exception as e:
        return False, f"Exception during validation: {str(e)}"

def filter_valid_products(products, logger):
    """Filter out products with invalid data that would cause Facebook API errors"""
    if not isinstance(products, list):
        #logger.warning(f"Invalid products format: Expected list but got {type(products)}")
        return []
    
    valid_products = []
    for i, product in enumerate(products):
        if not isinstance(product, dict):
            #logger.warning(f"Skipping invalid product entry at index {i}")
            continue
            
        # Check all required URL fields
        product_url = product.get('product_url')
        thumbnail_url = product.get('thumbnail_url')
        image_url = product.get('image_url')
        
        # Validate URLs with enhanced validation
        if not is_valid_product_url(product_url):
            is_valid, reason = debug_url_validation(product_url, logger)
            logger.warning(f"Skipping product {i} with invalid product_url: {product_url} - Reason: {reason}")
            continue
            
        # For thumbnail/image URLs, we can be less strict since they might be CDN URLs
        if not is_valid_url_basic(thumbnail_url) and not is_valid_url_basic(image_url):
            #logger.warning(f"Skipping product {i} with invalid thumbnail/image URLs: {thumbnail_url}, {image_url}")
            continue
            
        # Check for required fields
        if not product.get('product_title'):
            #logger.warning(f"Skipping product {i} with missing product_title")
            continue
            
        valid_products.append(product)
    
    logger.info(f"Filtered {len(products)} products to {len(valid_products)} valid products")
    
    # Log details about filtered products for debugging
    if len(valid_products) < len(products):
        logger.info(f"Filtered out {len(products) - len(valid_products)} invalid products")
    
    return valid_products

def validate_template_data(template_data, logger):
    """Validate that template data has all required fields for Facebook API"""
    required_fields = ["title", "image_url", "subtitle", "buttons"]
    for field in required_fields:
        if not template_data.get(field):
            logger.warning(f"Missing required field in template: {field}")
            return False
    return True

def create_safe_message(product_data, user_id, logger):
    """Create a safe message that won't cause Facebook API errors"""
    if not product_data or len(product_data) == 0:
        return general_payload_message(user_id, "Sorry, no valid products found. Please try again.", logger)
    
    # Filter valid products
    valid_products = filter_valid_products(product_data, logger)
    
    if not valid_products:
        return general_payload_message(user_id, "Sorry, I couldn't find any valid products to show you. Please try a different image or reel.", logger)
    
    # Create template message with valid products
    return create_generic_template_message(user_id, valid_products, logger)

#------------------------------------* ENHANCED MESSAGE SENDING WITH ERROR RECOVERY *------------------------------------
async def send_message_with_fallback(user_id, message_data, logger):
    """Send message with fallback handling for Facebook API errors"""
    try:
        # Try to send the full template
        return await send_message_to_user(message_data, user_id, logger)
    except Exception as e:
        if "Invalid message data" in str(e) or "400" in str(e):
            logger.warning(f"Facebook API rejected message, sending fallback: {str(e)}")
            # Send simplified message instead
            fallback_message = "Here are some products I found for you! Check them out! 🛍️"
            return await send_message_to_user(fallback_message, user_id, logger)
        else:
            # Re-raise other exceptions
            raise e

