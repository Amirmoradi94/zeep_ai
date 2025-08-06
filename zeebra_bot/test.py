
from pathlib import Path
import openai
import os
import requests
from dotenv import load_dotenv

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


def deep_product_research(search_query):
    """
    Conduct deep product research using Perplexity AI and generate audio review.
    
    Args:
        search_query (str): Product search query including name, brand, features, and user aspects
    
    Returns:
        str: Research text
    """
    try:
        # Perplexity AI API configuration
        url = "https://api.perplexity.ai/chat/completions"
        
        # Friendly and conversational system prompt for product review
        system_prompt = """You are a friendly and knowledgeable product advisor who helps people make informed buying decisions. Your task is to provide helpful, conversational advice about products in Farsi language.

                        WRITING STYLE:
                        - Use friendly, conversational tone like talking to a friend
                        - Start sentences with phrases like "به نظر میرسه که", "یکی از بهترین هاست", "می‌تونم بگم که"
                        - Use casual, approachable language while staying informative
                        - Write as if you're giving personal advice to someone you care about

                        CONTENT STRUCTURE:
                        - Begin with a friendly introduction about the product
                        - Share what you think about it in a conversational way
                        - Mention the good things (pros) in a positive, encouraging tone
                        - Honestly mention any concerns (cons) in a helpful way
                        - Give a friendly recommendation or suggestion

                        LANGUAGE REQUIREMENTS:
                        - Write entirely in Farsi/Persian
                        - Use everyday, conversational Farsi
                        - Avoid overly technical jargon unless necessary
                        - Make it sound natural and friendly

                        TONE EXAMPLES:
                        - "به نظر میرسه که این محصول واقعاً خوبه"
                        - "یکی از بهترین انتخاب‌هاست توی این رنج قیمت"
                        - "می‌تونم بگم که ارزش خرید داره"
                        - "البته یه کم مشکل هم داره ولی در کل خوبه"

                        OUTPUT REQUIREMENTS:
                        - WRITE **150-200 words** in friendly, conversational Farsi
                        - Focus on helping the user make a decision
                        - Be honest but encouraging
                        - Structure for 30-second audio narration
                        - Make it sound like friendly advice from a knowledgeable friend

                        Remember: You're not a formal reviewer, you're a helpful friend giving advice about a product!"""

        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"Please provide a comprehensive technical review for: {search_query}"
                }
            ],
            "max_tokens": 300
        }

        perplexity_api_key = os.getenv('PERPELEXITY_API_KEY')
        if not perplexity_api_key:
            print("❌ Error: PERPLEXITY_API_KEY environment variable not set")
            return None
        
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        # Make API request to Perplexity
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            research_text = result['choices'][0]['message']['content']
            
            print("✅ Product research completed successfully")
            #print(f"Research text: {research_text}")
            
            return research_text

        else:
            print(f"❌ Perplexity API error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error in deep product research: {e}")
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




