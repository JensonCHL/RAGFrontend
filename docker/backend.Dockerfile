# Backend Dockerfile for FastAPI backend
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OCR and PDF processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libpoppler-cpp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 5001

# Command to run the backend with uvicorn
CMD ["uvicorn", "BackendFastapi:app", "--host", "0.0.0.0", "--port", "5001", "--reload", "--log-level", "debug"]
