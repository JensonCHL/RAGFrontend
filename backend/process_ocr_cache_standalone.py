#!/usr/bin/env python3
"""
Standalone Debug Script for Processing OCR Cache Files

This script processes OCR cache JSON files sequentially and inserts them into Qdrant
using completely standalone implementations (no imports from app.py).

Usage:
    cd backend
    python process_ocr_cache_standalone.py
"""

import os
import sys
import json
import time
import hashlib
import uuid
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")

# Import required libraries (these are standard dependencies)
try:
    from langchain_openai import OpenAIEmbeddings
    from qdrant_client import QdrantClient
    from qdrant_client import models as rest
    from openai import OpenAI
    print("✅ Successfully imported required libraries")
except ImportError as e:
    print(f"❌ Failed to import required libraries: {e}")
    print("Please install required packages:")
    print("pip install langchain-openai qdrant-client openai python-dotenv")
    sys.exit(1)

# Configuration from environment variables
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "DataStreamLit")
DEKA_KEY = os.getenv("DEKA_KEY")
DEKA_BASE = os.getenv("DEKA_BASE_URL")
EMBED_MODEL = os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2")

def build_meta_header(meta: dict) -> str:
    """Build metadata header for document chunks - standalone implementation"""
    company = (meta or {}).get("company", "N/A")
    source = (meta or {}).get("source", "N/A")
    page = (meta or {}).get("page", "N/A")
    return f"Company: {company}\nDocument: {source}\nPage: {page}\n---\n"

def generate_document_id(company_id, file_name):
    """Generate a unique document ID based on company name and file name (deterministic) - standalone"""
    combined = f"{company_id}:{file_name}"
    return hashlib.sha1(combined.encode()).hexdigest()[:16]

def build_embedder():
    """Build OpenAI embeddings compatible with Deka AI - standalone implementation"""
    if not DEKA_KEY or not DEKA_BASE:
        print("❌ Deka AI configuration not found")
        return None

    return OpenAIEmbeddings(
        api_key=DEKA_KEY,
        base_url=DEKA_BASE,
        model=EMBED_MODEL,
        model_kwargs={"encoding_format": "float"}
    )

