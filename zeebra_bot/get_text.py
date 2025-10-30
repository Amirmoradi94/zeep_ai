import random

def get_text(key):
    texts = {
        "welcome_message": "Hey there! Welcome to Zeebra! 🐝\n\nI'm your shopping sidekick, here to find the best products from Instagram reels and posts! 🛍️",
        "region_selection": "Let's dive in! 🌟\n\nPlease select your region: US or CA.",
        "follow_page": "Get the Full Experience! ✨\n\nPlease follow the page to unlock unlimited product searches! 🛒",
        "correct_post_format": "Whoops! 😅\n\nPlease share an Instagram reel or post with the product you're hunting for! 📷",
        "no_products_found": "Hmm, nothing matched this time. 😕\n\nTry sending a screenshot of the product! 🔎",
        "ready_to_start": "Let's make shopping magic! 🪄\n\nSend me an Instagram reel or post of what you want, and I'll find the best matches! 🛍️",
        "GOOD_feedback_message": "Yay! Thanks for the love! 💖\n\nSo happy you're enjoying Zeebra's shopping magic!",
        "BAD_feedback_message": "So sorry to hear that. 😔",
        "analyzing_post": [
            " دارم پستی که فرستادی رو تحلیل میکنم. \n نقد و بررسی خودمو در قالب ویس واست میفرستم \n\n یکم  صبر کن لطفا..."
        ],
        "internal_error": "OOPS! 😓\n\nWe are doing maintenance. Please try again soon! 🔧",
        "general_message": "Thanks for messaging Zeebra!\n\nPlease send an Instagram reel or post with the product you want! 📸",
        "post_deleted": "Oh no! 😕\n\nThe message you sent seems to be gone. ",
        "we_are_working_on_it": "We're searching deep and wide for the best deals! 🕒",
        "restricted_product_message_sent": "We're sorry, this product is restricted. Please try a different reel or post! 📸",
        "no_more_products": "No more products available at the moment. \n\nYou can send me a new post or reel to find more products! 🐝"
    }
    
    if key == "analyzing_post":
        return random.choice(texts["analyzing_post"])
    return texts.get(key)