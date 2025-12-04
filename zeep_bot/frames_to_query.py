import os
import json
import time
import re
import base64
from pathlib import Path
from logging import Logger
from google.genai import types

#------------------------------------* FRAMES TO SEARCH QUERY GEMINI *------------------------------------
FRAMES_PATH = "./frames"

#------------------------------------* GEMINI API COST CONSTANTS *------------------------------------
GEMINI_TOKEN_COST = 0.1 / 1_000_000  # $0.7 per 1 million tokens
GEMINI_FRAME_TOKENS = 260  # tokens per frame
GEMINI_SYSTEM_PROMPT_TOKENS = 260  # system prompt tokens
GEMINI_OUTPUT_TOKENS = 50  # output tokens


async def frames_to_search_query_gemini(user_id, gemini_client, reel_caption, logger: Logger):
    logger.info("now in frames_to_search_query_gemini")
    frames_path = f"{FRAMES_PATH}/{user_id}/"
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

    system_instruction = f"""
        You are a product recognition expert for online shopping. You are given one or a set of frames from an Instagram reel that features one or more products for recognition. 
        Your PRIMARY task is to identify the **BRAND** and **PRODUCT TITLE** (name) of the main product(s) being advertised, along with detailed information for deep research and analysis.

        #### Instructions:

        1.  **Identify the Product Type:**
            - First, determine the type of product in the images by analyzing visual characteristics such as shape, color, size, and any visible text or logos.
            - Look carefully for brand logos, brand names, or any text that indicates the manufacturer.

        2.  **Extract Product Brand (CRITICAL):**
            - **PRIORITY TASK:** Identify the brand name from:
                - Visible logos on the product
                - Text on packaging or product
                - Brand names mentioned in the reel caption
                - Recognizable brand design patterns or signatures
            - Common brand identification tips:
                - Check product labels, tags, or packaging
                - Look for distinctive brand logos (swoosh for Nike, apple for Apple, etc.)
                - Examine the reel caption for brand mentions
                - Recognize brand-specific design elements
            - If brand is clearly identifiable, provide the exact brand name (e.g., "Nike", "Samsung", "Apple", "Adidas")
            - If brand cannot be identified with confidence, set to 'N/A'

        3.  **Extract Product Title/Name (CRITICAL):**
            - Create a specific, searchable product title that is **at most 3-4 words**
            - Include brand and model in the title if known (e.g., "Nike Air Max 270", "Samsung Galaxy Buds 2 Pro")
            - If brand unknown, use descriptive title (e.g., "Wireless Bluetooth Earbuds", "Black Leather Jacket")
            - Make it specific enough for online search

        6.  **Check if Product is Prohibited:**
            - Set `not_allowed` to `True` if the product matches any category in:
            {json.dumps(prohibited_products, indent=4)}
            - Set to `False` if the product is allowed

        7.  **Use the Reel Caption:**
            - **IMPORTANT:** The reel caption often contains the brand name and product details
            - Extract brand names and model information from the caption
            - Translate key terms if necessary

        8.  **Handle Multiple Products:**
            - If the same product appears in multiple frames, consolidate into **one entry**
            - If multiple different products are shown, create **separate entries** for each
            - Focus only on main products, ignore accessories or background items

        #### Response Format:
        Return a JSON object where each key is a product title (including brand if known, max 3-4 words) and the value contains:
        - product_brand: The brand name (CRITICAL - extract from images/caption) or 'N/A'
        - product_title: The product title (same as the key)
        - not_allowed: Boolean indicating if the product is prohibited

        **IMPORTANT:** Focus on accurately identifying the BRAND and creating a clear PRODUCT TITLE.

        Exactly follow this format:
        {{
            "Samsung Galaxy Earbuds": {{
                "product_brand": "Samsung",
                "product_title": "Samsung Galaxy Buds 2 Pro",
                "not_allowed": false
            }},
            "Nike Air Max Shoes": {{
                "product_brand": "Nike",
                "product_title": "Nike Air Max 270 Shoes",
                "not_allowed": false
            }},
            "Wireless Bluetooth Earbuds": {{
                "product_brand": "N/A",
                "product_title": "Wireless Bluetooth Earbuds",
                "not_allowed": false
            }}
        }}
    """

    start_time = time.time()
    for image_name in all_images:
        image_path = os.path.join(frames_path, image_name)
        with open(image_path, "rb") as f:
            local_file_img_bytes = f.read()
            # Create proper Part object for google.genai API
            image_part = types.Part.from_bytes(
                data=local_file_img_bytes,
                mime_type="image/jpeg"
            )
            image_files.append(image_part)

    usage_tokens = total_frame_count * GEMINI_FRAME_TOKENS + GEMINI_SYSTEM_PROMPT_TOKENS + GEMINI_OUTPUT_TOKENS
    usage_cost = usage_tokens * GEMINI_TOKEN_COST

    try:
        # Create the content list with proper format for google.genai API
        content_parts = [types.Part.from_text(text=system_instruction)]
        content_parts.extend(image_files)
        content_parts.append(types.Part.from_text(text=f"Reel Caption: {reel_caption}"))
        
        # Use the new google.genai API
        response = gemini_client.models.generate_content(
            # MODEL NAME IS ALWAYS gemini-2.5-flash-lite <---------------------------------
            model="gemini-2.5-flash-lite",
            contents=content_parts
        )
        end_time = time.time()
        response_time = end_time - start_time

        # Check if request was blocked
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
            logger.info("request was blocked")
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

            #logger.info(f"parsed response: {parsed_response}")
            
            # Validate the response structure
            if not isinstance(parsed_response, dict):
                raise ValueError("Response is not a dictionary")
            
            # Validate each product entry
            for product_title, details in parsed_response.items():
                if not isinstance(details, dict):
                    raise ValueError(f"Product details for {product_title} is not a dictionary")
                
                # Required fields in order: product_brand, product_title, not_allowed
                required_fields = ["product_brand", "product_title", "not_allowed"]
                
                for field in required_fields:
                    if field not in details:
                        raise ValueError(f"Missing required field '{field}' for product {product_title}")
                    
                    # Validate field types
                    if field == "not_allowed":
                        if not isinstance(details[field], bool):
                            raise ValueError(f"Field '{field}' for product {product_title} must be a boolean")
                    else:
                        if not isinstance(details[field], str):
                            raise ValueError(f"Field '{field}' for product {product_title} must be a string")
                
                # Log extracted brand and product name for debugging
                logger.info(f"Extracted Product: {details['product_title']} | Brand: {details['product_brand']}")

            return parsed_response
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {str(e)}")
        except ValueError as e:
            raise ValueError(f"Invalid response structure: {str(e)}")
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        error_message = str(e)
        logger.error(f"Error in frames_to_search_query_gemini: {error_message}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None
