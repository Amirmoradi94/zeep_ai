import hashlib
import hmac
import aiohttp
import aiofiles
import os
import re
from fastapi import Request
import time
import shutil
from urllib.parse import urlparse, parse_qs
import json
from dotenv import load_dotenv
import requests
from get_text import get_text
from query_to_narration import query_to_narration
from narration_to_voice import narration_to_voice
from db import (
    save_query, error_handler,
    clean_temp_variables,
    get_temp_variables,
    get_active_model,
    insert_temp_variables,
    get_query_info,
    update_query
)
from typing import Tuple, Optional


load_dotenv()

VIDEOS_PATH = os.getenv("VIDEOS_PATH", "videos")
FRAMES_PATH = os.getenv("FRAMES_PATH", "frames")
AUDIOS_PATH = os.getenv("AUDIOS_PATH", "audios")
SAVED_IMAGES_PATH = os.getenv("SAVED_IMAGES_PATH", "saved_images")
KEYFRAME_EXTRACTION_THRESHOLD = int(os.getenv("KEYFRAME_EXTRACTION_THRESHOLD", 20))
SUBPROCESS_TIMEOUT = int(os.getenv("SUBPROCESS_TIMEOUT", 10))

#------------------------------------* OPENAI API COST CONSTANTS *------------------------------------
OPENAI_TOKEN_COST = 0.15 / 1_000_000  # $0.00015 per 1 million tokens
OPENAI_FRAME_TOKENS = 100  # tokens per frame
OPENAI_SYSTEM_PROMPT_TOKENS = 260  # system prompt tokens
OPENAI_OUTPUT_TOKENS = 50  # output tokens

#------------------------------------* API VERSION *------------------------------------
# Facebook Graph API version - use v24.0 or latest stable version
API_VERSION = os.getenv("GRAPH_API_VERSION", "v24.0")

#------------------------------------* CLEAN MEMORY *------------------------------------
async def clean_memory_and_temp_variables(user_id, logger):
    video_path = f"{VIDEOS_PATH}/{user_id}/"
    audio_path = f"{AUDIOS_PATH}/{user_id}/"
    frames_path = f"{FRAMES_PATH}/{user_id}/"
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

