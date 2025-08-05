import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configurationss
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "zeebra_db_prod"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "zeebra_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD")
}

# API configuration
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "reload": os.getenv("NODE_ENV") == "development"
} 