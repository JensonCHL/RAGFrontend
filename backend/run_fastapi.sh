#!/bin/bash
# Install FastAPI requirements for n8n API

echo "Installing FastAPI requirements..."
pip install -r requirements_fastapi.txt

echo "Starting FastAPI server..."
uvicorn n8n_API_fastapi:app --host 0.0.0.0 --port 5000 --reload