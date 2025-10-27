
from perplexity import Perplexity
import os
from logging import Logger





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


def query_to_narration(search_query: dict, logger: Logger = None):
    """
    Conduct deep product research using Perplexity AI and generate audio review.
    
    Args:
        search_query (dict): Product search query including product_brand, product_title
        logger: Logger instance
    Returns:
        str: Audio review text or None if error
    """
    try:
        product_title = search_query.get('product_title')
        product_brand = search_query.get('product_brand')
        
        # Structured system prompt that returns JSON data for template
        system_prompt = """You are a friendly and knowledgeable product advisor. Your task is to research a product and provide structured data in Farsi for a narration template.

RESPONSE FORMAT - Return ONLY a JSON object with these exact keys:
{
    "product_title": "نام محصول",
    "intro_statement": "یک جمله معرفی کوتاه و دوستانه",
    "positive_features": "ویژگی مثبت اول، ویژگی مثبت دوم، و ویژگی مثبت سوم",
    "negative_aspects": "نکته منفی اول و نکته منفی دوم",
    "competitors": "رقیب اول، رقیب دوم، و رقیب سوم",
    "comparison": "جمله مقایسه با رقیبا",
    "recommendation": "توصیه نهایی"
}

CONTENT GUIDELINES:

1. intro_statement: 
   - One friendly sentence about the product
   - Examples: "یکی از بهترین انتخاب‌هاست توی بازار", "محصول خوبیه برای استفاده روزمره"

2. positive_features:
   - List 3 specific positive features separated by "،"
   - Use conversational style
   - Example: "باتریش خیلی خوبه، کیفیت ساختش عالیه، و قیمتش مناسبه"

3. negative_aspects:
   - List 2 concerns or weaknesses with "و" between them
   - Be honest but constructive
   - Example: "یه کم سنگینه و گاهی گرم میشه"

4. competitors:
   - Name 3 real competitor products separated by "،" and "و"
   - Use actual product names
   - Example: "Samsung Galaxy Buds، Sony WF-1000XM5، و Apple AirPods Pro"

5. comparison:
   - One sentence comparing with competitors
   - Example: "نسبت به رقیباش قیمتش بهتره ولی باتریش کمتره"

6. recommendation:
   - Final friendly recommendation in one sentence
   - Examples: "می‌تونم بگم که ارزش خرید داره", "اگه بودجه‌ت محدوده، گزینه خوبیه"

LANGUAGE STYLE:
- Use conversational Farsi like talking to a friend
- Be specific and helpful
- Keep each section concise (total ~150-200 words)
- Make it natural for voice narration

Return ONLY the JSON object, no additional text."""

        # Create Perplexity client
        client = Perplexity()
        
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
            return narration_text
        else:
            print("❌ Failed to format narration")
            return None
            
    except Exception as e:
        print(f"❌ Error in deep product research: {e}")
        print(f"Error details: {str(e)}")
        return None

