
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


# ============================== FORMAT RESEARCH DATA WITH TEMPLATE ==============================
def format_narration_with_template(research_data: dict, logger: Logger) -> str:
    """
    Format research data into a predefined narration template.
    
    Args:
        research_data (dict): Dictionary containing:
            - product_title: Full name of the product
            - short_name: Short, friendly name for the product
            - intro_statement: Brief introduction
            - positive_features: String of positive features
            - negative_aspects: String of negative aspects
            - users_feedback: String of user feedback
            - competitors: String of competitor names
            - comparison: Comparison statement
            - recommendation: Final recommendation
    
    Returns:
        str: Formatted narration text
    """
    try:
        short_name = research_data.get('short_name', 'این محصول')
        intro_statement = research_data.get('intro_statement', 'یکی از محصولات خوب بازاره')
        positive_features = research_data.get('positive_features', 'ویژگی‌های خوبی داره')
        negative_aspects = research_data.get('negative_aspects', 'یه سری نکات منفی هم داره')
        users_feedback = research_data.get('users_feedback', 'کاربرا نظرات مختلفی دارن')
        competitors = research_data.get('competitors', 'محصولات مشابه')
        comparison = research_data.get('comparison', 'در سطح مناسبیه')
        recommendation = research_data.get('recommendation', 'می‌تونی بررسی کنی')
        
        #------------------------------------* NARRATION TEMPLATE *------------------------------------
        NARRATION_TEMPLATE = f"""
    خب امروز میخوایم {short_name} بررسی کنیم. {intro_statement}.

    نکته‌های خوبش اینه که {positive_features}.

    البته {negative_aspects}.

    [SPLIT_HERE]

    {users_feedback}.

    رقیباش هم مدل هایی مثل {competitors} هستن.

    در مقایسه با اون‌ها، {comparison}.

    {recommendation}.
    """
        
        return NARRATION_TEMPLATE.strip()
    except Exception as e:
        logger.error(f"Error formatting narration: {e}")
        return None


