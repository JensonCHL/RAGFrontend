#!/usr/bin/env python3
"""
Vector Analysis Script to Understand Score Differences
"""

import os
import sys
# Handle encoding issues on Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

from dotenv import load_dotenv
from qdrant_client import QdrantClient
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

def analyze_vectors():
    """Analyze stored vectors vs query vectors"""
    print("[ANALYSIS] Analyzing vectors")
    print("=" * 50)
    
    try:
        # Build embedder
        embedder = build_embedder()
        if not embedder:
            return
            
        # Initialize client
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Get a sample point
        points = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=1,
            with_payload=True,
            with_vectors=True
        )[0]
        
        if not points:
            print("No points found")
            return
            
        point = points[0]
        stored_vector = point.vector
        content = point.payload.get('content', '')
        
        print(f"Stored vector dimension: {len(stored_vector) if stored_vector else 'None'}")
        print(f"Content preview: {content[:100]}...")
        
        # Generate vector for the same content
        generated_vector = embedder.embed_query(content)
        print(f"Generated vector dimension: {len(generated_vector)}")
        
        # Calculate cosine similarity manually
        def cosine_similarity(a, b):
            import math
            dot_product = sum(x * y for x, y in zip(a, b))
            magnitude_a = math.sqrt(sum(x * x for x in a))
            magnitude_b = math.sqrt(sum(x * x for x in b))
            return dot_product / (magnitude_a * magnitude_b) if magnitude_a * magnitude_b != 0 else 0
        
        if stored_vector and generated_vector:
            similarity = cosine_similarity(stored_vector, generated_vector)
            print(f"Similarity between stored and generated vector: {similarity:.6f}")
        
        # Test search with exact same content
        print("\n--- SEARCH WITH EXACT SAME CONTENT ---")
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=generated_vector,
            limit=1,
            with_payload=True
        )
        
        if results:
            print(f"Search score: {results[0].score:.6f}")
            print(f"Expected to be very high (close to 1.0)")
        else:
            print("No results found")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_vectors()