#------------------------------------* SAVE FRAMES WITH QUERY ID *------------------------------------
async def save_frames_with_query_id(user_id, query_ids, logger):
    try:
        # Source directory where frames are extracted
        source_frames_path = f"{FRAMES_PATH}/{user_id}/"
        
        # Destination directory for saved images with query_id
        saved_images_path = f"{SAVED_IMAGES_PATH}/{user_id}/"
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
async def process_instagram_post(attachment_url, reel_caption, user_id, client, attachment_type, location, logger):
    #logger.info("now in process_instagram_post")
    # Import here to avoid circular import
    from post_to_frames import post_to_frames
    from frames_to_query import frames_to_search_query_gemini
    try:
        post_to_frames_success = await post_to_frames(attachment_url, user_id, attachment_type, logger)
        if not post_to_frames_success:
            return "error_posting_frames"

        logger.info("post to frame success")
        # Extract the actual client from the ai_client dict
        actual_client = client['client'] if isinstance(client, dict) else client
        generated_response = await frames_to_search_query_gemini(user_id, actual_client, reel_caption, logger)
        if not generated_response:
            return "error_generating_query"
        logger.info(f"generated response: {generated_response}")
        
        if generated_response == 'blocked':
            return 'restricted_product_message_sent'

        # Check if any product in the response is not allowed
        all_not_allowed = all(product_details.get('not_allowed', False) for product_details in generated_response.values())
        if all_not_allowed:
            return 'restricted_product_message_sent'
            
        # Filter out not allowed products
        filtered_response = {
            product_name: details 
            for product_name, details in generated_response.items() 
            if not details.get('not_allowed', False)
        }
        generated_response = filtered_response
        #------------------------------------* SAVE QUERY *------------------------------------
        query_ids = []
        logger.info("now saving query")

        if len(generated_response) == 1 and list(generated_response.values())[0]['product_brand'] != 'N/A' and list(generated_response.values())[0].get('product_model', 'N/A') != 'N/A':
            query_id = await save_query(
                user_id=user_id,
                product_name=list(generated_response.keys())[0],
                product_brand=list(generated_response.values())[0]['product_brand'],
                product_title=list(generated_response.values())[0]['product_title'],
                feedback=None,
                logger=logger
            )
            #if await is_saving_training_data():
            #    await save_frames_with_query_id(user_id, [query_id], logger)
        elif len(generated_response) == 1 and (list(generated_response.values())[0]['product_brand'] == 'N/A' or list(generated_response.values())[0].get('product_model', 'N/A') == 'N/A'):
            logger.info("now asking user for product brand or model (one or both missing)")
            
            # Save incomplete product info to temp variables
            product_details = list(generated_response.values())[0]
            product_name = list(generated_response.keys())[0]
            
            # Save query first to get query_id
            query_id = await save_query(
                user_id=user_id,
                product_name=product_name,
                product_brand=product_details.get('product_brand', 'N/A'),
                product_title=product_details.get('product_title', product_name),
                feedback=None,
                logger=logger
            )
            
            if query_id:
                # Store query_id in temp variables for later retrieval
                await insert_temp_variables(
                    user_id,
                    logger,
                    query_id=query_id
                )
            
            return 'ask_user_for_product_brand'
        
        elif len(generated_response) > 1 :
            #------------------------------------* SAVE QUERY *------------------------------------
            for product_name, details in generated_response.items():
                logger.info(f"now saving query for product: {product_name}")
                query_id = await save_query(
                    user_id=user_id,
                    product_name=product_name,
                    product_brand=details['product_brand'].lower() if details['product_brand'] != 'N/A' else 'N/A',
                    product_title=details['product_title'],
                    feedback=None,
                    logger=logger
                )
                if query_id:
                    query_ids.append(query_id)

            #if await is_saving_training_data():
            #    await save_frames_with_query_id(user_id, query_ids, logger)

            if len(query_ids) > 1 and all(qid is not None for qid in query_ids):
                list_product_names = list(generated_response.keys())
                list_product_brands = [details['product_brand'] for details in generated_response.values()]
                list_product_models = [details.get('product_model', 'N/A') for details in generated_response.values()]
                list_product_titles = [details['product_title'] for details in generated_response.values()]
                return (list_product_names, query_ids, list_product_brands, list_product_models, list_product_titles)
        
        #------------------------------------* DEEP SEARCH *------------------------------------
        generated_narration = None
        logger.info("now generating narration")
        if isinstance(generated_response, dict) and generated_response.values():
            product_info = {
                'product_title': list(generated_response.values())[0]['product_title'],
                'product_brand': list(generated_response.values())[0]['product_brand']
            }
            generated_narration = query_to_narration(product_info, location, logger)
            if not generated_narration:
                return 'no_narration_generated'

            # Send message to user that research is done and voice is being generated
            research_complete_message = "تحقیقم رو انجام دادم و الان برات پیام صوتی می‌فرستم 🎤"
            await send_message_to_user(research_complete_message, user_id, logger)

            # Select a single voice for all parts to maintain consistency
            import random
            from narration_to_voice import AVAILABLE_SPEAKERS
            selected_voice = random.choice(AVAILABLE_SPEAKERS)
            logger.info(f"Selected voice for all parts: {selected_voice}")

            # Process and send each voice part immediately as it's generated
            for i, narration_text in enumerate(generated_narration, 1):
                logger.info(f"Generating voice part {i}/{len(generated_narration)}")
                
                # Start timing
                start_time = time.time()
                
                voice_success = await narration_to_voice(
                    narration_text=narration_text, 
                    gemini_client=actual_client,
                    logger=logger,
                    user_id=user_id,
                    voice_name=selected_voice  # Use same voice for all parts
                )
                
                # Calculate elapsed time
                elapsed_time = time.time() - start_time
                logger.info(f"Voice part {i}/{len(generated_narration)} generated in {elapsed_time:.2f} seconds")
                
                if not voice_success:
                    return 'no_voice_generated'
                
                # Send voice immediately after generation
                logger.info(f"Sending voice part {i}/{len(generated_narration)} to user")
                await send_message_to_user(voice_success, user_id, logger)
                
                # Clean up voice files immediately after successful send
                import os
                import glob
                voices_dir = f"./voices/{user_id}/"
                if os.path.exists(voices_dir):
                    try:
                        # Delete all voice files in the directory, but keep the directory
                        voice_files = glob.glob(os.path.join(voices_dir, "*"))
                        for voice_file in voice_files:
                            if os.path.isfile(voice_file):
                                os.remove(voice_file)
                        logger.info(f"Cleaned up {len(voice_files)} voice file(s) after sending part {i}: {voices_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up voice files: {e}")

            return 'voice_generated'
        
        # If no narration was generated, return error
        return 'no_narration_generated'

    except Exception as e:
        await error_handler(
            f"Error processing Instagram post: {str(e)}",
            "error",
            "high",
            logger
        )
        return 'error_processing_instagram_post'

