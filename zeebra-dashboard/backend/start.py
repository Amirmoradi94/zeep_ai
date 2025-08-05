#!/usr/bin/env python3
"""
Zeebra Dashboard Backend Startup Script
"""

import uvicorn
from config import API_CONFIG

if __name__ == "__main__":
    print("Starting Zeebra Dashboard Backend...")
    print(f"Server will run on http://{API_CONFIG['host']}:{API_CONFIG['port']}")
    print("Make sure your database is running and accessible!")
    
    uvicorn.run(
        "main:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG["reload"],
        log_level="info"
    ) 