# backend/app_fastapi.py
"""
Main FastAPI application for the RAG system.
Modular structure with separate routers for different functionalities.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.health import router as health_router
from app.companies import router as companies_router
from app.company_documents import router as company_documents_router
from app.document_processing import router as document_processing_router
from app.events import router as events_router
from app.indexing import router as indexing_router
from app.database_endpoints import router as database_router

# Load environment variables
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Create FastAPI app
app = FastAPI(
    title="RAG System API",
    description="API for managing documents, companies, and indexing in the RAG system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="", tags=["health"])
app.include_router(companies_router, prefix="", tags=["companies"])
app.include_router(company_documents_router, prefix="", tags=["company_documents"])
app.include_router(document_processing_router, prefix="", tags=["document_processing"])
app.include_router(events_router, prefix="", tags=["events"])
app.include_router(indexing_router, prefix="", tags=["indexing"])
app.include_router(database_router, prefix="", tags=["database"])

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to the RAG System API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_fastapi:app", host="0.0.0.0", port=5001, reload=True)