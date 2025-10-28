
from perplexity import Perplexity
from openai import OpenAI
import os
from logging import Logger
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root (two levels up from this file)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


def format_narration_with_template(research_data: dict) -> str:
    """
    Format research data into a predefined narration template.
    
    Args:
        research_data (dict): Dictionary containing:
            - product_name: Name of the product
            - intro_statement: Brief introduction
            - positive_features: String of positive features
            - negative_aspects: String of negative aspects
            - competitors: String of competitor names
            - comparison: Comparison statement
            - recommendation: Final recommendation
    
    Returns:
        str: Formatted narration text
    """

    #------------------------------------* NARRATION TEMPLATE *------------------------------------
    NARRATION_TEMPLATE = """
    به نظر میرسه که {product_title} {intro_statement}.

    نکته‌های خوبش اینه که {positive_features}.

    البته {negative_aspects}.

    رقیباش هم مدل هایی مثل {competitors} هستن.

    در مقایسه با اون‌ها، {comparison}.

    {recommendation}.
    """
    try:
        narration = NARRATION_TEMPLATE.format(
            product_title=research_data.get('product_title', 'این محصول'),
            intro_statement=research_data.get('intro_statement', 'یکی از محصولات خوب بازاره'),
            positive_features=research_data.get('positive_features', 'ویژگی‌های خوبی داره'),
            negative_aspects=research_data.get('negative_aspects', 'یه سری نکات منفی هم داره'),
            competitors=research_data.get('competitors', 'محصولات مشابه'),
            comparison=research_data.get('comparison', 'در سطح مناسبیه'),
            recommendation=research_data.get('recommendation', 'می‌تونی بررسی کنی')
        )
        return narration.strip()
    except Exception as e:
        print(f"Error formatting narration: {e}")
        return None


def split_long_narration(narration_text: str, logger: Logger = None) -> list:
    """
    Split long narration text into multiple parts if it exceeds 45 seconds of voice.
    Ensures parts are roughly equal in length to avoid short trailing segments.
    Adds natural transition phrases between parts.
    
    Args:
        narration_text (str): The complete narration text in Farsi
        logger: Logger instance
    
    Returns:
        list: List of text parts with transitions, or single-item list if no split needed
    """
    # Estimate: ~3 words per second in Farsi, average 5 chars per word + spaces
    # 45 seconds ≈ 135 words ≈ 675 characters (being conservative with 600)
    MAX_CHARS_PER_PART = 600
    MIN_CHARS_FOR_LAST_PART = 200  # Minimum 15 seconds for last part
    
    try:
        text_length = len(narration_text)
        
        # If text is short enough, return as single part
        if text_length <= MAX_CHARS_PER_PART:
            print(f"✅ Text length ({text_length} chars) is within 45 seconds limit")
            return [narration_text]
        
        # Calculate optimal number of parts for equal distribution
        # If remainder would be too short, split into more equal parts
        num_parts = text_length // MAX_CHARS_PER_PART
        remainder = text_length % MAX_CHARS_PER_PART
        
        # If remainder is too short, increase number of parts for better distribution
        if remainder > 0 and remainder < MIN_CHARS_FOR_LAST_PART:
            num_parts += 1
        elif remainder >= MIN_CHARS_FOR_LAST_PART:
            num_parts += 1
        
        # Calculate target length per part for equal distribution
        target_chars_per_part = text_length // num_parts
        
        print(f"⚠️ Text is long ({text_length} chars), splitting into {num_parts} equal parts...")
        print(f"📊 Target length per part: ~{target_chars_per_part} chars (~{target_chars_per_part // 15} seconds each)")
        
        # Use OpenAI to intelligently split the text
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        split_prompt = f"""You are a text editor for voice messages in Farsi. Your task is to split the following long text into {num_parts} parts of ROUGHLY EQUAL LENGTH.

IMPORTANT RULES:
1. Split into {num_parts} parts, each approximately {target_chars_per_part} characters
2. Parts should be ROUGHLY EQUAL in length (avoid one long part and one very short part)
3. Split at natural breaking points (between topics, not mid-sentence)
4. Each part should be coherent and make sense on its own
5. Add a natural transition phrase at the END of each part (except the last one)
6. Transition phrases should be conversational and friendly

SUGGESTED TRANSITION PHRASES (use variety):
- "خیلی خب، توضیحاتم رو توی ویس بعدی ادامه میدم"
- "بقیه نکات رو توی ویس بعدی واست میگم"
- "صبر کن، ادامشو توی پیام بعدی میگم"
- "یه لحظه، بذار ادامشو توی ویس بعدی بگم"
- "باقی مطالب رو توی پیام بعدی میشنوی"

TEXT TO SPLIT (Total: {text_length} chars → Target: {num_parts} parts of ~{target_chars_per_part} chars each):
{narration_text}

Return ONLY a JSON array with EXACTLY {num_parts} text parts of roughly equal length. Example format:
["part 1 text... خیلی خب، ادامه توضیحاتم رو توی ویس بعدی ادامه میدم", "part 2 text... بقیه نکات رو توی ویس بعدی براتون میگم", "final part text"]

Return ONLY the JSON array, no other text."""

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful text editor that splits Farsi text intelligently for voice messages."
                },
                {
                    "role": "user",
                    "content": split_prompt
                }
            ]
        )
        
        # Parse the response
        import json
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response if it contains markdown code blocks
        if response_text.startswith('```'):
            content = response_text.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            response_text = content.strip()
        
        # Parse JSON array
        text_parts = json.loads(response_text)
        
        if not isinstance(text_parts, list) or len(text_parts) == 0:
            print("⚠️ Failed to parse split result, returning original text")
            return [narration_text]
        
        print(f"✅ Text split into {len(text_parts)} parts successfully")
        
        # Display character count for each part
        for i, part in enumerate(text_parts, 1):
            part_length = len(part)
            part_seconds = part_length // 15
            print(f"   Part {i}: {part_length} chars (~{part_seconds} seconds)")
        
        if logger:
            logger.info(f"Split narration into {len(text_parts)} parts")
            for i, part in enumerate(text_parts, 1):
                logger.info(f"Part {i} length: {len(part)} chars (~{len(part) // 15} seconds)")
        
        return text_parts
        
    except Exception as e:
        print(f"❌ Error splitting narration: {e}")
        print("⚠️ Returning original text as fallback")
        if logger:
            logger.error(f"Failed to split narration: {e}")
        # Return original text as fallback
        return [narration_text]


