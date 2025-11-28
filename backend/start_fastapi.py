"""
Startup script for FastAPI RAG System with verbose logging
"""

import uvicorn
import sys

if __name__ == "__main__":
    print("🚀 Starting FastAPI RAG System...")
    print("📖 API Documentation will be available at: http://localhost:5001/docs")
    print("🔧 Interactive API: http://localhost:5001/redoc")
    print("")
    
    try:
        uvicorn.run(
            "app_fastapi:app",
            host="0.0.0.0",  # Allow connections from anywhere
            port=5001,
            reload=False,  # Disable reload to avoid issues
            log_level="debug",  # More verbose logging
            access_log=True
        )
    except Exception as e:
        print(f"❌ ERROR starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
