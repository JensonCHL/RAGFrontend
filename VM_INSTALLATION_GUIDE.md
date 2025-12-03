# VM Installation Guide for RAG Application

## Prerequisites

This guide will help you install all necessary dependencies on your VM to ensure the chat functionality works correctly with n8n.

---

## 1. System Dependencies (Ubuntu/Debian)

Run these commands on your VM to install system-level dependencies:

```bash
# Update package list
sudo apt-get update

# Install Tesseract OCR (for PDF text extraction)
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Install Poppler (for PDF processing)
sudo apt-get install -y poppler-utils libpoppler-cpp-dev

# Install Python development headers (if not already installed)
sudo apt-get install -y python3-dev python3-pip

# Install PostgreSQL client libraries (for psycopg2)
sudo apt-get install -y libpq-dev

# Install build essentials (for compiling Python packages)
sudo apt-get install -y build-essential
```

### For CentOS/RHEL:

```bash
sudo yum install -y tesseract poppler-utils poppler-cpp-devel python3-devel postgresql-devel gcc
```

---

## 2. Python Dependencies

Navigate to your backend directory and install all Python packages:

```bash
cd /path/to/your/rag/backend

# Upgrade pip first
pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt
```

---

## 3. Verify Installation

Check if critical packages are installed:

```bash
# Check Python packages
pip list | grep -E "fastapi|uvicorn|aiohttp|psycopg2|qdrant|openai|langchain|passlib"

# Check system packages
tesseract --version
pdfinfo -v
```

---

## 4. Common Issues & Solutions

### Issue: Chat not sending to n8n

**Possible causes:**

1. **Missing `aiohttp`** - Required for async HTTP requests to n8n webhook
2. **Firewall blocking outbound connections** - Check if your VM can reach n8n
3. **Wrong n8n webhook URL** - Verify `N8N_WEBHOOK_URL` in `.env`

**Solution:**

```bash
# Reinstall aiohttp
pip install --force-reinstall aiohttp

# Test n8n connectivity
curl -X POST https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1 \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'
```

### Issue: `psycopg2` installation fails

**Solution:**

```bash
# Install PostgreSQL development libraries
sudo apt-get install -y libpq-dev python3-dev

# Or use binary version (already in requirements.txt)
pip install psycopg2-binary
```

### Issue: PDF processing fails

**Solution:**

```bash
# Ensure Tesseract and Poppler are installed
sudo apt-get install -y tesseract-ocr poppler-utils

# Test Tesseract
tesseract --version

# Test Poppler
pdfinfo -v
```

---

## 5. Environment Variables

Make sure your `.env` file has the correct n8n webhook URL:

```env
N8N_WEBHOOK_URL=https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1
```

---

## 6. Docker Installation (Recommended)

If using Docker, all dependencies are automatically installed:

```bash
# Build and start all services
docker-compose -f docker-compose.dev.yml up -d --build

# Check logs
docker-compose -f docker-compose.dev.yml logs -f backend
```

---

## 7. Testing the Setup

### Test Backend Health:

```bash
curl http://localhost:5001/health
```

### Test Chat Endpoint:

```bash
curl -X POST http://localhost:5001/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "conversation_id": "test-123",
    "user_id": "user-1",
    "timestamp": "2024-01-01T00:00:00Z",
    "messages": []
  }'
```

### Test n8n Connectivity:

```bash
curl -X POST https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1 \
  -H "Content-Type: application/json" \
  -d '{"chatInput": "test message", "sessionId": "test-user"}'
```

---

## 8. Key Libraries for n8n Integration

These are the critical libraries for chat functionality:

| Library            | Purpose               | Required For                 |
| ------------------ | --------------------- | ---------------------------- |
| `aiohttp`          | Async HTTP client     | Streaming responses from n8n |
| `fastapi`          | Web framework         | API endpoints                |
| `uvicorn`          | ASGI server           | Running FastAPI              |
| `psycopg2-binary`  | PostgreSQL driver     | Chat history storage         |
| `passlib`          | Password hashing      | User authentication          |
| `openai`           | OpenAI API client     | Deka AI integration          |
| `langchain-openai` | LangChain integration | Embeddings                   |
| `qdrant-client`    | Vector database       | Document search              |

---

## 9. Quick Reinstall Script

Save this as `install_dependencies.sh`:

```bash
#!/bin/bash
set -e

echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng poppler-utils libpoppler-cpp-dev libpq-dev python3-dev build-essential

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing Python dependencies..."
pip install -r backend/requirements.txt

echo "Verifying installation..."
pip list | grep -E "fastapi|uvicorn|aiohttp|psycopg2|qdrant|openai|langchain|passlib"

echo "Installation complete!"
```

Run it:

```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

---

## 10. Debugging Chat Issues

If chat still doesn't work after installation:

1. **Check backend logs:**

   ```bash
   # If running directly
   python backend/BackendFastapi.py

   # If using Docker
   docker-compose -f docker-compose.dev.yml logs -f backend
   ```

2. **Enable debug logging in chatBackend.py:**

   ```python
   logger.setLevel(logging.DEBUG)
   ```

3. **Test n8n webhook directly:**

   ```bash
   curl -v -X POST https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1 \
     -H "Content-Type: application/json" \
     -d '{"chatInput": "test", "sessionId": "test"}'
   ```

4. **Check firewall rules:**
   ```bash
   # Allow outbound HTTPS
   sudo ufw allow out 443/tcp
   ```

---

## Summary

The most likely cause of chat not working on your VM is **missing `aiohttp`** or **network connectivity issues**. The updated `requirements.txt` includes all necessary packages. Simply run:

```bash
pip install -r backend/requirements.txt
```

And verify n8n connectivity with:

```bash
curl https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1
```