def query_to_narration(search_query: dict, location: str, logger: Logger = None):
    """
    Conduct deep product research using Perplexity AI and generate audio review.
    
    Args:
        search_query (dict): Product search query including product_brand, product_title
        location (str): Location for price research (e.g., "Canada", "US")
        logger: Logger instance
    Returns:
        list: List of narration text parts (split if longer than 45 seconds) or None if error
    """
    try:
        product_title = search_query.get('product_title')
        product_brand = search_query.get('product_brand')
        
        # Structured system prompt that returns JSON data for template
        # Determine price search sources based on location
        price_sources = ""
        if location.lower() in ['iran', 'ایران', 'tehran', 'تهران']:
            price_sources = "Iranian e-commerce websites (Digikala, Torob, etc.)"
        else:
            price_sources = f"{location} market retailers and e-commerce platforms"
        
        system_prompt = f"""You are a friendly and knowledgeable product advisor. Your task is to research a product and provide structured data in Farsi for a narration template.

IMPORTANT RESEARCH REQUIREMENTS:
- Find the current price of the product in {location} by searching {price_sources}
- For Iranian market: Check prices on Digikala (دیجی‌کالا), Torob (ترب), and other Iranian e-commerce sites
- For other markets: Search local retailers and e-commerce platforms specific to {location}
- Gather REAL user feedback and reviews from the internet (Reddit, Amazon, YouTube comments, tech forums, Persian forums for Iranian products, etc.)
- Compare prices with competitor products in the same market
- Base your analysis on actual user experiences, not just specifications

RESPONSE FORMAT - Return ONLY a JSON object with these exact keys:
{{
    "product_title": "نام محصول",
    "intro_statement": "یک جمله معرفی کوتاه و دوستانه",
    "positive_features": "ویژگی مثبت اول، ویژگی مثبت دوم، و ویژگی مثبت سوم",
    "negative_aspects": "نکته منفی اول و نکته منفی دوم",
    "competitors": "رقیب اول، رقیب دوم، و رقیب سوم",
    "comparison": "جمله مقایسه با رقیبا",
    "recommendation": "توصیه نهایی"
}}

CONTENT GUIDELINES:

1. intro_statement: 
   - One friendly sentence about the product
   - Mention price if found for {location}
   - For Iran: Use Toman or million Toman (e.g., "حدود ۵ میلیون تومن")
   - For other markets: Use local currency (USD, CAD, etc.)
   - Examples: "یکی از بهترین انتخاب‌هاست توی بازار با قیمت حدود ۵ میلیون تومن"

2. positive_features:
   - List 3 specific positive features separated by "،"
   - Use conversational style
   - Base features on REAL user feedback and reviews from the internet
   - Example: "باتریش خیلی خوبه، کیفیت ساختش عالیه، و قیمتش مناسبه"

3. negative_aspects:
   - List 2 concerns or weaknesses with "و" between them
   - Be honest but constructive
   - Base on REAL user complaints and negative feedback from actual reviews
   - Example: "یه کم سنگینه و گاهی گرم میشه"

4. competitors:
   - Name 3 real competitor products separated by "،" and "و"
   - Use actual product names in similar price range for {location}
   - Example: "Samsung Galaxy Buds، Sony WF-1000XM5، و Apple AirPods Pro"

5. comparison:
   - One sentence comparing with competitors
   - MUST include price comparison based on {location} market prices from sources mentioned above
   - Consider both features and price
   - For Iran: Mention prices from Digikala/Torob in Toman
   - Examples: "نسبت به رقیباش قیمتش یک میلیون تومن کمتره ولی باتریش کمتره" (Iran), "نسبت به رقیباش قیمتش ۱۰۰ دلار کمتره" (US/Canada)

6. recommendation:
   - Final friendly recommendation in one sentence
   - Consider price-to-value ratio based on {location} pricing
   - Examples: "می‌تونم بگم که ارزش خرید داره", "اگه بودجه‌ت محدوده، گزینه خوبیه"

LANGUAGE STYLE:
- Use conversational Farsi like talking to a friend
- Be specific and helpful
- Keep each section concise (total ~150-200 words)
- Make it natural for voice narration
- Ground your analysis in real user experiences and feedback from the internet

Return ONLY the JSON object, no additional text."""

        # Create Perplexity client
        client = Perplexity(api_key=PERPLEXITY_API_KEY)
        
        # Construct query
        query_text = f"product title: {product_title}"
        if product_brand and product_brand != 'N/A':
            query_text += f", brand: {product_brand}"
        
        # Create chat completion
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"Research and provide structured review data for: {query_text}"
                }
            ],
            model="sonar-pro"
        )
        
        # Extract and parse response
        response_text = completion.choices[0].message.content
        
        # Clean up response if it contains markdown code blocks
        import json
        import re
        
        response_text = response_text.strip()
        if response_text.startswith('```'):
            content = response_text.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            response_text = content.strip()
        
        # Parse JSON
        research_data = json.loads(response_text)
        
        # Format using template
        narration_text = format_narration_with_template(research_data)
        
        if narration_text:
            print("✅ Product research completed successfully")
            print(f"📄 Narration text length: {len(narration_text)} characters")
            if logger:
                logger.info(f"Generated narration: {narration_text[:100]}...")
            
            # Split long narration if needed
            narration_parts = split_long_narration(narration_text, logger)
            
            return narration_parts
        else:
            print("❌ Failed to format narration")
            return None
            
    except Exception as e:
        print(f"❌ Error in deep product research: {e}")
        print(f"Error details: {str(e)}")
        return None


