from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
from openai import OpenAI
from get_text import get_text
from google import genai
import uvicorn
from utils import *
from fastapi.middleware.cors import CORSMiddleware
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from datetime import datetime
from contextlib import asynccontextmanager
import time
from db import (
    get_user_info,
    create_new_user, initialize_database,
    init_db_pool,
    update_user_info, update_feedback_query,
    get_temp_variables, 
    insert_temp_variables, check_db_health,
    periodic_db_health_check, get_additional_products,
    save_temp_products, get_temp_products_batch,
    clean_temp_products, get_max_batch_number,
    get_generated_query, get_active_model, is_saving_training_data
)
from utils import (
    render_products_template,
    handle_more_products_request,
    error_handler,
    is_following,
    send_message_to_user,
    send_follow_postback_message,
    process_instagram_post,
    save_frames_with_query_id,
    clean_memory_and_temp_variables,
    verify_webhook_call,
    main_brain_message_processor,
    send_feedback_postback_message,
    search_and_save_products,
    send_more_products_postback_message,
    is_duplicate_message, 
    get_ai_client
)
import asyncio
import asyncpg

from conversation_manager import get_conversation_history, clear_conversation_history, add_to_conversation_history, conversation_history

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
gemini_client = genai.Client(api_key=gemini_api_key.strip())

#------------------------------------* GET AI CLIENT *------------------------------------
ai_client = None

#------------------------------------* CREATE FASTAPI APP *------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ai_client
    await initialize_database(logger)  # Initialize database and tables first
    await init_db_pool()  # Then create the connection pool
    asyncio.create_task(periodic_db_health_check())
    ai_client = await get_ai_client(openai_client, gemini_client)  # Initialize AI client
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
    if await is_duplicate_message(user_id, message_id, is_postback):
        #logger.info(f"Message from user {user_id} ignored - sent within 45 second cooldown period")
        return {"status": "message_ignored_cooldown"}

    # Message Handling
    if message_element:
        if 'is_echo' in message_element:
            return {"status": "echo_ignored"}
        
    # Check if user is following
    is_user_following = await is_following(user_id, logger)
    
    # Get user info
    user_info = await get_user_info(user_id, ['user_id'], logger)
    if not user_info:
        user_created = await create_new_user(
            user_id, 
            logger,
            is_following=is_user_following, 
            region='iran', 
            reels_search_count=0,
            images_search_count=0,
            created_at=datetime.now(), 
            updated_at=datetime.now()
        )
        #logger.info("now created new user")
        if not user_created:
            await send_message_to_user(internal_error_text, user_id, logger)
            return {"status": "error_creating_user"}

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
                temp_variables_inserted = await insert_temp_variables(user_id, logger, post_url=attachment_url, post_type=attachment_type, reel_caption=reel_caption, initial_query='None')
            else:
                await send_message_to_user(internal_error_text, user_id, logger)
                return {"status": "error_inserting_temp_variables"}
        
        # Natural language message handling
        else:
            user_message = message_element.get('text')
            if user_message:
                success = await main_brain_message_processor(user_id, user_message, ai_client, logger)
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
        processing_result = await process_instagram_post(attachment_url, reel_caption, user_id, ai_client, attachment_type, 'iran', logger)
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
                    #add_to_conversation_history(user_id, "assistant", bad_feedback_message_text)
                    result_of_postback = await send_more_products_postback_message(user_id, query_id, logger)
                    if not result_of_postback:
                        await send_message_to_user(no_more_products_text, user_id, logger)
                        return {"status": "error_sending_more_products_postback_message"}
            return {"status": "feedback_handled"}
                
        # Handle more products postbacks
        elif payload.startswith("SHOW_MORE_PRODUCTS_"):
            parts = payload.split("_")
            if len(parts) >= 3:
                query_id = int(parts[3])
                #logger.info(f"query_id: {query_id}")
                await handle_more_products_request(user_id, query_id, logger)
            return {"status": "more_products_shown"}
            
        elif payload == "NO_MORE_PRODUCTS":
            #await clean_temp_products(user_id, logger)
            await send_message_to_user(no_more_products_text, user_id, logger)
            return {"status": "no_more_products"}

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
            product_brand = parts[-1].replace('_', ' ')

            generated_query = await get_generated_query(user_id, query_id, logger)
            #add_to_conversation_history(user_id, "assistant", f"Generated search query for {product_name}: {generated_query}")
            if generated_query:
                logger.info(f"initial query changed to: {generated_query}")
                await insert_temp_variables(user_id, logger, initial_query=generated_query)

                # Get query from database for the selected product
                top_products = await search_and_save_products(user_id, product_name, product_brand, generated_query, query_id, logger)
            
                if not top_products:
                    await send_message_to_user(no_products_found_text, user_id, logger)
                    return {"status": "no_products_found"}
            
                response = await send_message_to_user(top_products, user_id, logger)
                if response:
                    await send_feedback_postback_message(user_id, query_id, logger)
                    return {"status": "products_sent"}

            return {"status": "product_selection_processed"}

        # Handle stored post processing
        temp_variables = await get_temp_variables(user_id, ['post_url', 'post_type', 'reel_caption'], logger)
        if temp_variables:  # Only proceed if temp_variables exists
            post_url = temp_variables.get('post_url')
            post_type = temp_variables.get('post_type')
            reel_caption = temp_variables.get('reel_caption')
            
            if post_url and post_type:
                # User attached an invalid post
                if post_type not in ['image', 'share', 'ig_reel']:
                    await send_message_to_user(correct_post_format_text, user_id, logger)
                    return {"status": "correct_post_format"}
                
                # Process the instagram post
                top_products, query_id, default_url = await process_instagram_post(post_url, reel_caption, user_id, ai_client, post_type, 'ca', logger)
                # User's selected product is found and now we can send the products
                if top_products:
                    response = await send_message_to_user(top_products, user_id, logger)
                    if response:
                        await send_feedback_postback_message(user_id, query_id, logger)
                        generated_query = await get_generated_query(user_id, query_id, logger)
                        if generated_query:
                            logger.info(f"initial query changed to: {generated_query}")
                            await insert_temp_variables(user_id, logger, initial_query=generated_query)
                    return {"status": "products_sent"}

                elif query_id == 'select_product_postback_message_sent':
                    list_product_names, query_ids, list_product_brands = default_url
                    await send_select_product_postback_message(user_id, list_product_names, query_ids, list_product_brands, logger)
                    if await is_saving_training_data():
                        logger.info(f"now saving frames with query_ids: {query_ids}")
                        await save_frames_with_query_id(user_id, query_ids, logger)
                    return {"status": "select_product_postback_message_sent"}

                elif query_id in ['restricted_product_message_sent', 'no_products_found']:
                    if query_id == 'restricted_product_message_sent':
                        await send_message_to_user(restricted_product_message_sent_text, user_id, logger)
                    elif query_id == 'no_products_found':
                        await send_message_to_user(no_products_found_text, user_id, logger)
                    return {"status": "no_products_found"}
                
                # Error handling for instagram post processing in postback
                else:
                    await send_message_to_user(internal_error_text, user_id, logger)
                    return {"status": "error_processing_instagram_post"}

    # Clean up the processing request
    if 'message_id' in locals() and message_id:
        processing_requests.discard(message_id)

    return {"status": "success"}
 
# Run the FastAPI app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 