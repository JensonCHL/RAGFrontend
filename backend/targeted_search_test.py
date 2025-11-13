#!/usr/bin/env python3
"""
Targeted Search Test for DataStreamLit Collection
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
QDRANT_COLLECTION = "BadResult"  # Focus on this collection
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

def test_targeted_search():
    """Test search with your specific prompt"""
    query_text = "Company: AIRNAV\nDocument: PURCHASE ORDER DEKA GPU PERUM LEMBAGA PENYELENGGARA PELAYANAN NAVIGASI PENERBANGAN INDONESI.pdf"
    
    print(f"[SEARCH] Testing with prompt: '{query_text}'")
    print("=" * 70)
    
    try:
        # Build embedder
        embedder = build_embedder()
        if not embedder:
            return
            
        # Generate query vector
        query_vector = embedder.embed_query(query_text)
        print(f"SUCCESS: Generated query vector (dim: {len(query_vector)})")
        
        # Initialize client
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Test different search approaches
        print("\n--- EXACT CONTENT MATCH TEST ---")
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=5,
            with_payload=True,
            search_params=rest.SearchParams(exact=True)
        )
        
        print(f"[RESULTS] Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. Score: {result.score:.6f}")
            if result.payload:
                metadata = result.payload.get('metadata', {})
                company = metadata.get('company', 'N/A')
                source = metadata.get('source', 'N/A')
                print(f"      Company: {company}")
                print(f"      Document: {source}")
                
        print("\n--- APPROXIMATE SEARCH TEST ---")
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=5,
            with_payload=True,
            search_params=rest.SearchParams(exact=False, hnsw_ef=256)
        )
        
        print(f"[RESULTS] Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. Score: {result.score:.6f}")
            if result.payload:
                metadata = result.payload.get('metadata', {})
                company = metadata.get('company', 'N/A')
                source = metadata.get('source', 'N/A')
                print(f"      Company: {company}")
                print(f"      Document: {source}")
                
        # # Test with filtering
        # print("\n--- FILTERED SEARCH TEST ---")
        # search_filter = rest.Filter(
        #     must=[
        #         rest.FieldCondition(
        #             key="metadata.company",
        #             match=rest.MatchValue(value="AIRNAV")
        #         ),
        #         rest.FieldCondition(
        #             key="metadata.source",
        #             match=rest.MatchValue(value="PURCHASE ORDER DEKA GPU PERUM LEMBAGA PENYELENGGARA PELAYANAN NAVIGASI PENERBANGAN INDONESI.pdf")
        #         )
        #     ]
        # )
        
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=5,
            with_payload=True,
            # query_filter=search_filter,
            search_params=rest.SearchParams(exact=False, hnsw_ef=256)
        )
        
        print(f"[RESULTS] Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. Score: {result.score:.6f}")
            if result.payload:
                metadata = result.payload.get('metadata', {})
                company = metadata.get('company', 'N/A')
                source = metadata.get('source', 'N/A')
                print(f"      Company: {company}")
                print(f"      Document: {source}")
                
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_targeted_search()