#------------------------------------* SEND SELECT PRODUCT POSTBACK MESSAGE *------------------------------------
async def send_select_product_postback_message(user_id, product_names, query_ids, product_brands, product_models, logger):
    url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
    headers = {
        'Content-Type': 'application/json'
    }

    #print(f"product brands: {product_brands}")

    # Ensure all lists have the same length
    min_length = min(len(product_names), len(query_ids), len(product_brands), len(product_models))
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


#------------------------------------* SEND FOLLOW POSTBACK MESSAGE *------------------------------------
async def send_follow_postback_message(user_id, logger):
    url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Get the page name from environment variable or use a default
    page_name = os.getenv('PAGE_NAME', '@zeep.ai')
    
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

        
#------------------------------------* SEND MESSAGE TO USER *------------------------------------
async def send_message_to_user(message, user_id, logger):
    try:
        # Ensure user_id is a string
        if isinstance(user_id, (int, float)):
            user_id = str(int(user_id))
        
        # Handle case where voices are generated and need to be sent to user
        if isinstance(message, bool) and message:
            # Read voice files from /voices directory
            voices_path = f"./voices/{user_id}/"
            
            # Check if voices directory exists
            if not os.path.exists(voices_path):
                logger.warning(f"Voices directory not found: {voices_path}")
                await error_handler(
                    f"Voices directory not found for user {user_id}",
                    "error",
                    "medium",
                    logger
                )
                return False
            
            # Get all audio files from the directory
            audio_extensions = ('.mp3', '.wav', '.ogg', '.m4a')
            voice_files = [
                f for f in os.listdir(voices_path) 
                if f.lower().endswith(audio_extensions)
            ]
            
            if not voice_files:
                logger.warning(f"No voice files found in {voices_path}")
                await error_handler(
                    f"No voice files found for user {user_id}",
                    "error",
                    "medium",
                    logger
                )
                return False
            
            # Sort files to ensure consistent order
            voice_files.sort()
            
            logger.info(f"Found {len(voice_files)} voice file(s) to send for user {user_id}")
            
            access_token = os.getenv('PAGE_ACCESS_TOKEN')
            if not access_token:
                await error_handler(
                    "Missing PAGE_ACCESS_TOKEN",
                    "error",
                    "high",
                    logger
                )
                return False
            
            # Send each voice file
            success_count = 0
            async with aiohttp.ClientSession() as session:
                for voice_file in voice_files:
                    try:
                        file_path = os.path.join(voices_path, voice_file)
                        
                        # Send file directly to Facebook Messenger API
                        message_url = f"https://graph.facebook.com/{API_VERSION}/me/messages"
                        
                        # Read file as binary
                        async with aiofiles.open(file_path, 'rb') as f:
                            file_data = await f.read()
                        
                        # Determine MIME type based on extension
                        file_ext = os.path.splitext(voice_file)[1].lower()
                        mime_types = {
                            '.mp3': 'audio/mpeg',
                            '.wav': 'audio/wav',
                            '.ogg': 'audio/ogg',
                            '.m4a': 'audio/mp4'
                        }
                        mime_type = mime_types.get(file_ext, 'audio/mpeg')
                        
                        # Prepare multipart form data for direct upload
                        form_data = aiohttp.FormData()
                        form_data.add_field(
                            'recipient',
                            json.dumps({"id": user_id})
                        )
                        form_data.add_field(
                            'message',
                            json.dumps({
                                'attachment': {
                                    'type': 'audio',
                                    'payload': {
                                        'is_reusable': False
                                    }
                                }
                            })
                        )
                        form_data.add_field(
                            'filedata',
                            file_data,
                            filename=voice_file,
                            content_type=mime_type
                        )
                        
                        # Send file directly
                        async with session.post(
                            message_url, 
                            data=form_data, 
                            params={'access_token': access_token}
                        ) as message_response:
                            if message_response.status == 200:
                                logger.info(f"Successfully sent voice file: {voice_file}")
                                success_count += 1
                            else:
                                response_text = await message_response.text()
                                logger.error(f"Failed to send voice file {voice_file}: {message_response.status}, Response: {response_text}")
                    
                    except Exception as e:
                        logger.error(f"Error sending voice file {voice_file}: {str(e)}")
                        await error_handler(
                            f"Error sending voice file {voice_file}: {str(e)}",
                            "error",
                            "medium",
                            logger
                        )
                        continue
                
                # Return True if at least one file was sent successfully
                if success_count > 0:
                    logger.info(f"Successfully sent {success_count}/{len(voice_files)} voice file(s)")
                    return True
                else:
                    logger.error(f"Failed to send all voice files for user {user_id}")
                    return False
        
        # Handle case where input is a string message identifier
        elif isinstance(message, str):
            payload = await general_payload_message(user_id, message, logger)
            if not payload:
                return False
        
        
        else:
            logger.error(f"Unsupported message type: {type(message)}")
            await error_handler(
                f"Unsupported message type in send_message_to_user: {type(message)}",
                "error",
                "high",
                logger
            )
            return False

        # Send the message payload
        url = f"https://graph.facebook.com/{API_VERSION}/me/messages?access_token={os.getenv('PAGE_ACCESS_TOKEN')}"
        headers = {
            "Content-Type": "application/json",
        }
        
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
        app_secret = os.getenv('FACEBOOK_APP_SECRET')

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
            #await error_handler(
            #    "Invalid Facebook signature",
            #    "error",
           #     "high",
           #     logger
        #)
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