# ============================== SPLIT LONG NARRATION ==============================
def split_long_narration(narration_text: str, logger: Logger) -> list[str]:
    """
    Split long narration text into second parts based on content structure.
    First part: intro, positive features, negative aspects
    Second part: user feedback, competitors, comparison, recommendation
    Cleans up text by removing extra spaces, fixing punctuation, and removing duplicate words.
    Adds natural transition phrases between parts.
    
    Args:
        narration_text (str): The complete narration text in Farsi
        logger: Logger
    
    Returns:
        list: List of cleaned text parts with transitions, or single-item list if no split needed
    """
    # Estimate: ~3 words per second in Farsi, average 5 chars per word + spaces
    # 60 seconds ≈ 180 words ≈ 900 characters (being conservative with 900)
    MAX_CHARS_PER_PART = 500
    
    try:
        # Check if there's a split marker in the template
        if "[SPLIT_HERE]" in narration_text:
            logger.info("Found split marker, splitting narration into structured parts...")
            
            # Split by marker
            parts = narration_text.split("[SPLIT_HERE]")
            part1 = parts[0].strip()
            part2 = parts[1].strip() if len(parts) > 1 else ""
            
            # Use OpenAI to clean up the text and add transition
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            cleanup_prompt = f"""You are a professional text editor for voice messages in Farsi. Your task is to CLEAN UP two parts of a product review and add a proper transition.

                        TEXT CLEANUP RULES (VERY IMPORTANT):
                        1. Remove EXTRA SPACES between words (multiple spaces → single space)
                        2. Fix punctuation marks (commas, dots, etc.):
                           - Remove excessive punctuation (e.g., ".." → ".")
                           - Add missing commas where needed for natural flow
                           - Remove unnecessary punctuation
                        3. Remove DUPLICATE WORDS (e.g., "خوب خوب" → "خوب")
                        4. Fix spacing around punctuation marks according to Farsi rules
                        5. Ensure proper sentence structure and flow
                        6. Keep the conversational Farsi tone natural and friendly

                        PART 1 (Intro, positive features, negative aspects):
                        {part1}

                        PART 2 (User feedback, competitors, comparison, recommendation):
                        {part2}

                        INSTRUCTIONS:
                        1. Clean up Part 1 and add a casual transition phrase at the end
                        2. For Part 2, start with a phrase like "خب بررسی خودمون رو با [FEATURE] ادامه میدیم" where [FEATURE] should be something relevant from Part 2 (like "بازخورد کاربرا" for user feedback section)
                        3. Then clean up the rest of Part 2

                        SUGGESTED TRANSITION PHRASES FOR PART 1 END:
                        - "خیلی خب، توضیحاتمو توی ویس بعدی ادامه میدم"
                        - "بقیه نکات رو توی ویس بعدی واست میگم"
                        - "صبر کن، ادامشو توی پیام بعدی میگم"

                        SUGGESTED START PHRASES FOR PART 2:
                        - "خب بررسی خودمون رو با بازخورد کاربرا ادامه میدیم"
                        - "خب بیا ببینیم کاربرا چی میگن"
                        - "خب الان نظر کاربرا رو بررسی می‌کنیم"

                        Return ONLY a JSON array with EXACTLY 2 CLEANED text parts:
                        ["cleaned part 1 with transition...", "cleaned part 2 with intro phrase..."]

                        Return ONLY the JSON array, no other text."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional Farsi text editor that cleans up text and adds natural transitions for voice messages. You fix grammar, remove extra spaces, correct punctuation, and remove duplicate words while maintaining natural conversational flow."
                    },
                    {
                        "role": "user",
                        "content": cleanup_prompt
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
            
            if not isinstance(text_parts, list) or len(text_parts) != 2:
                logger.error(f"Failed to split narration properly: {response_text}")
                return [narration_text.replace("[SPLIT_HERE]", "").strip()]
            
            logger.info(f"Split narration into {len(text_parts)} structured parts")
            for i, part in enumerate(text_parts, 1):
                logger.info(f"Part {i} length: {len(part)} chars (~{len(part) // 15} seconds)")
            
            return text_parts
        
        # If no split marker, check if text is short enough
        text_length = len(narration_text)
        
        if text_length <= MAX_CHARS_PER_PART:
            logger.info(f"Text length ({text_length} chars) is within 60 seconds limit")
            return [narration_text]
        
        # If text is long but no split marker (legacy support), fall back to generic split
        logger.warning("Text is long but no split marker found, using generic split...")
        
        # Calculate optimal number of parts for equal distribution
        num_parts = (text_length // MAX_CHARS_PER_PART) + (1 if text_length % MAX_CHARS_PER_PART > 0 else 0)
        target_chars_per_part = text_length // num_parts
        
        logger.info(f"Text is long ({text_length} chars), splitting into {num_parts} equal parts...")
        logger.info(f"Target length per part: ~{target_chars_per_part} chars (~{target_chars_per_part // 15} seconds each)")
        
        # Use OpenAI to intelligently split the text
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        split_prompt = f"""You are a professional text editor for voice messages in Farsi. Your task is to split and CLEAN the following long text into {num_parts} parts of ROUGHLY EQUAL LENGTH.

                    IMPORTANT SPLITTING RULES:
                    1. Split into {num_parts} parts, each approximately {target_chars_per_part} characters
                    2. Parts should be ROUGHLY EQUAL in length (avoid one long part and one very short part)
                    3. Split at natural breaking points (between topics, not mid-sentence)
                    4. Each part should be coherent and make sense on its own
                    5. Add a natural transition phrase at the END of each part (except the last one)
                    6. Transition phrases should be casual, conversational and friendly

                    TEXT CLEANUP RULES (VERY IMPORTANT):
                    Before splitting, clean up the text according to Farsi writing standards:
                    1. Remove EXTRA SPACES between words (multiple spaces → single space)
                    2. Fix punctuation marks (commas, dots, etc.):
                    - Remove excessive punctuation (e.g., ".." → ".")
                    - Add missing commas where needed for natural flow
                    - Remove unnecessary punctuation
                    3. Remove DUPLICATE WORDS (e.g., "خوب خوب" → "خوب")
                    4. Fix spacing around punctuation marks according to Farsi rules
                    5. Ensure proper sentence structure and flow
                    6. Keep the conversational Farsi tone natural and friendly

                    SUGGESTED TRANSITION PHRASES (use variety):
                    - "خیلی خب، توضیحاتمو توی ویس بعدی ادامه میدم"
                    - "بقیه نکات رو توی ویس بعدی واست میگم"
                    - "صبر کن، ادامشو توی پیام بعدی میگم"
                    - "یه لحظه، بذار ادامشو توی ویس بعدی بگم"
                    - "باقی مطالب رو توی پیام بعدی میشنوی"

                    TEXT TO SPLIT AND CLEAN (Total: {text_length} chars → Target: {num_parts} parts of ~{target_chars_per_part} chars each):
                    {narration_text}

                    Return ONLY a JSON array with EXACTLY {num_parts} CLEANED text parts of roughly equal length. 
                    Make sure each part has proper grammar, no extra spaces, correct punctuation, and no duplicate words.

                    Example format:
                    ["part 1 cleaned text... خیلی خب، توضیحاتم رو توی ویس بعدی ادامه میدم", "part 2 cleaned text... بقیه نکات رو توی ویس بعدی واست میگم", "final part cleaned text"]

                    Return ONLY the JSON array, no other text."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional Farsi text editor that cleans up and splits text intelligently for voice messages. You fix grammar, remove extra spaces, correct punctuation, and remove duplicate words while maintaining natural conversational flow."
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
            logger.error(f"Failed to split narration: {response_text}")
            return [narration_text]
        
        logger.info(f"Split narration into {len(text_parts)} parts")
        for i, part in enumerate(text_parts, 1):
            logger.info(f"Part {i} length: {len(part)} chars (~{len(part) // 15} seconds)")
        
        return text_parts
        
    except Exception as e:
        logger.error(f"Failed to split narration: {e}")
        return [narration_text.replace("[SPLIT_HERE]", "").strip() if "[SPLIT_HERE]" in narration_text else narration_text]


