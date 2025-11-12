#!/usr/bin/env python3
"""
Simple Debug Script for Processing OCR Cache Files

This script processes OCR cache JSON files sequentially and inserts them into Qdrant
using the exact same methods as the main application.

Usage:
    cd backend
    python process_ocr_cache_debug.py
"""

import os
import sys
import json
import time
import hashlib
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Import required functions from app.py
try:
    from app import (
        build_meta_header,
        generate_document_id,
        build_embedder,
        qdrant_client,
        QDRANT_COLLECTION
    )
    print("✅ Successfully imported required modules")
    print(f"Using Qdrant collection: {QDRANT_COLLECTION}")
    print(f"Using embedding model: {os.getenv('EMBED_MODEL', 'baai/bge-multilingual-gemma2')}")
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    sys.exit(1)

def generate_embeddings_simple(chunks_data, doc_id):
    """Use the existing generate_embeddings function from app.py"""
    try:
        print("  Generating embeddings using existing function...")
        
        # Import the existing function
        from app import generate_embeddings
        
        points_data = []
        embedding_count = 0
        
        # Process embeddings (collect results from generator)
        for embed_update in generate_embeddings(chunks_data, doc_id):
            # print(f"    Embedding update: {embed_update.strip()}")
            try:
                update_data = json.loads(embed_update.strip())
                if update_data.get("status") == "embedding_completed":
                    points_data = update_data.get("points_data", [])
                    embedding_count = len(points_data)
            except json.JSONDecodeError:
                pass  # Ignore non-JSON updates
        
        print(f"  ✅ Generated {embedding_count} embeddings")
        return points_data
        
    except Exception as e:
        print(f"  ❌ Error in generate_embeddings_simple: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def ingest_to_qdrant_simple(points_data, company_name, source_name):
    """Use the existing ingest_to_qdrant function from app.py"""
    try:
        print(f"  Ingesting {len(points_data)} points to Qdrant using existing function...")
        
        # Import the existing function
        from app import ingest_to_qdrant
        
        ingestion_count = 0
        
        # Process ingestion (collect results from generator)
        for ingest_update in ingest_to_qdrant(points_data, company_name, source_name):
            print(f"    Ingestion update: {ingest_update.strip()}")
            try:
                update_data = json.loads(ingest_update.strip())
                if update_data.get("status") == "ingestion_completed":
                    ingestion_count = update_data.get("total_points", 0)
            except json.JSONDecodeError:
                pass  # Ignore non-JSON updates
                
        print(f"  ✅ Successfully ingested {ingestion_count} points to Qdrant")
        return ingestion_count
        
    except Exception as e:
        print(f"  ❌ Error in ingest_to_qdrant_simple: {str(e)}")
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
        
        # 2. Generate document ID (same as in app.py)
        print("2. Generating document ID...")
        doc_id = generate_document_id(company_name, file_name)
        print(f"   ✅ Document ID: {doc_id}")
        
        # 3. Create chunks with metadata (same as in app.py)
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
        
        # 4. Generate embeddings
        print("4. Generating embeddings...")
        points_data = generate_embeddings_simple(chunks_data, doc_id)
        if not points_data:
            print("   ❌ Failed to generate embeddings")
            return False
        print(f"   ✅ Generated {len(points_data)} embeddings")
        
        # 5. Ingest to Qdrant
        print("5. Ingesting to Qdrant...")
        ingested_count = ingest_to_qdrant_simple(points_data, company_name, file_name)
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
    print("Sequential OCR Cache Processor for Debugging")
    print("=" * 50)
    
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