#------------------------------------* GEMINI MESSAGE PROCESSOR *------------------------------------
async def process_message_with_gemini(
    user_message: str, 
    gemini_client,
    logger
) -> Tuple[str, Optional[str], str]:
    """
    Process user message using Gemini model to determine message type and generate appropriate response.
    
    Args:
        message: The user's message
        gemini_client: The Gemini client instance from zeep_main
        logger: Logger instance
    
    Returns:
        Tuple[str, Optional[str], str]: (message_type, response, product_info)
        - message_type can be: 'general' | 'product_details'
        - response: 
            * general: Answer for general message
            * product_details: JSON with product brand and/or model
    """
    try:
        # Use the new google.genai API
        prompt = f"""
        Analyze the user's message to determine the appropriate response.

        Here is the user's message:
        {user_message}

        Respond ONLY in the following JSON format (do not include any extra text, markdown, or explanation):

        {{
            "message_type": "general" | "product_details",
            "response": "answer user's general message" | {{"product_brand": "brand name or N/A", "product_model": "model name/number or N/A"}}
        }}
        
        For product_details:
        - Determine if user message contains product brand and/or model information.
        - Extract BOTH brand AND model if available (e.g., "Samsung M27", "iPhone 15 Pro", "Galaxy S24 Ultra")
        - If user provides brand only (e.g., "Samsung"), extract brand and set model to "N/A"
        - If user provides model only (e.g., "M27 27 inch"), set brand to "N/A" and extract model
        - If user provides both, extract both
        - If neither is provided, return "general" message_type and ask the user to share product brand and/or model
        - Model can include: model numbers, sizes, capacities (e.g., "M27", "27 inch FHD", "S24 Ultra", "256GB", "16 Pro Max")

        Examples:
        User: "Samsung M27 27 inch FHD monitor"
        Output:
        {{
            "message_type": "product_details",
            "response": {{"product_brand": "Samsung", "product_model": "M27 27 inch FHD"}}
        }}
        
        User: "iPhone 15 Pro Max"
        Output:
        {{
            "message_type": "product_details",
            "response": {{"product_brand": "Apple", "product_model": "iPhone 15 Pro Max"}}
        }}
        
        User: "Samsung Galaxy S24"
        Output:
        {{
            "message_type": "product_details",
            "response": {{"product_brand": "Samsung", "product_model": "Galaxy S24"}}
        }}
        
        User: "Samsung"
        Output:
        {{
            "message_type": "product_details",
            "response": {{"product_brand": "Samsung", "product_model": "N/A"}}
        }}
        
        User: "M27 monitor"
        Output:
        {{
            "message_type": "product_details",
            "response": {{"product_brand": "N/A", "product_model": "M27"}}
        }}
        
        User: "Hello, how are you?"
        Output:
        {{
            "message_type": "general",
            "response": "سلام! من خوبم، ممنون. چطور می‌تونم کمکت کنم؟"
        }}
        """
        
        # Use generate_content instead of start_chat for the new google.genai API
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        # Parse response with better error handling
        try:
            response_text = response.text.strip() if hasattr(response, 'text') else response.candidates[0].content.parts[0].text.strip()
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
            if "message_type" not in result or "response" not in result:
                raise ValueError("Missing required fields in response")

            # Add assistant response to history
            #add_to_conversation_history(user_id, "assistant", result["response"])

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse Gemini response: {str(e)}. Response: {response.text}")
            # Return fallback response
            fallback_response = "I'm having trouble processing your request right now. Could you please try sharing an Instagram post or reel with me?"
            #add_to_conversation_history(user_id, "assistant", fallback_response)
            return "general", fallback_response

        return result["message_type"], result["response"]

    except Exception as e:
        await error_handler(
            f"Error processing message with Gemini: {str(e)}",
            "error",
            "high",
            logger
        )
        # Return general message type as fallback
        return "general", "Ooops! I got confused. Please tell me with more details what you want."



