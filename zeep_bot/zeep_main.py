from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
from openai import OpenAI
from get_text import get_text
from google import genai as google_genai
from query_to_narration import query_to_narration
from narration_to_voice import narration_to_voice
import uvicorn
from utils import *
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime
from contextlib import asynccontextmanager
import time
from db import (
    get_user_info,
    create_new_user, initialize_database,
    init_db_pool,
    update_user_info, update_feedback_query,
    get_temp_variables, 
    insert_temp_variables,
)

#------------------------------------* CONFIGURE LOGGING *------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

#------------------------------------* REQUEST DEDUPLICATION *------------------------------------
# Simple in-memory cache to prevent duplicate processing
processing_requests = set()
MAX_CACHE_SIZE = 10000  # Maximum number of message IDs to keep in cache

def cleanup_processing_cache():
    """Clean up the processing cache if it gets too large"""
    global processing_requests
    if len(processing_requests) > MAX_CACHE_SIZE:
        # Keep only the most recent 5000 entries (simple approach)
        processing_requests.clear()
        logger.info("Processing cache cleared due to size limit")

#------------------------------------* LOAD ENVIRONMENT VARIABLES *------------------------------------
load_dotenv()

#------------------------------------* LOAD TEXT *------------------------------------
internal_error_text = get_text('internal_error')
general_message_text = get_text('general_message')
post_deleted_text = get_text('post_deleted')
correct_post_format_text = get_text('correct_post_format')
analyzing_post_text = get_text('analyzing_post')
deep_analysis_message_text = get_text('deep_analysis_message')
follow_page_text = get_text('follow_page')
good_feedback_message_text = get_text('GOOD_feedback_message')
bad_feedback_message_text = get_text('BAD_feedback_message')
error_processing_instagram_post_text = get_text('error_processing_instagram_post')
no_narration_generated_text = get_text('no_narration_generated')
no_voice_generated_text = get_text('no_voice_generated')
voice_generated_text = get_text('voice_generated')
ask_user_for_product_brand_text = get_text('ask_user_for_product_brand')
error_posting_frames_text = get_text('error_posting_frames')
error_generating_query_text = get_text('error_generating_query')
restricted_product_message_sent_text = get_text('restricted_product_message_sent')


#------------------------------------* INITIALIZE API CLIENTS *------------------------------------
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_client = google_genai.Client(api_key=gemini_api_key.strip())

#------------------------------------* GET AI CLIENT *------------------------------------
ai_client = None

#------------------------------------* CREATE FASTAPI APP *------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ai_client
    try:
        logger.info("Starting application startup...")
        db_init_success = await initialize_database(logger)  # Initialize database and tables first
        if db_init_success:
            logger.info("Database initialized successfully")
            await init_db_pool()  # Then create the connection pool
        else:
            logger.warning("Database initialization failed, continuing without database")
        
        ai_client = await get_ai_client(openai_client, gemini_client)  # Initialize AI client
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        # Continue anyway - server can still handle requests that don't need DB
    yield

#------------------------------------* CREATE FASTAPI APP *------------------------------------
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

#------------------------------------* VERIFY WEBHOOK *------------------------------------
# GET /webhook for verification
@app.get("/webhook")
async def verify_webhook_get(request: Request):
    query_params = request.query_params
    mode = query_params.get('hub.mode')
    token = query_params.get('hub.verify_token')
    challenge = query_params.get('hub.challenge')

    # Check if the request is not from facebook, ignore it.
    if not mode or not token or not challenge:
        return
    
    logger.info(os.getenv('VERIFY_TOKEN'))
    if mode == "subscribe" and token == os.getenv('VERIFY_TOKEN'):
        # Return challenge as an integer instead of a string to match Facebook's expected format
        if challenge:
            return int(challenge)
        return challenge
    else:
        await error_handler(
            "webhook_verification", 
            "warning", 
            "high",
            logger
        )
        raise HTTPException(status_code=403, detail="Forbidden")

