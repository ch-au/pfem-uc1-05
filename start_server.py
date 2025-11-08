#!/usr/bin/env python3
"""
Simple startup script for FastAPI server
"""
import uvicorn
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Mainz 05 Quiz & Chatbot API Server")
    print("=" * 60)
    print("\nServer will be available at:")
    print("  - API: http://localhost:8000")
    print("  - Swagger UI: http://localhost:8000/docs")
    print("  - ReDoc: http://localhost:8000/redoc")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )




