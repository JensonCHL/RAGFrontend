#!/usr/bin/env python3
"""
General Query Test for DataStreamLit Collection
"""

import os
import sys
# Handle encoding issues on Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client import models as rest
from langchain_openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = "DataStreamLit"  # Focus on this collection
DEKA_KEY = os.getenv("DEKA_KEY")
DEKA_BASE = os.getenv("DEKA_BASE_URL")
EMBED_MODEL = os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2")

def build_embedder():
    """Build OpenAI embeddings compatible with Deka AI"""
    if not DEKA_KEY or not DEKA_BASE:
        print("ERROR: Deka AI configuration not found")
        return None

    return OpenAIEmbeddings(
        api_key=DEKA_KEY,
        base_url=DEKA_BASE,
        model=EMBED_MODEL,
        model_kwargs={"encoding_format": "float"}
    )

def test_general_queries():
    """Test with more general queries that might produce lower scores"""
    
    general_queries = [
        "purchase order",
        "AirNav Indonesia",
        "GPU L40S",
        "Tangerang, 17 Juni 2025",
        "Lintasarta services"
    ]
    
    print("[SEARCH] Testing general queries on DataStreamLit collection")
    print("=" * 70)
    
    try:
        # Build embedder
        embedder = build_embedder()
        if not embedder:
            return
            
        # Initialize client
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        for query_text in general_queries:
            print(f"\n--- Query: '{query_text}' ---")
            
            # Generate query vector
            query_vector = embedder.embed_query(query_text)
            
            # Search
            results = client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=3,
                with_payload=True
            )
            
            print(f"[RESULTS] Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                score = result.score
                if result.payload:
                    metadata = result.payload.get('metadata', {})
                    company = metadata.get('company', 'N/A')
                    source = metadata.get('source', 'N/A')
                    print(f"   {i}. Score: {score:.6f} - {company} / {source}")
                else:
                    print(f"   {i}. Score: {score:.6f}")
                    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_general_queries()