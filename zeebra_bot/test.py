
from pathlib import Path
import openai
import os
import requests
from dotenv import load_dotenv
from perplexity import Perplexity

load_dotenv()



def generate_voice_from_text(text_input, output_filename="speech.mp3", voice="alloy"):
    """
    Generate audio file from text input using OpenAI TTS API.
    
    Args:
        text_input (str): The text to convert to speech
        output_filename (str): Name of the output audio file (default: "speech.mp3")
        voice (str): Voice to use for speech generation (default: "alloy")
    
    Returns:
        str: Path to the generated audio file
    """
    try:
        # Check if text input is valid
        if not text_input or not text_input.strip():
            print("❌ Error: Text input is empty or invalid")
            return None
        
        # Get the directory of the current file
        current_dir = Path(__file__).parent
        speech_file_path = current_dir / output_filename
        
        # Ensure the filename has .mp3 extension
        if not output_filename.lower().endswith('.mp3'):
            speech_file_path = speech_file_path.with_suffix('.mp3')
        
        print(f"🎵 Generating audio file: {speech_file_path}")
        
        # Create OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ Error: OPENAI_API_KEY environment variable not set")
            return None
            
        client = openai.OpenAI(api_key=api_key)

        # Instructions for Farsi technical product review audio generation
        instructions = """Affect: Professional, knowledgeable, and authoritative, with a warm and engaging quality that reflects expertise in technical product analysis.

        Tone: Educational, analytical, and trustworthy, capturing the essence of expert technical review while maintaining accessibility for diverse audiences.

        Emotion: Confidence, enthusiasm for quality products, and balanced objectivity when discussing both strengths and areas for improvement.

        Pronunciation: Clear, deliberate, and with appropriate technical terminology emphasis. Product names, specifications, and technical terms should be pronounced with precision and clarity.

        Pause: Strategic pauses after introducing key product features, before revealing important findings, and between different review sections to allow listeners to process technical information effectively.

        Language Style: Use Farsi language with appropriate technical terminology, maintaining formal yet approachable tone suitable for product reviews."""
        
        # Generate speech with streaming response
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text_input,
            instructions=instructions
        ) as response:
            response.stream_to_file(speech_file_path)
        
        # Verify file was created and has content
        if speech_file_path.exists() and speech_file_path.stat().st_size > 0:
            print(f"✅ Audio file generated successfully: {speech_file_path}")
            print(f"📁 File size: {speech_file_path.stat().st_size} bytes")
            return str(speech_file_path)
        else:
            print("❌ Error: Audio file was not created or is empty")
            return None
        
    except Exception as e:
        print(f"❌ Error generating audio: {e}")
        return None



    

if __name__ == "__main__":
    print("=== Product Research and Voice Generation ===")
    
    # Example search query
    search_query = "samsung galaxy buds 2 pro. noise cancellation is very important for me. i want to buy it."
    
    print(f"🔍 Researching: {search_query}")
    
    # Get research text
    research_text = deep_product_research(search_query)
    
    if research_text:
        print("\n📝 Research completed. Generating voice...")
        
        # Generate voice file with a descriptive filename
        audio_file_path = generate_voice_from_text(
            text_input=research_text,
            output_filename="samsung_galaxy_buds_review.mp3",
            voice="alloy"
        )
        
        if audio_file_path:
            print(f"\n🎉 Success! Audio file saved at: {audio_file_path}")
            print(f"📄 Research text length: {len(research_text)} characters")
        else:
            print("\n❌ Failed to generate audio file")
    else:
        print("\n❌ Failed to get research text")
    
    print("\n=== Process Complete ===")