def generate_embeddings_standalone(chunks_data, doc_id):
    """Generate embeddings for document chunks one by one - standalone implementation"""
    try:
        print("  Building embedder...")
        embedder = build_embedder()
        if not embedder:
            print("  ❌ Embedder not configured")
            return []

        print(f"  Generating embeddings for {len(chunks_data)} chunks...")
        
        # Prepare chunks for embedding
        texts = [chunk["text"] for chunk in chunks_data]
        total_chunks = len(texts)

        # Generate embeddings in batches
        BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))
        vectors = []

        # Process each chunk individually
        for i, text in enumerate(texts):
            print(f"    Processing chunk {i+1}/{total_chunks}...")
            
            try:
                # Generate embedding for single text
                vector = embedder.embed_query(text)
                vectors.append(vector)
                print(f"    ✅ Completed chunk {i+1}/{total_chunks}")
                
            except Exception as e:
                print(f"    ❌ Failed to generate embedding for chunk {i+1}: {str(e)}")
                return []

        # Prepare final result with IDs and payloads
        result_data = []
        for i, chunk in enumerate(chunks_data):
            # Generate point ID using UUIDv5 (deterministic)
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk['page']}"))

            result_data.append({
                "id": point_id,
                "vector": vectors[i] if i < len(vectors) else None,
                "payload": {
                    "content": chunk["text"],
                    "metadata": chunk.get("meta", {})
                }
            })
            print(f"    Vector dimension: {len(vectors[i])}")
            
        print(f"  ✅ Generated {len(vectors)} embeddings")
        return result_data

    except Exception as e:
        print(f"  ❌ Error in generate_embeddings_standalone: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def ingest_to_qdrant_standalone(points_data, company_name, source_name):
    """Ingest embedded points to Qdrant - standalone implementation"""
    try:
        print(f"  Ingesting {len(points_data)} points to Qdrant...")
        
        if not points_data:
            print("  ⚠️  No points to ingest")
            return 0
            
        # Initialize Qdrant client
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )

        # Ensure collection exists
        try:
            qdrant_client.get_collection(QDRANT_COLLECTION)
            print(f"  Collection {QDRANT_COLLECTION} exists")
        except Exception:
            # Collection doesn't exist, create it
            try:
                dim = len(points_data[0]["vector"]) if points_data[0]["vector"] else 768
                qdrant_client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=rest.VectorParams(
                        size=dim, distance=rest.Distance.COSINE),
                )
                print(f"  ✅ Created collection {QDRANT_COLLECTION} with dimension {dim}")
            except Exception as create_error:
                if "already exists" in str(create_error):
                    print(f"  Collection {QDRANT_COLLECTION} already exists")
                else:
                    raise create_error

        # Create PointStruct objects
        points = [
            rest.PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point["payload"]
            )
            for point in points_data
        ]

        # Upload to Qdrant
        qdrant_client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points,
            wait=True
        )
        
        print(f"  ✅ Successfully ingested {len(points)} points to Qdrant")
        return len(points)
        
    except Exception as e:
        print(f"  ❌ Error in ingest_to_qdrant_standalone: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def process_single_json_file(json_file_path, company_name, file_name):
    """Process a single OCR cache JSON file through the entire pipeline"""
    print(f"\n{'='*60}")
    print(f"Processing: {company_name} / {file_name}")
    print(f"{'='*60}")
    
    try:
        # 1. Load OCR JSON data
        print(f"1. Loading OCR data from: {json_file_path}")
        with open(json_file_path, 'r', encoding='utf-8') as f:
            ocr_pages_data = json.load(f)
        print(f"   ✅ Loaded {len(ocr_pages_data)} pages")
        
        # 2. Generate document ID (standalone implementation)
        print("2. Generating document ID...")
        doc_id = generate_document_id(company_name, file_name)
        print(f"   ✅ Document ID: {doc_id}")
        
        # 3. Create chunks with metadata (standalone implementation)
        print("3. Creating chunks with metadata...")
        chunks_data = []
        for page_data in ocr_pages_data:
            meta = {
                "company": company_name,
                "source": file_name,
                "page": page_data["page"],
                "doc_id": doc_id,
                "words": page_data["words"],
                "upload_time": time.time()
            }
            text_with_header = build_meta_header(meta) + page_data["text"]
            chunks_data.append({
                "text": text_with_header,
                "meta": meta,
                "page": page_data["page"]
            })
        print(f"   ✅ Created {len(chunks_data)} chunks")
        
        # 4. Generate embeddings (standalone implementation)
        print("4. Generating embeddings...")
        points_data = generate_embeddings_standalone(chunks_data, doc_id)
        if not points_data:
            print("   ❌ Failed to generate embeddings")
            return False
        print(f"   ✅ Generated {len(points_data)} embeddings")
        
        # 5. Ingest to Qdrant (standalone implementation)
        print("5. Ingesting to Qdrant...")
        ingested_count = ingest_to_qdrant_standalone(points_data, company_name, file_name)
        if ingested_count == 0:
            print("   ❌ Failed to ingest to Qdrant")
            return False
        print(f"   ✅ Successfully ingested {ingested_count} points")
        
        print(f"\n✅ Successfully processed: {file_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error processing {file_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def find_all_json_files():
    """Find all JSON files in the OCR cache directory"""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    ocr_cache_root = os.path.join(backend_dir, 'ocr_cache')
    
    if not os.path.exists(ocr_cache_root):
        print(f"OCR cache directory not found: {ocr_cache_root}")
        return []
    
    json_files = []
    
    print(f"Scanning OCR cache directory: {ocr_cache_root}")
    
    for company_dir in Path(ocr_cache_root).iterdir():
        if company_dir.is_dir():
            company_name = company_dir.name
            
            for json_file in company_dir.iterdir():
                if json_file.suffix == '.json':
                    # Extract original filename (remove .pdf.json extension)
                    original_filename = json_file.name
                    if original_filename.endswith('.pdf.json'):
                        original_filename = original_filename[:-9] + '.pdf'  # Remove .pdf.json, add .pdf
                    elif original_filename.endswith('.json'):
                        original_filename = original_filename[:-5]  # Remove .json
                    
                    json_files.append({
                        'path': str(json_file),
                        'company': company_name,
                        'filename': original_filename
                    })
                    print(f"  Found: {company_name} / {original_filename}")
    
    print(f"Found {len(json_files)} JSON files to process")
    return json_files

def main():
    """Main function to process all OCR cache files sequentially"""
    print("Standalone Sequential OCR Cache Processor for Debugging")
    print("=" * 50)
    print(f"Qdrant Collection: {QDRANT_COLLECTION}")
    print(f"Embedding Model: {EMBED_MODEL}")
    
    # Validate configuration
    # if not all([QDRANT_URL, QDRANT_API_KEY, DEKA_KEY, DEKA_BASE]):
    #     print("❌ Missing required environment variables:")
    #     if not QDRANT_URL: print("  - QDRANT_URL")
    #     if not QDRANT_API_KEY: print("  - QDRANT_API_KEY")
    #     if not DEKA_KEY: print("  - DEKA_KEY")
    #     if not DEKA_BASE: print("  - DEKA_BASE_URL")
    #     return
    
    # Find all JSON files
    json_files = find_all_json_files()
    
    if not json_files:
        print("No JSON files found in OCR cache directory")
        return
    
    # Process files one by one
    print(f"\nStarting sequential processing of {len(json_files)} files...")
    print("This processes one file at a time to avoid mixing issues.")
    
    successful = 0
    failed = 0
    
    start_time = time.time()
    
    for i, file_info in enumerate(json_files, 1):
        print(f"\n[{i}/{len(json_files)}] Processing file...")
        
        success = process_single_json_file(
            file_info['path'],
            file_info['company'],
            file_info['filename']
        )
        
        if success:
            successful += 1
        else:
            failed += 1
    
    end_time = time.time()
    
    # Summary
    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total files processed: {len(json_files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {end_time - start_time:.2f} seconds")
    
    if failed > 0:
        print(f"\n⚠️  {failed} files failed. Check error messages above.")
    else:
        print(f"\n✅ All files processed successfully!")

if __name__ == "__main__":
    main()