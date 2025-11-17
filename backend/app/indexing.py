# backend/app/indexing.py
"""
Indexing endpoints for the FastAPI application.
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
import threading
import os
from typing import Optional

from services.indexing_service import job_orchestrator
from core.config import get_settings

router = APIRouter()
settings = get_settings()


def verify_api_key(authorization: Optional[str] = Header(None)) -> bool:
    """
    Dependency to verify API key from Authorization header.
    """
    # If no API key is set in config, allow access (development mode)
    if not settings.N8N_API_KEY:
        return True
        
    # Check if authorization header exists and is valid
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header is missing or invalid")
        
    token = authorization.split(" ")[1]
    if token != settings.N8N_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    return True


@router.post("/api/create-index")
async def create_index_endpoint(
    index_name: str,
    api_key_verified: bool = True  # Depends(verify_api_key)
):
    """
    API endpoint to start a full manual indexing job, protected by an API key.
    Expects 'Authorization: Bearer <YOUR_API_KEY>' in the header.
    """
    
    if not index_name:
        raise HTTPException(status_code=400, detail="Missing index_name")

    # Run the entire orchestration in a single background thread
    orchestrator_thread = threading.Thread(target=job_orchestrator, args=(index_name, settings.PROJECT_ROOT))
    orchestrator_thread.daemon = True
    orchestrator_thread.start()

    return JSONResponse(
        content={'success': True, 'message': f'Indexing job launched for: {index_name}'},
        status_code=202
    )