# ================================================================================================
# EXAMPLE USAGE
# ================================================================================================

if __name__ == "__main__":
    """
    Example demonstrating how to use query_to_narration function.
    This example shows:
    1. Basic usage with product search
    2. Handling returned list of text parts
    3. Processing multiple voice segments if text is split
    """
    
    # Example 1: Generate product review
    print("\n📱 Example 1: Generating review for Samsung Galaxy Buds")
    print("-" * 80)
    
    search_query = {
        'product_title': 'Samsung Galaxy Buds Pro 2',
        'product_brand': 'Samsung'
    }
    
    location = "Iran"  # Can be "Canada", "US", or other locations
    
    # Call the main function
    narration_parts = query_to_narration(search_query, location)
    
    if narration_parts:
        print(f"\n✅ Successfully generated {len(narration_parts)} voice part(s)")
        print("\n" + "=" * 80)
        
        # Display each part
        for i, part in enumerate(narration_parts, 1):
            print(f"\n🎤 VOICE MESSAGE {i}:")
            print("-" * 80)
            print(part)
            print(f"\n📊 Length: {len(part)} characters (~{len(part) // 15} seconds)")
            print("-" * 80)
        
        print("\n💡 Usage Tips:")
        print("   - Each part is designed for ~45 seconds of voice narration")
        print("   - Parts include natural transition phrases to maintain flow")
        print("   - Send each part as a separate voice message in sequence")
        
    else:
        print("❌ Failed to generate narration")