#------------------------------------* HANDLE WEBHOOK EVENTS *------------------------------------
# POST /webhook for event handling
@app.post("/webhook")
async def handle_webhook_post(request: Request):
    verified = await verify_webhook_call(request, logger)
    if not verified:
        return {"status": "unverified"}
    body = await request.json()

    if body.get('object') != 'instagram':
        await error_handler(
            f"Unexpected webhook object: {body.get('object')}",
            "warning",
            "medium",
            logger
        )
        return {"status": "not_instagram"}
    output_message = body['entry'][0]['messaging'][0]

    # Extract user_id first
    user_id = int(output_message['sender']['id'])
    
    # Check for duplicate message using simple message ID cache (StackOverflow approach)
    message_id = output_message.get('message', {}).get('mid') or output_message.get('postback', {}).get('mid')
    
    # Simple in-memory cache for message deduplication
    if message_id and message_id in processing_requests:
        logger.info(f"Message {message_id} from user {user_id} ignored - already processed")
        return {"status": "message_already_processed"}
    
    # Add message ID to processing set
    if message_id:
        processing_requests.add(message_id)
        # Clean up cache if it gets too large
        cleanup_processing_cache()
    
    postback_message = output_message.get('postback', None)
    message_element = output_message.get('message', None)

    # Check if user sent a message within 30 seconds (ignore rapid messages)
    # Postback messages are excluded from cooldown checks
    is_postback = postback_message is not None
    if await is_duplicate_message(message_id):
        #logger.info(f"Message from user {user_id} ignored - sent within 45 second cooldown period")
        return {"status": "message_ignored_cooldown"}

    # Message Handling
    if message_element:
        if 'is_echo' in message_element:
            return {"status": "echo_ignored"}
        
    # Check if user is following
    is_user_following = await is_following(user_id, logger)
    
    # Get user info
    user_info = await get_user_info(user_id, ['user_id', 'location'], logger)
    if not user_info:
        user_created = await create_new_user(
            user_id, 
            logger,
            is_following=is_user_following, 
            location='iran', 
            reels_search_count=0,
            images_search_count=0,
            created_at=datetime.now(), 
            updated_at=datetime.now()
        )
        #logger.info("now created new user")
        if not user_created:
            await send_message_to_user(internal_error_text, user_id, logger)
            return {"status": "error_creating_user"}
        # Get location after creating user
        user_info = await get_user_info(user_id, ['user_id', 'location'], logger)
    
    # Get location from user info, default to 'iran' if not set
    location = user_info.get('location', 'iran') if user_info else 'iran'

    # Message Handling
    if message_element:
        logger.info("now in message_element")

        attachments = message_element.get('attachments', [])
        #logger.info(f"attachments: {attachments}")
        if attachments:
            #### *********** CLEAN MEMORY AND TEMP VARIABLES BEFORE NEW ATTACHMENT *********** ####
            await clean_memory_and_temp_variables(user_id, logger)
            #### *********** ---------------------- *********** ####

            attachment_payload = attachments[0].get('payload', None)
            attachment_type = attachments[0].get('type')
            if attachment_payload:
                attachment_url = attachment_payload.get('url')
                #logger.info(f"attachment_url: {attachment_url}")
                reel_caption = attachment_payload.get('title') if attachment_type == 'ig_reel' else None
                temp_variables_inserted = await insert_temp_variables(user_id, logger, post_url=attachment_url, post_type=attachment_type, reel_caption=reel_caption)
            else:
                await send_message_to_user(internal_error_text, user_id, logger)
                return {"status": "error_inserting_temp_variables"}
        
        # Natural language message handling
        else:
            user_message = message_element.get('text')
            if user_message:
                success = await main_brain_message_processor(user_id, user_message, ai_client, location, logger)
                if not success:
                    await send_message_to_user(internal_error_text, user_id, logger)
                    return {"status": "error_processing_message"}
                
                return {"status": "user_message_processed"}
            else:
                await send_message_to_user(general_message_text, user_id, logger)
                return {"status": "general_message"}

        # Handle post deleted by user
        if message_element.get('is_deleted', False):
            await send_message_to_user(post_deleted_text, user_id, logger)
            return {"status": "post_deleted"}
        
        # If user is not following, send follow postback message
        if not is_user_following:
            await send_message_to_user(follow_page_text, user_id, logger)
            await send_follow_postback_message(user_id, logger)
            return {"status": "follow_page"}
        
        # User is following but the attachment is not an image, reel or share
        if attachment_type not in ['ig_reel', 'share', 'image']:
            await send_message_to_user(correct_post_format_text, user_id, logger)
            return {"status": "correct_post_format"}
        
        # User is following and the attachment is an image, reel or share
        await send_message_to_user(analyzing_post_text, user_id, logger)
        logger.info("now processing instagram post")
        processing_result = await process_instagram_post(attachment_url, reel_caption, user_id, ai_client, attachment_type, location, logger)
        if type(processing_result) == str:
            if processing_result != 'voice_generated':
                await send_message_to_user(get_text(processing_result), user_id, logger)
                return {"status": processing_result}
        elif type(processing_result) == tuple:
            list_product_names, query_ids, list_product_brands, list_product_titles = processing_result
            await send_select_product_postback_message(user_id, list_product_names, query_ids, list_product_brands, list_product_titles, logger)
            return {"status": "select_product_postback_message_sent"}
        
        # User's reel or image contains only one product
        if processing_result == 'voice_generated':
            await send_message_to_user(True, user_id, logger)
            return {"status": "voice_generated"}

    #------------------------------------* Postbacks Handling *------------------------------------   
    elif postback_message:
        payload = postback_message.get('payload')
        
        # Handle feedback postbacks
        if payload.startswith("FEEDBACK_"):
            parts = payload.split("_")
            if len(parts) >= 3:
                feedback_type = parts[1].lower()
                query_id = int(parts[2])
                
                # Update feedback in database
                await update_feedback_query(query_id, feedback_type, logger)
                
                # Send thank you message
                if feedback_type == "good":
                    await send_message_to_user(good_feedback_message_text, user_id, logger)
                elif feedback_type == "bad":
                    await send_message_to_user(bad_feedback_message_text, user_id, logger)
            return {"status": "feedback_handled"}
                
        # Handle confirm follow postback
        elif payload == "CONFIRM_FOLLOW_POSTBACK":
            if is_user_following:
                await update_user_info(user_id, logger, is_following=True)
            else:
                await send_message_to_user(follow_page_text, user_id, logger)
                await send_follow_postback_message(user_id, logger)
                return {"status": "follow_page"}

        # User selected a product in postback
        elif 'SELECT_PRODUCT_' in payload:
            # Extract query_id, product name and brand from postback payload
            parts = payload.replace('SELECT_PRODUCT_', '').split('_')
            
            if len(parts) < 3:
                logger.error(f"Invalid postback payload format: {payload}")
                await send_message_to_user(internal_error_text, user_id, logger)
                return {"status": "error_processing_instagram_post"}
                
            query_id = int(parts[0])
            product_name = parts[1].replace('_', ' ')
            product_brand = parts[2].replace('_', ' ')

            if product_brand == 'N/A':
                await send_message_to_user(ask_user_for_product_brand_text, user_id, logger)
                return {"status": "ask_user_for_product_brand"}

            # Send deep analysis message to user immediately
            await send_message_to_user(deep_analysis_message_text, user_id, logger)

            product_info = {
                'product_title': product_name,
                'product_brand': product_brand
            }
            generated_narration = query_to_narration(product_info, location, logger)
            if not generated_narration:
                await send_message_to_user(no_narration_generated_text, user_id, logger)
                return {"status": "no_narration_generated"}

            # Send message to user that research is done and voice is being generated
            research_complete_message = "تحقیقم رو انجام دادم و الان بهت ویس میدم 🎤"
            await send_message_to_user(research_complete_message, user_id, logger)

            for narration_text in generated_narration:
                voice_success = await narration_to_voice(
                    narration_text=narration_text, 
                    gemini_client=ai_client['client'],
                    logger=logger,
                    user_id=user_id
                )
                if not voice_success:
                    await send_message_to_user(no_voice_generated_text, user_id, logger)
                    return {"status": "no_voice_generated"}
                
                await send_message_to_user(voice_success, user_id, logger)
                return {"status": "voice_sent_successfully"}

        # Handle stored post processing
        temp_variables = await get_temp_variables(user_id, ['post_url', 'post_type', 'reel_caption'], logger)
        if temp_variables:  # Only proceed if temp_variables exists
            attachment_url = temp_variables.get('post_url')
            attachment_type = temp_variables.get('post_type')
            reel_caption = temp_variables.get('reel_caption')
            
            if attachment_url and attachment_type:
                # User attached an invalid post
                if attachment_type not in ['image', 'share', 'ig_reel']:
                    await send_message_to_user(correct_post_format_text, user_id, logger)
                    return {"status": "correct_post_format"}
                
                # Process the instagram post
                processing_result = await process_instagram_post(attachment_url, reel_caption, user_id, ai_client, attachment_type, location, logger)
                if type(processing_result) == str:
                    if processing_result != 'voice_generated':
                        await send_message_to_user(get_text(processing_result), user_id, logger)
                        return {"status": processing_result}
                elif type(processing_result) == tuple:
                    list_product_names, query_ids, list_product_brands, list_product_titles = processing_result
                    await send_select_product_postback_message(user_id, list_product_names, query_ids, list_product_brands, list_product_titles, logger)
                    return {"status": "select_product_postback_message_sent"}
                
                # User's reel or image contains only one product
                if processing_result == 'voice_generated':
                    await send_message_to_user(True, user_id, logger)
                    return {"status": "voice_generated"}

                else:
                    await send_message_to_user(internal_error_text, user_id, logger)
                    return {"status": "error_processing_instagram_post_in_postback"}

    # Clean up the processing request
    if 'message_id' in locals() and message_id:
        processing_requests.discard(message_id)

    return {"status": "success"}
 
# Run the FastAPI app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 