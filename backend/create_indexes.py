"""
Script to create required indexes in Qdrant for the Document Ingestion Web App
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

def create_indexes():
    # Load environment variables
    load_dotenv()
    
    # Qdrant configuration
    QDRANT_URL = os.getenv('QDRANT_URL')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION')
    
    if not all([QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION]):
        print("Error: Missing Qdrant configuration in .env file")
        print("Please ensure QDRANT_URL, QDRANT_API_KEY, and QDRANT_COLLECTION are set")
        return
    
    try:
        # Initialize Qdrant client
        print("Connecting to Qdrant...")
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )
        
        # Test connection and check if collection exists
        print("Testing connection...")
        collections = client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if QDRANT_COLLECTION not in collection_names:
            print(f"Warning: Collection '{QDRANT_COLLECTION}' not found in Qdrant")
            print("Available collections:", collection_names)
            return
        
        print("Connection successful!")
        print(f"Collection '{QDRANT_COLLECTION}' found")
        
        # Create keyword index on metadata.company field
        print("Creating index on metadata.company field...")
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="metadata.company",
            field_schema=PayloadSchemaType.KEYWORD
        )
        print("[OK] Index on metadata.company created successfully")
        
        # Create keyword index on metadata.source field
        print("Creating index on metadata.source field...")
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="metadata.source",
            field_schema=PayloadSchemaType.KEYWORD
        )
        print("[OK] Index on metadata.source created successfully")
        
        print("\n[SUCCESS] All indexes created successfully!")
        print("Your Flask API should now work without indexing errors.")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check that your Qdrant credentials in .env are correct")
        print("2. Ensure the collection exists in Qdrant")
        print("3. Verify network connectivity to your Qdrant instance")

if __name__ == "__main__":
    create_indexes()