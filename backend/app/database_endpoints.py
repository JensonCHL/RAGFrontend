# backend/app/database_endpoints.py
"""
Database-related endpoints for the FastAPI application.
"""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import json
from datetime import datetime

from core.database import get_db_connection

router = APIRouter()


@router.get("/api/get-all-data")
async def get_all_data():
    """Fetches all records from the extracted_data table for debugging."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, company_name, file_name, index_name, result, created_at FROM extracted_data ORDER BY created_at DESC;")
            rows = cur.fetchall()

            # Get column names from the cursor description
            column_names = [desc[0] for desc in cur.description]

            # Convert rows to a list of dictionaries
            data = [dict(zip(column_names, row)) for row in rows]

            # Convert datetime objects to ISO format strings
            for row in data:
                if 'created_at' in row and isinstance(row['created_at'], datetime):
                    row['created_at'] = row['created_at'].isoformat()

            return JSONResponse(content={'success': True, 'data': data})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/list-indexes")
async def list_indexes():
    """
    API endpoint to list all unique index names present in the extracted_data table.
    No authentication required.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT index_name FROM extracted_data ORDER BY index_name;")
            index_names = [row[0] for row in cur.fetchall()]
            return JSONResponse(content={'index_names': index_names})
    except Exception as e:
        print(f"[DB_ERROR] Failed to fetch index names: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.delete("/api/index/{index_name}")
async def delete_index(index_name: str = Path(..., description="Name of the index to delete")):
    """
    Deletes all data associated with a specific index_name from the database.
    (Authentication temporarily removed for testing/debugging purposes)
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM extracted_data WHERE index_name = %s;", (index_name,))
            conn.commit()
            deleted_count = cur.rowcount
            print(f"[DB_INFO] Deleted {deleted_count} rows for index_name: {index_name}")
            return JSONResponse(content={'success': True, 'message': f'Successfully deleted {deleted_count} records for index \'{index_name}\''})
    except Exception as e:
        conn.rollback()
        print(f"[DB_ERROR] Failed to delete index data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()