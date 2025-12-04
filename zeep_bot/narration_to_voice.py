import base64
import mimetypes
import os
import re
import random
import shutil
import struct
from google import genai
from google.genai import types
from pathlib import Path
from logging import Logger

from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


#------------------------------------* CONSTANTS *------------------------------------
VOICES_PATH = "./voices"

# Available speaker names for random selection
AVAILABLE_SPEAKERS = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir",
    "Leda", "Orus", "Aoede", "Callirrhoe", "Autonoe",
    "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina",
    "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird",
    "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
]


#------------------------------------* HELPER FUNCTIONS *------------------------------------
async def save_binary_file(file_name, data):
    """Save binary data to a file."""
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"File saved to: {file_name}")


async def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """
    Generates a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.
    """
    parameters = await parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data


async def parse_audio_mime_type(mime_type: str) -> dict:
    """
    Parses bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys.
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass  # Keep rate as default
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass  # Keep bits_per_sample as default

    return {"bits_per_sample": bits_per_sample, "rate": rate}


#------------------------------------* MAIN FUNCTION *------------------------------------
async def narration_to_voice(
    narration_text: str,
    gemini_client,
    logger: Logger,
    output_filename: str = None,
    user_id: int = None,
    voice_name: str = None,
    temperature: float = 0.15
):
    """
    Convert narration text to voice using Gemini TTS API.
    
    Args:
        narration_text (str): The text to convert to speech
        gemini_client: Gemini client instance (genai.Client)
        output_filename (str, optional): Custom output filename (without extension)
        user_id (int, optional): User ID for organizing files
        voice_name (str, optional): Voice to use. If None, a random voice will be selected
        temperature (float): Temperature for generation (default: 0.15)
        logger (Logger): Logger instance
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Starting voice generation for text length: {len(narration_text)}")
        
        # Validate input
        if not narration_text or not narration_text.strip():
            error_msg = "Narration text is empty"
            logger.error(error_msg)
            return False
        
        if not gemini_client:
            error_msg = "Gemini client is required"
            logger.error(error_msg)
            return False
        
        # Select random voice if not specified
        if voice_name is None:
            voice_name = random.choice(AVAILABLE_SPEAKERS)
            logger.info(f"Randomly selected voice: {voice_name}")

        
        # Create voices directory
        if user_id:
            voices_dir = f"{VOICES_PATH}/{user_id}/"
        else:
            voices_dir = f"{VOICES_PATH}/"
        
        # Clean up existing voices for this user
        if os.path.exists(voices_dir):
            logger.info(f"Cleaning up existing voices directory: {voices_dir}")
            shutil.rmtree(voices_dir)
        
        os.makedirs(voices_dir, exist_ok=True)
        
        # Generate output filename
        if output_filename is None:
            import time
            timestamp = int(time.time())
            output_filename = f"narration_{timestamp}"
        
        # Remove extension if provided
        output_filename = output_filename.replace('.wav', '').replace('.mp3', '')
        
        # Prepare content with speaking style instruction
        styled_text = f"[Speak quickly and energetically] {narration_text}"
        model = "gemini-2.5-flash-preview-tts"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=styled_text),
                ],
            ),
        ]
        
        # Configure generation
        generate_content_config = types.GenerateContentConfig(
            temperature=temperature,
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )
        
        logger.info(f"Generating audio with voice: {voice_name}")
        
        # Generate audio
        file_index = 0
        generated_files = []
        
        for chunk in gemini_client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if (
                chunk.candidates is None
                or chunk.candidates[0].content is None
                or chunk.candidates[0].content.parts is None
            ):
                continue
            
            if (chunk.candidates[0].content.parts[0].inline_data and 
                chunk.candidates[0].content.parts[0].inline_data.data):
                
                file_name = f"{output_filename}_{file_index}" if file_index > 0 else output_filename
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                data_buffer = inline_data.data
                
                # Determine file extension
                file_extension = mimetypes.guess_extension(inline_data.mime_type)
                if file_extension is None:
                    file_extension = ".wav"
                    data_buffer = await convert_to_wav(inline_data.data, inline_data.mime_type)
                
                # Save file
                file_path = os.path.join(voices_dir, f"{file_name}{file_extension}")
                await save_binary_file(file_path, data_buffer)
                generated_files.append(file_path)
                file_index += 1
            else:
                if chunk.text:
                    logger.info(f"Chunk text: {chunk.text}")
        
        # Return result
        if generated_files:
            main_file = generated_files[0]
            file_size = os.path.getsize(main_file)
            
            success_msg = f"Successfully generated {len(generated_files)} audio file(s)"
            logger.info(success_msg)
            logger.info(f"Main file: {main_file} ({file_size} bytes)")
            
            return True
        else:
            error_msg = "No audio files were generated"
            logger.error(error_msg)
            return False
    
    except Exception as e:
        error_msg = f"Error generating voice: {str(e)}"
        logger.error(error_msg)
        
        return False