#------------------------------------* CLEAR TEMP PRODUCTS *------------------------------------
async def main_brain_message_processor(user_id, user_message, ai_client, location, logger):
    try:

        message_type, response = await process_message_with_gemini(user_message, ai_client['client'], logger)
        logger.info(f"message_type: {message_type}")
        logger.info(f"response: {response}")

        if message_type == "general":
            if response:
                #logger.info(f"sending general message")
                await send_message_to_user(response, user_id, logger)
            else:
                general_message_text = get_text('general_message')
                await send_message_to_user(general_message_text, user_id, logger)
            return True
        
        # Product details (brand and/or model)
        elif message_type == "product_details":
            temp_variables = await get_temp_variables(user_id, ['query_id'], logger)
            if temp_variables:
                query_id = temp_variables.get('query_id')
                
                # Get stored product info from queries table
                query_info = await get_query_info(user_id, query_id, logger)
                if not query_info:
                    logger.error("Could not retrieve query info")
                    return False
                
                stored_product_name = query_info.get('product_name')
                stored_product_brand = query_info.get('product_brand', 'N/A')
                stored_product_title = query_info.get('product_title')
                
                # Parse the response to get brand and model from user input
                import json
                if isinstance(response, str):
                    try:
                        product_details = json.loads(response)
                    except:
                        product_details = {'product_brand': response, 'product_model': 'N/A'}
                elif isinstance(response, dict):
                    product_details = response
                else:
                    logger.error(f"Unexpected response type: {type(response)}")
                    return False
                
                user_provided_brand = product_details.get('product_brand', 'N/A')
                user_provided_model = product_details.get('product_model', 'N/A')
                
                # Merge with stored data: use user-provided if available, otherwise keep stored
                final_brand = user_provided_brand if user_provided_brand != 'N/A' else stored_product_brand
                final_model = user_provided_model if user_provided_model != 'N/A' else 'N/A'
                
                logger.info(f"User provided - Brand: {user_provided_brand}, Model: {user_provided_model}")
                logger.info(f"Stored - Brand: {stored_product_brand}")
                logger.info(f"Final - Brand: {final_brand}, Model: {final_model}")
                
                # Check if we still have missing information
                if final_brand == 'N/A' or final_model == 'N/A':
                    missing = []
                    if final_brand == 'N/A':
                        missing.append("برند (Brand)")
                    if final_model == 'N/A':
                        missing.append("مدل (Model)")
                    
                    missing_info = " و ".join(missing)
                    ask_again_message = f"لطفاً {missing_info} محصول رو بهم بگو تا بتونم بررسی دقیق‌تری انجام بدم."
                    await send_message_to_user(ask_again_message, user_id, logger)
                    
                    # Update query with what we have so far
                    if final_brand != 'N/A' and final_brand != stored_product_brand:
                        await update_query(query_id, user_id, final_brand, logger)
                    
                    return True
                
                # We have both brand and model, proceed with narration generation
                logger.info(f"Got complete product info - Brand: {final_brand}, Model: {final_model}")
                
                # Update query with final brand
                if final_brand != stored_product_brand:
                    await update_query(query_id, user_id, final_brand, logger)
                
                # Construct product_title with brand and model
                product_title = f"{final_brand} {final_model}".strip()
                
                product_info = {
                    'product_title': product_title,
                    'product_brand': final_brand
                }
                
                generated_narration = query_to_narration(product_info, location, logger)
                if not generated_narration:
                    return False

                # Send message to user that research is done and voice is being generated
                research_complete_message = "تحقیقم رو انجام دادم و الان برات پیام صوتی می‌فرستم 🎤"
                await send_message_to_user(research_complete_message, user_id, logger)

                # Select a single voice for all parts to maintain consistency
                import random
                from narration_to_voice import AVAILABLE_SPEAKERS
                selected_voice = random.choice(AVAILABLE_SPEAKERS)
                logger.info(f"Selected voice for all parts: {selected_voice}")

                # Process and send each voice part immediately as it's generated
                for i, narration_text in enumerate(generated_narration, 1):
                    logger.info(f"Generating voice part {i}/{len(generated_narration)}")
                    
                    # Start timing
                    start_time = time.time()
                    
                    voice_success = await narration_to_voice(
                        narration_text=narration_text, 
                        gemini_client=ai_client['client'],
                        logger=logger,
                        user_id=user_id,
                        voice_name=selected_voice  # Use same voice for all parts
                    )
                    
                    # Calculate elapsed time
                    elapsed_time = time.time() - start_time
                    logger.info(f"Voice part {i}/{len(generated_narration)} generated in {elapsed_time:.2f} seconds")
                    
                    if not voice_success:
                        return False
                    
                    # Send voice immediately after generation
                    logger.info(f"Sending voice part {i}/{len(generated_narration)} to user")
                    await send_message_to_user(voice_success, user_id, logger)
                    
                    # Clean up voice files immediately after successful send
                    import os
                    import glob
                    voices_dir = f"./voices/{user_id}/"
                    if os.path.exists(voices_dir):
                        try:
                            # Delete all voice files in the directory, but keep the directory
                            voice_files = glob.glob(os.path.join(voices_dir, "*"))
                            for voice_file in voice_files:
                                if os.path.isfile(voice_file):
                                    os.remove(voice_file)
                            logger.info(f"Cleaned up {len(voice_files)} voice file(s) after sending part {i}: {voices_dir}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up voice files: {e}")
                
                # All voices sent successfully
                return True
            else:
                logger.warning("No temp variables found for product_details message type")
                return False
        
    except Exception as e:
        await error_handler(
            f"Error in main_brain_message_processor: {str(e)}",
            "error",
            "high",
            logger
        )
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

#------------------------------------* VALIDATE TEMPLATE DATA *------------------------------------
def validate_template_data(template_data, logger):
    """Validate that template data has all required fields for Facebook API"""
    required_fields = ["title", "image_url", "subtitle", "buttons"]
    for field in required_fields:
        if not template_data.get(field):
            logger.warning(f"Missing required field in template: {field}")
            return False
    return True


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

