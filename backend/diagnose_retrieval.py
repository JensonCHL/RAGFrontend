#!/usr/bin/env python3
"""
Diagnostic Script to Check Qdrant Data Quality
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "DataStreamLit")

def diagnose_qdrant_quality():
    """Diagnose Qdrant data quality issues"""
    
    # Initialize client
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    print("🔍 DIAGNOSING QDRANT DATA QUALITY")
    print("=" * 50)
    
    # 1. Get total count
    try:
        collection_info = client.get_collection(QDRANT_COLLECTION)
        total_points = collection_info.points_count
        print(f"📊 Total points: {total_points}")
    except Exception as e:
        print(f"❌ Error getting collection info: {e}")
        return
    
    if total_points == 0:
        print("⚠️  No points found in collection!")
        return
    
    # 2. Sample some points
    print("\n📋 SAMPLING POINTS...")
    try:
        points, _ = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=min(20, total_points),
            with_payload=True,
            with_vectors=False
        )
        
        companies = {}
        documents = {}
        issues = []
        
        for point in points:
            payload = point.payload
            if not payload:
                issues.append(f"Point {point.id} has no payload")
                continue
                
            metadata = payload.get('metadata', {})
            content = payload.get('content', '')
            
            # Check required fields
            company = metadata.get('company', 'MISSING')
            source = metadata.get('source', 'MISSING')
            page = metadata.get('page', 'MISSING')
            
            # Track statistics
            companies[company] = companies.get(company, 0) + 1
            doc_key = f"{company}/{source}"
            documents[doc_key] = documents.get(doc_key, 0) + 1
            
            # Check for obvious issues
            if company == 'MISSING':
                issues.append(f"Point {point.id} missing company metadata")
            
            if source == 'MISSING':
                issues.append(f"Point {point.id} missing source metadata")
                
            # Check content quality
            if len(content) < 50:
                issues.append(f"Point {point.id} has very short content ({len(content)} chars)")
        
        # Report findings
        print(f"\n🏢 COMPANIES FOUND:")
        for company, count in sorted(companies.items()):
            print(f"  {company}: {count} points")
            
        print(f"\n📄 TOP DOCUMENTS:")
        sorted_docs = sorted(documents.items(), key=lambda x: x[1], reverse=True)
        for doc, count in sorted_docs[:10]:
            print(f"  {doc}: {count} points")
            
        if issues:
            print(f"\n⚠️  ISSUES FOUND:")
            for issue in issues[:10]:  # Show first 10
                print(f"  - {issue}")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more issues")
        else:
            print(f"\n✅ No obvious issues found in sample!")
            
    except Exception as e:
        print(f"❌ Error sampling points: {e}")
        import traceback
        traceback.print_exc()

def test_specific_query(query_text="purchase order"):
    """Test a specific query to check retrieval quality"""
    print(f"\n🔍 TESTING QUERY: '{query_text}'")
    print("=" * 50)
    
    try:
        from langchain_openai import OpenAIEmbeddings
        import os
        
        # Build embedder
        embedder = OpenAIEmbeddings(
            api_key=os.getenv("DEKA_KEY"),
            base_url=os.getenv("DEKA_BASE_URL"),
            model=os.getenv("EMBED_MODEL", "baai/bge-multilingual-gemma2"),
            model_kwargs={"encoding_format": "float"}
        )
        
        # Generate query vector
        query_vector = embedder.embed_query(query_text)
        print(f"✅ Generated query vector (dim: {len(query_vector)})")
        
        # Initialize client
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Search
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=5,
            with_payload=True
        )
        
        print(f"\n🎯 RETRIEVAL RESULTS ({len(results)} found):")
        for i, result in enumerate(results, 1):
            print(f"\n--- RESULT {i} (score: {result.score:.4f}) ---")
            if result.payload:
                metadata = result.payload.get('metadata', {})
                company = metadata.get('company', 'N/A')
                source = metadata.get('source', 'N/A')
                page = metadata.get('page', 'N/A')
                print(f"   Company: {company}")
                print(f"   Document: {source}")
                print(f"   Page: {page}")
                content = result.payload.get('content', '')[:200] + "..."
                print(f"   Content: {content}")
            else:
                print("   No payload")
                
    except Exception as e:
        print(f"❌ Error testing query: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_qdrant_quality()
    test_specific_query()