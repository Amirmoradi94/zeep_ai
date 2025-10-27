import os
import asyncio
import aiohttp
import aiofiles
from utils import is_valid_url
from pathlib import Path
import shutil


#------------------------------------* CONSTANTS *------------------------------------
FRAMES_PATH = "./frames"
VIDEOS_PATH = "./videos"

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
            return False
        except Exception as e:
            logger.error(f"Unexpected error in download_reel: {e}, type: {type(e)}")
            return False
    except Exception as e:
        logger.error(f"Outer exception in download_reel: {e}, type: {type(e)}")
        return False
        
#------------------------------------* DOWNLOAD IMAGE *------------------------------------
async def download_image(image_url, user_id, logger):
    """
    Download an image from a URL and save it to the frames directory.
    
    Args:
        image_url (str): URL of the image to download
        user_id (str/int): User ID for organizing files
        logger: Logger instance
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not await is_valid_url(image_url, logger):
            logger.error(f"Invalid image URL: {image_url}")
            return False

        # Save directly to frames path as a single frame
        frames_dir = f"{FRAMES_PATH}/{user_id}/"
        os.makedirs(frames_dir, exist_ok=True)
        save_path = f"{frames_dir}frame_0001.jpg"
        
        for attempt in range(3):  # Retry up to 3 times
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            async with aiofiles.open(save_path, 'wb') as file:
                                content = await response.read()
                                await file.write(content)
                            logger.info(f"Successfully downloaded image to: {save_path}")
                            return True
                        else:
                            logger.error(f"HTTP error downloading image: {response.status}")
                            return False
            except aiohttp.ClientError as e:
                logger.error(f"Client error downloading image (attempt {attempt + 1}/3): {e}")
                if attempt < 2:  # If it's not the last attempt
                    await asyncio.sleep(5)  # Wait for 5 seconds before retrying
                else:
                    return False
            except Exception as e:
                logger.error(f"Unexpected error downloading image: {e}")
                return False
        return False
    except Exception as e:
        logger.error(f"Outer exception in download_image: {e}")
        return False


#------------------------------------* EXTRACT KEY FRAMES *------------------------------------
async def extract_keyframes(reel_path: str, user_id: int, logger):
    """
    Extract keyframes from a video file using FFmpeg.
    
    Args:
        reel_path (str): Path to the video file
        user_id (int): User ID for organizing frames
        logger: Logger instance
    
    Returns:
        bool: True if successful and frames were extracted, False otherwise
    """
    try:
        frames_path = f"{FRAMES_PATH}/{user_id}/"
        os.makedirs(frames_path, exist_ok=True)
        
        # Check if reel file exists
        if not os.path.exists(reel_path):
            logger.error(f"Reel file not found: {reel_path}")
            return False

        cmd = [
            "ffmpeg", "-i", reel_path, "-vf", "select='eq(pict_type,PICT_TYPE_I)'",
            "-vsync", "vfr", f"{frames_path}frame_%04d.jpg"
        ]
        
        logger.info(f"Extracting keyframes from: {reel_path}")
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            return False
        
        # Check if frames were extracted
        if os.path.exists(frames_path) and os.listdir(frames_path):
            frame_count = len(os.listdir(frames_path))
            logger.info(f"Successfully extracted {frame_count} keyframes")
            return True
        else:
            logger.error("No frames were extracted")
            return False
            
    except Exception as e:
        logger.error(f"Error extracting keyframes: {e}")
        return False

#------------------------------------* POST TO FRAMES (MAIN FUNCTION) *------------------------------------
async def post_to_frames(post_url: str, user_id: int, post_type: str = None, logger = None):
    """
    Main function to process a post URL and extract frames.
    Handles both images and videos (reels).
    
    Args:
        post_url (str): URL of the post (image or video)
        user_id (int): User ID for organizing files
        post_type (str): Type of post ('image' or 'video')
        logger: Logger instance
    
    Returns:
        dict: {
            'success': bool,
            'type': str ('image' or 'video'),
            'frames_path': str (path to frames directory),
            'frame_count': int (number of frames extracted),
            'message': str (status message)
        }
    """
    try:
        logger.info(f"Processing post URL for user {user_id}: {post_url}")
        
        # Validate URL
        if not await is_valid_url(post_url, logger):
            return False
        
        # Clean up existing frames for this user
        frames_dir = f"{FRAMES_PATH}/{user_id}/"
        if os.path.exists(frames_dir):
            logger.info(f"Cleaning up existing frames directory: {frames_dir}")
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)
        
        # Process based on post type
        if post_type == 'image':
            logger.info("Processing as image post")
            success = await download_image(post_url, user_id, logger)
            
            if not success:
                return False
            return True
        
        elif post_type == 'video':
            success = await download_reel(post_url, reel_path, logger)
            if not success:
                return False
            
            # Extract keyframes
            extraction_success = await extract_keyframes(reel_path, user_id, logger)
            
            if not extraction_success:
                return False
            return True
        
        else:
            logger.error(f"Unknown post type: {post_type}")
            return False
    
    except Exception as e:
        logger.error(f"Error in post_to_frames: {e}")
        return False