# ============================== QUERY TO NARRATION ==============================
def query_to_narration(product_info: dict, location: str, logger: Logger):
    """
    Conduct deep product research using Perplexity AI and generate audio review.
    
    Args:
        product_info (dict): Product information including product_brand, product_title
        location (str): Location for price research (e.g., "Canada", "US")
        logger: Logger
    Returns:
        list: List of narration text parts (split if longer than 60 seconds) or None if error
    """
    try:
        #product_title = product_info.get('product_title')
        #product_brand = product_info.get('product_brand')
        
        # Structured system prompt that returns JSON data for template
        # Determine price search sources based on location
        #price_sources = ""
        #if location.lower() in ['iran', 'ایران', 'tehran', 'تهران']:
        #    price_sources = "Iranian e-commerce websites (Digikala, Torob, etc.)"
        #else:
        #    price_sources = f"{location} market retailers and e-commerce platforms"
        
        system_prompt = f"""You are a friendly and knowledgeable product advisor who talks like a close friend. Your task is to research a product and create TWO separate voice narrations in VERY CASUAL, FRIENDLY Farsi each 500 characters.

                        ⚠️ CRITICAL: Use ONLY informal/colloquial Farsi verbs (داره, نداره, می‌کنه, میشه, می‌تونه) - NEVER formal verbs (دارد, ندارد, می‌کند, می‌شود, می‌تواند)

                        🎯 TONE REQUIREMENTS:
                        - Write like you're talking to your best friend over coffee
                        - Use casual expressions: "خب", "ببین", "اصلاً", "واقعاً", "خیلی", "یه کم"
                        - Be enthusiastic and personal: "من که خیلی خوشم اومد", "به نظرم عالیه"
                        - Use contractions and casual forms: "میشه" not "می‌شود", "داره" not "دارد"
                        - Add personality: "باورم نمیشه", "واقعاً عجیبه", "خیلی جالبه"

                        IMPORTANT RESEARCH REQUIREMENTS:
                        - Gather REAL user feedback and reviews from the internet (Reddit, Amazon, YouTube comments, tech forums, etc.)
                        - Base your analysis on actual user experiences, not just specifications

                        RESPONSE FORMAT - Return ONLY a JSON object with these exact keys:
                        {{
                            "narration_part_1": "First voice narration - complete text ready for voice",
                            "narration_part_2": "Second voice narration - complete text ready for voice"
                        }}

                        NARRATION STRUCTURE:

                        📝 NARRATION PART 1 (First Voice) - MUST CONTAIN EXACTLY:
                        1. INTRO_STATEMENT: Brief introduction with product short name (e.g., "خب امروز میخوایم گلکسی بادز بررسی کنیم. یکی از محبوب‌ترین هدفون‌های بی‌سیمه")
                        2. POSITIVE_FEATURES: 3 specific positive features in casual language (e.g., "نکته‌های خوبش اینه که کیفیت صداش واقعاً عالیه، باتریش خیلی خوبه، و قیمتش هم مناسبه")
                        3. NEGATIVE_ASPECTS: 2-3 weaknesses honestly but casually (e.g., "البته یه کم سنگینه و گاهی واقعاً گرم میشه")
                        4. TRANSITION PHRASE: End with casual transition (e.g., "خیلی خب، توضیحاتمو توی ویس بعدی ادامه میدم")

                        Example Part 1 structure:
                        "خب امروز میخوایم [SHORT_NAME] بررسی کنیم. [INTRO_STATEMENT].
                        
                        نکته‌های خوبش اینه که [POSITIVE_FEATURES].
                        
                        البته [NEGATIVE_ASPECTS].
                        
                        خیلی خب، توضیحاتمو توی ویس بعدی ادامه میدم"

                        📝 NARRATION PART 2 (Second Voice) - MUST CONTAIN EXACTLY:
                        1. START PHRASE: "خب بررسی خودمون رو با بازخورد کاربرا ادامه میدیم" or "خب بیا ببینیم کاربرا چی میگن"
                        2. USER_FEEDBACK: Real user feedback from internet research (e.g., "بر اساس نظراتی که دیدم، کاربرا میگن که واقعاً راحته و کیفیت ساختش عالیه")
                        3. COMPETITORS: Name 3 real competitor products (e.g., "رقیباش هم مدل هایی مثل Apple AirPods Pro، Sony WF-1000XM4، و Jabra Elite 85t هستن")
                        4. COMPARISON: Compare with competitors (e.g., "در مقایسه با اون‌ها، باتریش بهتره ولی قیمتش یه کم بیشتره")
                        5. RECOMMENDATION: Final casual recommendation (e.g., "من که می‌تونم بگم اگه بودجه‌ت بهش برسه، واقعاً ارزش خرید داره")

                        Example Part 2 structure:
                        "خب بررسی خودمون رو با بازخورد کاربرا ادامه میدیم. [USER_FEEDBACK].
                        
                        رقیباش هم مدل هایی مثل [COMPETITORS] هستن.
                        
                        در مقایسه با اون‌ها، [COMPARISON].
                        
                        [RECOMMENDATION]"

                        CRITICAL CONTENT REQUIREMENTS:
                        
                        FOR NARRATION PART 1 (First Voice):
                        ✅ MUST HAVE: intro_statement (product introduction)
                        ✅ MUST HAVE: positive_features (3 specific features with casual enthusiasm)
                        ✅ MUST HAVE: negative_aspects (2-3 weaknesses with casual honesty)
                        ✅ MUST END WITH: transition phrase to next voice
                        
                        FOR NARRATION PART 2 (Second Voice):
                        ✅ MUST START WITH: "خب بررسی خودمون رو با بازخورد کاربرا ادامه میدیم" or similar
                        ✅ MUST HAVE: user_feedback (REAL feedback from internet research)
                        ✅ MUST HAVE: competitors (3 real competitor products)
                        ✅ MUST HAVE: comparison (honest comparison with competitors)
                        ✅ MUST HAVE: recommendation (casual, personal final advice)
                        TRANSITION PHRASES:
                        - End of Part 1: "خیلی خب، توضیحاتمو توی ویس بعدی ادامه میدم" or "بقیه نکات رو توی ویس بعدی واست میگم"
                        - Start of Part 2: "خب بررسی خودمون رو با بازخورد کاربرا ادامه میدیم" or "خب بیا ببینیم کاربرا چی میگن"

                        LENGTH GUIDELINES:
                        - Part 1: Approximately 400-500 characters (~30 seconds of speech)
                        - Part 2: Approximately 400-500 characters (~30 seconds of speech)
                        - Both parts should be roughly equal in length

                        TEXT QUALITY RULES:
                        1. Remove EXTRA SPACES between words (multiple spaces → single space)
                        2. Fix punctuation marks properly
                        3. NO DUPLICATE WORDS (e.g., "خوب خوب" → "خوب")
                        4. Proper spacing around punctuation
                        5. Natural sentence structure and flow

                        Return ONLY the JSON object, no additional text."""

        # Create Perplexity client
        client = Perplexity(api_key=PERPLEXITY_API_KEY)
        
        # Construct query
        query_text = f"product title: {product_info['product_title']}"
        if product_info['product_brand'] and product_info['product_brand'] != 'N/A':
            query_text += f", brand: {product_info['product_brand']}"
        
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
        
        response_text = response_text.strip()
        if response_text.startswith('```'):
            content = response_text.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            response_text = content.strip()
        
        # Parse JSON
        narration_data = json.loads(response_text)
        
        # Extract the two narration parts
        narration_part_1 = narration_data.get('narration_part_1', '').strip()
        narration_part_2 = narration_data.get('narration_part_2', '').strip()
        
        if not narration_part_1 or not narration_part_2:
            logger.error("Failed to extract narration parts from response")
            return None
        
        logger.info(f"Generated narration part 1 length: {len(narration_part_1)} chars")
        logger.info(f"Generated narration part 2 length: {len(narration_part_2)} chars")
        
        # Return both parts as a list
        return [narration_part_1, narration_part_2]
            
    except Exception as e:
        logger.error(f"Error in deep product research: {e}")
        logger.error(f"Error details: {str(e)}")
        return None




