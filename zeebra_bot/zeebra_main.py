from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv
from openai import OpenAI
from get_text import get_text
from google import genai
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
    insert_temp_variables, check_db_health,
    periodic_db_health_check,
    get_generated_query
)

import asyncio

#------------------------------------* REQUEST DEDUPLICATION *------------------------------------
# Simple in-memory cache to prevent duplicate processing
processing_requests = set()

#------------------------------------* LOAD ENVIRONMENT VARIABLES *------------------------------------
load_dotenv()

#------------------------------------* LOAD TEXT *------------------------------------
internal_error_text = get_text('internal_error')
general_message_text = get_text('general_message')
no_detailed_search_result_text = get_text('no_detailed_search_result')
post_deleted_text = get_text('post_deleted')
correct_post_format_text = get_text('correct_post_format')
searching_messages_text = get_text('searching_messages')
follow_page_text = get_text('follow_page')
good_feedback_message_text = get_text('GOOD_feedback_message')
bad_feedback_message_text = get_text('BAD_feedback_message')
restricted_product_message_sent_text = get_text('restricted_product_message_sent')
ask_user_for_product_model_text = get_text('ask_user_for_product_model')

#------------------------------------* INITIALIZE API CLIENTS *------------------------------------
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key.strip())
gemini_client = genai.GenerativeModel('gemini-2.5-flash')

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

#------------------------------------* CHECK DATABASE HEALTH *------------------------------------
@app.get("/health/db")
async def db_health_check():
    is_healthy = await check_db_health()
    if is_healthy:
        return {"status": "healthy"}
    else:
        raise HTTPException(status_code=503, detail="Database unavailable")



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

    # Check for duplicate message
    message_id = output_message.get('message', {}).get('mid') or output_message.get('postback', {}).get('mid')
    if message_id and await is_duplicate_message(message_id):
        return {"status": "duplicate_ignored"}
    
    # Check for duplicate processing request
    request_key = f"{user_id}_{message_id}_{int(time.time())}"
    if request_key in processing_requests:
        logger.info(f"Duplicate processing request detected: {request_key}")
        return {"status": "duplicate_processing_ignored"}
    processing_requests.add(request_key)

    postback_message = output_message.get('postback', None)
    message_element = output_message.get('message', None)
    user_id = int(output_message['sender']['id'])

    # Initialize conversation history if it doesn't exist
    #get_conversation_history(user_id)

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
            region='ca', 
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
                
                # Log conversation history after processing to see the updated state
                #conversation_history = get_conversation_history(user_id)
                #logger.info(f"conversation_history after main brain message processor: {conversation_history}")
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
        await send_message_to_user(searching_messages_text, user_id, logger)
        detailed_search_result, query_id, default_url = await process_instagram_post(attachment_url, reel_caption, user_id, ai_client, attachment_type, 'ca', logger)
        
        # User's reel or image contains only one product
        if detailed_search_result:
            #------------------------------------* CONVERT DEEP SEARCH RESULT TO VOICE *------------------------------------
            voice_message = await convert_deep_search_result_to_voice(detailed_search_result, user_id, logger)
            if not voice_message:
                await send_message_to_user(internal_error_text, user_id, logger)
                return {"status": "error_converting_deep_search_result_to_voice"}
            
            #------------------------------------* SEND VOICE MESSAGE *------------------------------------
            response = await send_message_to_user(voice_message, user_id, logger)
            if response:
                await send_feedback_postback_message(user_id, query_id, logger)
                generated_query = await get_generated_query(user_id, query_id, logger)
                if generated_query:
                    await insert_temp_variables(user_id, logger, initial_query=generated_query)
                return {"status": "products_sent"}
            
        # User sent a reel that contains multiple products
        elif query_id == 'select_product_postback_message_sent':
            list_product_names, query_ids, list_product_brands, list_product_models = default_url
            await send_select_product_postback_message(user_id, list_product_names, query_ids, list_product_brands, list_product_models, logger)
            return {"status": "select_product_postback_message_sent"}
        
        # Error handling for instagram post processing
        elif query_id in ['restricted_product_message_sent', 'no_detailed_search_result']:
            if query_id == 'restricted_product_message_sent':
                await send_message_to_user(restricted_product_message_sent_text, user_id, logger)
            elif query_id == 'no_detailed_search_result':
                await send_message_to_user(no_detailed_search_result_text, user_id, logger)
            return {"status": query_id}
        else:
            await send_message_to_user(internal_error_text, user_id, logger)
            return {"status": "error_processing_instagram_post"}

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
            product_model = parts[3].replace('_', ' ')

            if product_model == 'N/A':
                await send_message_to_user(ask_user_for_product_model_text, user_id, logger)
                return {"status": "ask_user_for_product_model"}

            generated_query = await get_generated_query(user_id, query_id, logger)
            if generated_query:
                logger.info(f"initial query changed to: {generated_query}")
                await insert_temp_variables(user_id, logger, initial_query=generated_query)

                # Get query from database for the selected product
                voice_message = await search_and_create_voice_message(user_id, product_name, product_brand, product_model, generated_query, query_id, logger)
            
                response = await send_message_to_user(voice_message, user_id, logger)
                if response:
                    await send_feedback_postback_message(user_id, query_id, logger)
                    return {"status": "products_sent"}

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
                detailed_search_result, query_id, default_url = await process_instagram_post(post_url, reel_caption, user_id, ai_client, post_type, 'ca', logger)
                # User's selected product is found and now we can send the products
                if detailed_search_result:
                    #------------------------------------* CONVERT DEEP SEARCH RESULT TO VOICE *------------------------------------
                    voice_message = await convert_deep_search_result_to_voice(detailed_search_result, user_id, logger)
                    if not voice_message:
                        await send_message_to_user(internal_error_text, user_id, logger)
                        return {"status": "error_converting_deep_search_result_to_voice"}
                    
                    response = await send_message_to_user(voice_message, user_id, logger)
                    if response:
                        await send_feedback_postback_message(user_id, query_id, logger)
                        generated_query = await get_generated_query(user_id, query_id, logger)
                        if generated_query:
                            logger.info(f"initial query changed to: {generated_query}")
                            await insert_temp_variables(user_id, logger, initial_query=generated_query)
                    return {"status": "products_sent"}

                elif query_id == 'select_product_postback_message_sent':
                    list_product_names, query_ids, list_product_brands, list_product_models = default_url
                    await send_select_product_postback_message(user_id, list_product_names, query_ids, list_product_brands, list_product_models, logger)
                    return {"status": "select_product_postback_message_sent"}

                elif query_id in ['restricted_product_message_sent', 'no_detailed_search_result']:
                    if query_id == 'restricted_product_message_sent':
                        await send_message_to_user(restricted_product_message_sent_text, user_id, logger)
                    elif query_id == 'no_detailed_search_result':
                        await send_message_to_user(no_detailed_search_result_text, user_id, logger)
                    return {"status": "no_detailed_search_result"}
                
                # Error handling for instagram post processing in postback
                else:
                    await send_message_to_user(internal_error_text, user_id, logger)
                    return {"status": "error_processing_instagram_post"}

    return {"status": "success"}
 
# Run the FastAPI app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 