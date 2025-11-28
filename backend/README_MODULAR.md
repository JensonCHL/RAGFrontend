# RAG System Backend - Modular Architecture

## 🎯 Overview

This backend has been refactored into a **modular architecture** that supports both **Flask** and **FastAPI** frameworks using the same core business logic.

## 📁 Project Structure

```
backend/
├── core/                      # Core functionality
│   ├── __init__.py
│   ├── config.py             # Configuration & environment variables
│   ├── clients.py            # Qdrant & Deka AI clients
│   └── state.py              # Processing state management (RAM-only)
│
├── services/                  # Business logic services
│   ├── __init__.py
│   ├── ocr_service.py        # OCR processing functions
│   ├── embedding_service.py  # Embedding generation
│   └── qdrant_service.py     # Qdrant operations
│
├── app.py                    # Flask application
├── app_fastapi.py            # FastAPI application
├── start_fastapi.py          # FastAPI startup script
│
├── manual_indexer.py         # Manual indexing worker
├── db_utils.py               # Database utilities
├── n8n_API_fastapi.py        # N8N API Gateway
│
└── ocr_cache/                # OCR cache directory
```

## 🚀 Running the Applications

### Flask Application (Port 5000)
```bash
python app.py
```

### FastAPI Application (Port 5001)
```bash
python start_fastapi.py
```

Or directly:
```bash
uvicorn app_fastapi:app --reload --port 5001
```

## 📚 API Documentation

### Flask
- No auto-generated docs
- Endpoints available at `http://localhost:5000/api/*`

### FastAPI
- **Swagger UI**: `http://localhost:5001/docs`
- **ReDoc**: `http://localhost:5001/redoc`
- **OpenAPI JSON**: `http://localhost:5001/openapi.json`

## 🔧 Core Modules

### `core/config.py`
- Environment variable loading
- Configuration constants
- Directory paths
- Helper functions

### `core/clients.py`
- Qdrant client initialization
- Deka AI client initialization
- Client connection status

### `core/state.py`
- RAM-only processing state storage
- State management functions
- SSE notification system
- Thread-safe operations

## 🛠️ Services

### `services/ocr_service.py`
- PDF page OCR processing
- Image to base64 conversion
- Text cleaning
- Progress tracking
- Cache management

### `services/embedding_service.py`
- Embedding generation
- Batch processing
- Vector creation
- Progress tracking

### `services/qdrant_service.py`
- Document ingestion to Qdrant
- Batch uploads
- Collection management
- Data update notifications

## 🎨 Benefits of Modular Architecture

### ✅ Code Reusability
- Same business logic for Flask and FastAPI
- No code duplication
- Easy to maintain

### ✅ Separation of Concerns
- Core logic separated from API layer
- Easy to test individual components
- Clear responsibility boundaries

### ✅ Flexibility
- Can switch between Flask and FastAPI
- Easy to add new frameworks
- Framework-agnostic business logic

### ✅ Maintainability
- Smaller, focused files
- Easy to locate and fix bugs
- Clear module dependencies

## 🔄 Migration Path

### From Monolithic to Modular

**Before:**
- Single `app.py` with 1916 lines
- All logic mixed together
- Hard to test and maintain

**After:**
- Modular structure with clear separation
- `app.py` reduced to ~1251 lines
- Reusable core and services
- Both Flask and FastAPI supported

## 📊 State Management

### RAM-Only Storage
- Processing states stored in memory
- **Lost on server restart** (by design)
- Maximum performance (no disk I/O)
- Clean filesystem

### Trade-offs
- ✅ **Pros**: Fast, simple, no file management
- ⚠️ **Cons**: States lost on restart
- 💡 **Rationale**: Processing states are transient; completed data is in Qdrant

## 🔐 Environment Variables

Required in `.env`:
```env
# Qdrant Configuration
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_api_key
QDRANT_COLLECTION=your_collection_name

# Deka AI Configuration
DEKA_BASE_URL=your_deka_url
DEKA_KEY=your_deka_key
EMBED_MODEL=baai/bge-multilingual-gemma2

# Processing Configuration
BATCH_SIZE=64
```

## 🧪 Testing

### Test Core Modules
```bash
python -c "from core import config, clients, state; print('✅ All core modules loaded')"
```

### Test Services
```bash
python -c "from services import ocr_service, embedding_service, qdrant_service; print('✅ All services loaded')"
```

### Test Flask App
```bash
python -c "from app import app; print('✅ Flask app loaded')"
```

### Test FastAPI App
```bash
python -c "from app_fastapi import app; print('✅ FastAPI app loaded')"
```

## 📝 API Endpoints

### Common Endpoints (Both Flask & FastAPI)

#### Companies
- `GET /api/companies` - List all companies
- `GET /api/companies/{company_name}/documents` - Get company documents
- `DELETE /api/companies/{company_name}` - Delete company data

#### Documents
- `GET /api/company-documents` - Get all companies with documents
- `GET /api/qdrant-data` - Get all Qdrant data
- `DELETE /api/documents` - Delete specific document

#### Processing
- `POST /api/process-documents` - Process documents
- `GET /api/document-processing-states` - Get processing states
- `GET /api/processing-queue-status` - Get queue status

#### Events
- `GET /events/processing-updates` - SSE for real-time updates

#### Health
- `GET /health` - Health check

## 🎯 Next Steps

1. **Expand FastAPI endpoints** - Add remaining endpoints from Flask
2. **Add authentication** - Implement API key or JWT auth
3. **Add rate limiting** - Protect against abuse
4. **Add caching** - Redis for performance
5. **Add monitoring** - Prometheus/Grafana
6. **Add tests** - Unit and integration tests

## 📖 Documentation

- Flask: Traditional web framework, synchronous
- FastAPI: Modern framework, async, auto-docs
- Both use the same core business logic
- Choose based on your needs and preferences

## 🤝 Contributing

When adding new features:
1. Add core logic to appropriate service module
2. Update both Flask and FastAPI endpoints
3. Test both implementations
4. Update this README

## 📄 License

[Your License Here]

---

**Built with ❤️ using modular architecture principles**
