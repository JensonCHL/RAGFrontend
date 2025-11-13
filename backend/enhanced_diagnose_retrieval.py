#!/usr/bin/env python3
"""
Enhanced Diagnostic Script to Test Qdrant Retrieval with Proper Parameters
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
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "DataStreamLit")
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

def test_search_with_parameters(query_text="purchase order", company_filter=None, document_filter=None):
    """Test search with various parameters to optimize performance"""
    print(f"\n[SEARCH] Testing search: '{query_text}'")
    print("=" * 50)
    
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
        
        # Build filter if specified
        search_filter = None
        if company_filter or document_filter:
            must_conditions = []
            if company_filter:
                must_conditions.append(
                    rest.FieldCondition(
                        key="metadata.company",
                        match=rest.MatchValue(value=company_filter)
                    )
                )
            if document_filter:
                must_conditions.append(
                    rest.FieldCondition(
                        key="metadata.source",
                        match=rest.MatchValue(value=document_filter)
                    )
                )
            if must_conditions:
                search_filter = rest.Filter(must=must_conditions)
        
        print(f"Filter: {search_filter}")
        
        # Test different search parameters
        search_variants = [
            {"name": "Default search", "params": {}},
            {"name": "High ef_search", "params": {"hnsw_ef": 256}},
            {"name": "Exact search", "params": {"exact": True}},
            {"name": "High ef_search + Exact", "params": {"hnsw_ef": 256, "exact": True}},
        ]
        
        for variant in search_variants:
            print(f"\n--- {variant['name']} ---")
            
            # Search
            results = client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=5,
                with_payload=True,
                query_filter=search_filter,
                search_params=rest.SearchParams(**variant["params"]) if variant["params"] else None
            )
            
            print(f"[RESULTS] Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"   {i}. Score: {result.score:.6f}")
                if result.payload:
                    metadata = result.payload.get('metadata', {})
                    company = metadata.get('company', 'N/A')
                    source = metadata.get('source', 'N/A')
                    print(f"      Company: {company}, Document: {source}")
                    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

def test_exact_phrase_matching():
    """Test searching for exact phrases from your documents"""
    print("\n" + "="*60)
    print("TESTING EXACT PHRASE MATCHING")
    print("="*60)
    
    # Test phrases that should be in your documents
    test_phrases = [
        "AirNav Indonesia",
        "Purchase Order",
        "Lintasarta",
        "GPU L40S",
        "Tangerang, 17 Juni 2025"
    ]
    
    for phrase in test_phrases:
        print(f"\nTesting phrase: '{phrase}'")
        test_search_with_parameters(phrase)

if __name__ == "__main__":
    # Test basic search
    test_search_with_parameters("purchase order")
    
    # Test with filtering
    print("\n" + "="*60)
    print("TESTING WITH FILTERING")
    print("="*60)
    test_search_with_parameters("purchase order", company_filter="AIRNAV")
    
    # Test exact phrase matching
    test_exact_phrase_matching()