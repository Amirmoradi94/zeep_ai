import random

def get_text(key):
    texts = {
        "welcome_message": "Hey there! Welcome to Zeep! 🐝\n\nI'm your shopping sidekick, here to find the best products from Instagram reels and posts! 🛍️",
        "region_selection": "Let's dive in! 🌟\n\nPlease select your region: US or CA.",
        "follow_page": "Get the Full Experience! ✨\n\nPlease follow the page to unlock unlimited product searches! 🛒",
        "correct_post_format": "Whoops! 😅\n\nPlease share an Instagram reel or post with the product you're hunting for! 📷",
        "ready_to_start": "Let's make shopping magic! 🪄\n\nSend me an Instagram reel or post of what you want, and I'll find the best matches! 🛍️",
        "GOOD_feedback_message": "Yay! Thanks for the love! 💖\n\nSo happy you're enjoying Zeep's shopping magic!",
        "BAD_feedback_message": "So sorry to hear that. 😔",
        "analyzing_post": [
            " دارم پستی که فرستادی رو تحلیل میکنم.\n\n یکم صبر کن لطفا..."
        ],
        "deep_analysis_message": "دارم یک تحلیل عمیق روی این محصول انجام میدم و بهت نتیجه رو به صورت صوتی میفرستم 🎤\n\nیکم صبر کن...",
        "internal_error": "OOPS! 😓\n\nWe are doing maintenance. Please try again soon! 🔧",
        "general_message": "Thanks for messaging Zeep!\n\nPlease send an Instagram reel or post with the product you want! 📸",
        "error_generating_query": "Sorry, I couldn't identify the product in your post. Please try again with a clearer image or reel! 🔍",
        "post_deleted": "Oh no! 😕\n\nThe message you sent seems to be gone. ",
        "we_are_working_on_it": "We're searching deep and wide for the best deals! 🕒",
        "restricted_product_message_sent": "We're sorry, this product is restricted. Please try a different reel or post! 📸",
        "ask_user_for_product_brand": "ببخشید من نتونستم برند محصول رو پیدا کنم. لطفا برند محصول رو بهم بگو.",
    }
    
    if key == "analyzing_post":
        return random.choice(texts["analyzing_post"])
    return texts.get(key)