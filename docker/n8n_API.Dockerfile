# API Gateway Dockerfile for n8n FastAPI
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 5000

# Command to run the API gateway with uvicorn
CMD ["uvicorn", "n8n_API_fastapi:app", "--host", "0.0.0.0", "--port", "5000"]
