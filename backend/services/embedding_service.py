"""
Embedding Service Module
Handles document embedding generation using Deka AI
"""

import json
import uuid
from typing import Generator, List, Dict, Any

from core.config import DEKA_KEY, DEKA_BASE, EMBED_MODEL, BATCH_SIZE
from core.clients import deka_client

# ============================================================================
# EMBEDDING FUNCTIONS
# ============================================================================

def build_embedder():
    """
    Build OpenAI embeddings compatible with Deka AI
    
    Returns:
        OpenAIEmbeddings instance or None if not configured
    """
    from langchain_openai import OpenAIEmbeddings
    
    if not deka_client:
        return None
        
    return OpenAIEmbeddings(
        api_key=DEKA_KEY,
        base_url=DEKA_BASE,
        model=EMBED_MODEL,
        model_kwargs={"encoding_format": "float"}
    )


def generate_embeddings(
    chunks_data: List[Dict[str, Any]], 
    doc_id: str
) -> Generator[str, None, None]:
    """
    Generate embeddings for document chunks with progress tracking
    
    Args:
        chunks_data: List of chunk dictionaries with text and metadata
        doc_id: Document ID for generating point IDs
        
    Yields:
        JSON progress updates
    """
    try:
        # Build embedder
        embedder = build_embedder()
        if not embedder:
            yield json.dumps({"error": "Embedder not configured"}) + "\n"
            return
            
        # Detect embedding dimension
        dim = len(embedder.embed_query("hello world"))
        yield json.dumps({
            "status": "embedding_started",
            "message": f"Generating embeddings for {len(chunks_data)} chunks",
            "dimension": dim,
            "chunk_count": len(chunks_data)
        }) + "\n"
        
        # Prepare chunks for embedding
        texts = [chunk["text"] for chunk in chunks_data]
        total_chunks = len(texts)
        
        # Generate embeddings in batches
        vectors = []
        
        for i in range(0, total_chunks, BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
            
            yield json.dumps({
                "status": "embedding_batch",
                "batch": batch_num,
                "total_batches": total_batches,
                "message": f"Generating embeddings for batch {batch_num}/{total_batches}",
                "embeddingProgress": {
                    "batch": batch_num,
                    "total_batches": total_batches
                }
            }) + "\n"
            
            try:
                # Generate embeddings for batch
                batch_vectors = embedder.embed_documents(batch)
                vectors.extend(batch_vectors)
                
                yield json.dumps({
                    "status": "embedding_batch_completed",
                    "batch": batch_num,
                    "processed": len(batch_vectors),
                    "message": f"Completed batch {batch_num}/{total_batches}",
                    "embeddingProgress": {
                        "batch": batch_num,
                        "total_batches": total_batches
                    }
                }) + "\n"
                
            except Exception as e:
                yield json.dumps({
                    "status": "embedding_error",
                    "batch": batch_num,
                    "error": f"Failed to generate embeddings for batch {batch_num}: {str(e)}"
                }) + "\n"
                return
        
        # Prepare final result with IDs and payloads
        result_data = []
        for i, chunk in enumerate(chunks_data):
            # Generate point ID using UUIDv5
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk['page']}"))
            
            result_data.append({
                "id": point_id,
                "vector": vectors[i] if i < len(vectors) else None,
                "payload": {
                    "content": chunk["text"],
                    "metadata": chunk.get("meta", {})
                }
            })
        
        yield json.dumps({
            "status": "embedding_completed",
            "vectors_generated": len(vectors),
            "points_data": result_data,
            "message": f"Embedding completed: {len(vectors)} vectors generated"
        }) + "\n"
        
    except Exception as e:
        yield json.dumps({
            "status": "embedding_failed",
            "error": f"Embedding generation failed: {str(e)}"
        }) + "\n"

print("✅ Embedding service initialized")
