# Document Ingestion Web App

This is a Next.js project for managing document ingestion before accessing the RAG system.

## Project Structure

- `/src/app/dashboard` - Main dashboard frontend
- `/src/components` - Reusable UI components
- `/src/app/api` - Next.js API routes for file operations
- `/backend` - Flask API for Qdrant data retrieval
- `/knowledge` - Persistent storage for uploaded files

## Getting Started

### Prerequisites

1. Node.js and npm
2. Python 3.7+
3. Access to Qdrant database (configured in .env)

### Running the Application

You need to run both the frontend and backend services:

1. **Start the Flask backend** (handles Qdrant data):
   ```bash
   # Windows
   run_backend.bat
   
   # Or manually:
   cd backend
   pip install -r requirements.txt
   python app.py
   ```

2. **Start the Next.js frontend**:
   ```bash
   # Windows
   run_frontend.bat
   
   # Or manually:
   npm run dev
   ```

The application will be available at:
- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:5000](http://localhost:5000)

### Features

1. **File Upload**:
   - Drag and drop PDF contracts
   - Create companies and upload documents
   - Files stored in `/knowledge` directory

2. **Document Management**:
   - View uploaded companies and their contracts
   - Delete individual files or entire companies
   - Direct file system operations

3. **Processed Documents**:
   - View companies and documents from Qdrant
   - Expand companies to see associated documents
   - Real-time data from backend processing

## Development

This project uses:
- Next.js 16 with App Router
- TypeScript
- Tailwind CSS v4
- Flask for backend API
- Qdrant client for vector database operations

You can start editing the page by modifying `app/dashboard/page.tsx`. The page auto-updates as you edit the file.
"# RAGFrontend" 
