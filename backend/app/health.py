# backend/app/health.py
"""
Health check endpoints for the FastAPI application.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return JSONResponse(content={
        'status': 'healthy',
        'service': 'Qdrant API'
    })