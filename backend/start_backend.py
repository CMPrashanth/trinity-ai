# Start Backend Script
# Run this in one terminal: python start_backend.py

import uvicorn
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Starting Trinity Agent Backend...")
    print("📍 API will be available at: http://localhost:8080")
    print("📚 API Docs at: http://localhost:8080/api/v1/docs")
    print("\n⚠️  Using SQLite database (trinity.db)")
    print("⚠️  Neo4j and ChromaDB will use mock data\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
