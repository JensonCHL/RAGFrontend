# Backend API for Document Ingestion Dashboard

This Flask application provides API endpoints to retrieve company and document information from Qdrant.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure the `.env` file in the parent directory contains the Qdrant configuration:
   ```
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_api_key
   QDRANT_COLLECTION=your_collection_name
   ```

3. Create required indexes in Qdrant (important for filtering to work):
   ```bash
   python create_indexes.py
   ```

4. Run the application:
   ```bash
   python app.py
   ```

## API Endpoints

- `GET /api/companies` - Get all unique company names
- `GET /api/companies/<company_name>/documents` - Get all documents for a specific company
- `GET /health` - Health check endpoint

The application runs on port 5000 by default.