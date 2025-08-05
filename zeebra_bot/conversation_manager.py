"""
Global conversation history manager for the Zeebra bot.
This module provides functions to manage conversation history that persists across webhook calls.
"""

# Global conversation history that persists across webhook calls
conversation_history = {}

def get_conversation_history(user_id: int) -> list:
    """Get conversation history for a specific user."""
    global conversation_history
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    return conversation_history[user_id]

def clear_conversation_history(user_id: int) -> None:
    """Clear conversation history for a specific user."""
    global conversation_history
    if user_id in conversation_history:
        print(f"DEBUG: Clearing conversation history for user {user_id}. Current length: {len(conversation_history[user_id])}")
        conversation_history[user_id] = []

def add_to_conversation_history(user_id: int, role: str, content: str) -> None:
    """Add a message to the conversation history for a specific user."""
    global conversation_history
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    conversation_history[user_id].append({
        "role": role,
        "content": content
    })

def get_all_conversation_history() -> dict:
    """Get all conversation history (for debugging purposes)."""
    global conversation_history
    return conversation_history.copy() 