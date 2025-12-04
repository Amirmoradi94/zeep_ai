
from pathlib import Path
import openai
import os
import requests
import logging
import asyncio
from dotenv import load_dotenv
from perplexity import Perplexity
from google import genai

# Import our custom functions
from query_to_narration import query_to_narration
from narration_to_voice import narration_to_voice

# Setup logger for test file
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Load environment variables
load_dotenv()

# Get API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


async def generate_voice_from_product_name(product_name: str, location: str = "Iran", user_id: int = None):
    """
    Complete pipeline: Generate voice review from product name.
    
    This function orchestrates the entire workflow:
    1. Takes a product name as input
    2. Generates narration text using AI (with price finding and user feedback)
    3. Splits long text into multiple parts if needed
    4. Converts each narration part to voice file(s)
    
    Args:
        product_name (str): Name of the product to review (e.g., "Samsung Galaxy Buds Pro 2")
        location (str): Market location for price research (default: "Iran")
                       Options: "Iran", "US", "Canada", "UK", etc.
        user_id (int, optional): User ID for organizing output files
    
    Returns:
        list: List of generated voice file paths, or None if error
    
    Example:
        >>> files = generate_voice_from_product_name("Samsung Galaxy Buds Pro 2", "Iran")
        >>> print(files)
        ['./voices/samsung_galaxy_buds_pro_2_part1.mp3', './voices/samsung_galaxy_buds_pro_2_part2.mp3']
    """
    
    print("=" * 80)
    print(f"🎯 GENERATING VOICE REVIEW FOR: {product_name}")
    print(f"📍 Market Location: {location}")
    print("=" * 80)
    
    try:
        
        
        # ======================== STEP 1: GENERATE NARRATION TEXT ========================
        print("\n📚 Step 1: Generating narration text with AI...")
        
        # Extract brand if possible (simple heuristic: first word)
        parts = product_name.strip().split()
        brand = parts[0] if parts else "N/A"
        
        search_query = {
            'product_title': product_name,
            'product_brand': brand
        }
        
        print(f"   ✅ Product: {product_name}")
        print(f"   ✅ Brand: {brand}")
        print(f"   ✅ Location: {location}")
        
        narration_parts = query_to_narration(search_query, location)
        
        if not narration_parts:
            print("❌ Failed to generate narration text")
            return None
        
        print(f"✅ Generated {len(narration_parts)} narration part(s)")
        #for i, part in enumerate(narration_parts, 1):
        #    print(f"      Part {i}: {len(part)} characters (~{len(part) // 15} seconds)")
        
        
        # ======================== STEP 2: CONVERT TO VOICE ========================
        print("\n🎤 Step 2: Converting narration to voice files...")
        
        # Create Gemini client for TTS
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Create safe filename from product name
        safe_filename = product_name.lower().replace(' ', '_').replace('-', '_')
        safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c == '_')
        
        generated_files = []
        
        for i, narration_text in enumerate(narration_parts, 1):
            # Determine filename
            if len(narration_parts) == 1:
                output_filename = safe_filename
            else:
                output_filename = f"{safe_filename}_part{i}"
            
            print(f"\n🔊 Processing Part {i}/{len(narration_parts)}...")
            #print(f"      Text preview: {narration_text[:80]}...")
            
            # Convert to voice
            success = await narration_to_voice(
                narration_text=narration_text,
                gemini_client=gemini_client,
                logger=logger,
                output_filename=output_filename,
                user_id=user_id,
                voice_name="Algieba",  # Default Farsi voice
                temperature=0.15
            )
            
            if success:
                # Construct file path
                if user_id:
                    file_path = f"./voices/{user_id}/{output_filename}.mp3"
                else:
                    file_path = f"./voices/{output_filename}.mp3"
                
                generated_files.append(file_path)
                print(f"      ✅ Voice file generated: {file_path}")
            else:
                print(f"      ❌ Failed to generate voice for Part {i}")
        
        
        # ======================== STEP 3: SUMMARY ========================
        print("\n" + "=" * 80)
        if generated_files:
            print(f"✅ SUCCESS! Generated {len(generated_files)} voice file(s)")
            print("=" * 80)
            print("\n📁 Generated Files:")
            for i, file_path in enumerate(generated_files, 1):
                print(f"   {i}. {file_path}")
            
            print("\n💡 Usage Tips:")
            print("   - Play files in order for complete review")
            print("   - Each part includes natural transitions")
            print("   - Files are ready to send as voice messages")
            
            return generated_files
        else:
            print("❌ FAILED! No voice files were generated")
            print("=" * 80)
            return None
        
    except Exception as e:
        print(f"\n❌ Error in generate_voice_from_product_name: {e}")
        print(f"   Details: {str(e)}")
        return None


# ================================================================================================
# EXAMPLE USAGE
# ================================================================================================

if __name__ == "__main__":
    """
    Example demonstrating the complete workflow from product name to voice files.
    """
    
    async def main():
        print("\n" + "=" * 80)
        print("EXAMPLE: Complete Product Review Voice Generation")
        print("=" * 80)
        
        # Example 1: Generate voice for Samsung Galaxy Buds Pro 2 in Iranian market
        print("\n📱 Example 1: Samsung Galaxy Buds Pro 2")
        print("-" * 80)
        
        voice_files = await generate_voice_from_product_name(
            product_name="Samsung Galaxy Buds Pro 2",
            location="Iran",
            user_id=123456
        )
        
        if voice_files:
            print("\n✅ Success! Voice files are ready.")
        else:
            print("\n❌ Failed to generate voice files.")
        
        
        # Example 2: Generate voice for different product in Iranian market
        print("\n\n📱 Example 2: Dyson Airwrap Multi-styler and Dryer Straight+Wavy in Ceramic Pink")
        print("-" * 80)
        
        voice_files_iran = await generate_voice_from_product_name(
            product_name="Dyson Airwrap Multi-styler and Dryer Straight+Wavy in Ceramic Pink",
            location="Iran",
            user_id=123456
        )
        
        if voice_files_iran:
            print("\n✅ Success! Voice files are ready.")
        
        print("\n" + "=" * 80)
        print("✅ Examples complete!")
        print("=" * 80)
    
    asyncio.run(main())





