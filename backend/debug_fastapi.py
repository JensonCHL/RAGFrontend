
from fastapi import FastAPI
import uvicorn
import os

print("Step 1: Basic imports done")

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

print("Step 2: App created")

# Try imports one by one
try:
    print("Step 3: Importing core.config...")
    from core.config import get_project_root
    print("✅ core.config imported")
except Exception as e:
    print(f"❌ core.config failed: {e}")

try:
    print("Step 4: Importing core.clients...")
    from core.clients import qdrant_client
    print("✅ core.clients imported")
except Exception as e:
    print(f"❌ core.clients failed: {e}")

try:
    print("Step 5: Importing services.ocr_service...")
    from services.ocr_service import ocr_pdf_pages
    print("✅ services.ocr_service imported")
except Exception as e:
    print(f"❌ services.ocr_service failed: {e}")

try:
    print("Step 6: Importing services.embedding_service...")
    from services.embedding_service import generate_embeddings
    print("✅ services.embedding_service imported")
except Exception as e:
    print(f"❌ services.embedding_service failed: {e}")

try:
    print("Step 7: Importing services.qdrant_service...")
    from services.qdrant_service import ingest_to_qdrant
    print("✅ services.qdrant_service imported")
except Exception as e:
    print(f"❌ services.qdrant_service failed: {e}")

try:
    print("Step 8: Importing services.processing_pipeline...")
    from services.processing_pipeline import process_documents_pipeline
    print("✅ services.processing_pipeline imported")
except Exception as e:
    print(f"❌ services.processing_pipeline failed: {e}")

try:
    print("Step 9: Importing manual_indexer...")
    from manual_indexer import index_company_worker
    print("✅ manual_indexer imported")
except Exception as e:
    print(f"❌ manual_indexer failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Debug Server on 5002...")
    uvicorn.run(app, host="0.0.0.0", port=5002)
