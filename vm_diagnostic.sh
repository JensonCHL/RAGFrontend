#!/bin/bash
# VM Diagnostic Script for n8n Chat Integration
# This script helps diagnose why chat works locally but not on VM

echo "=========================================="
echo "🔍 RAG VM Diagnostic Script"
echo "=========================================="
echo ""

# 1. Check if aiohttp is installed
echo "1️⃣ Checking Python dependencies..."
python3 -c "import aiohttp; print('✅ aiohttp version:', aiohttp.__version__)" 2>/dev/null || echo "❌ aiohttp NOT installed - Run: pip install aiohttp"
python3 -c "import fastapi; print('✅ fastapi installed')" 2>/dev/null || echo "❌ fastapi NOT installed"
python3 -c "import requests; print('✅ requests installed')" 2>/dev/null || echo "❌ requests NOT installed"
echo ""

# 2. Check network connectivity to n8n
echo "2️⃣ Testing network connectivity to n8n..."
N8N_URL="https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1"
echo "Testing: $N8N_URL"

# Test DNS resolution
echo "  - DNS resolution:"
nslookup n8n.cloudeka.ai 2>/dev/null || echo "    ⚠️  nslookup not available, trying ping..."
ping -c 1 n8n.cloudeka.ai >/dev/null 2>&1 && echo "    ✅ Can reach n8n.cloudeka.ai" || echo "    ❌ Cannot reach n8n.cloudeka.ai"
echo ""

# Test HTTPS connectivity
echo "  - HTTPS connectivity:"
curl -s -o /dev/null -w "    HTTP Status: %{http_code}\n" "$N8N_URL" 2>/dev/null || echo "    ❌ curl failed - check if curl is installed"
echo ""

# 3. Test actual webhook with payload
echo "3️⃣ Testing n8n webhook with test payload..."
curl -X POST "$N8N_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "chatInput": "test message from VM diagnostic",
    "sessionId": "diagnostic-test",
    "currentMessage": "test"
  }' \
  -w "\n  HTTP Status: %{http_code}\n" \
  -s -o /tmp/n8n_response.txt

echo "  Response saved to /tmp/n8n_response.txt"
echo "  Response preview:"
head -c 200 /tmp/n8n_response.txt 2>/dev/null || echo "    (no response)"
echo ""

# 4. Check firewall rules
echo "4️⃣ Checking firewall status..."
if command -v ufw >/dev/null 2>&1; then
    sudo ufw status | grep -E "Status|443" || echo "  UFW not active or port 443 not configured"
else
    echo "  UFW not installed"
fi
echo ""

# 5. Check if backend is running
echo "5️⃣ Checking if backend is running..."
ps aux | grep -E "BackendFastapi|uvicorn" | grep -v grep || echo "  ❌ Backend not running"
netstat -tlnp 2>/dev/null | grep ":5001" || ss -tlnp 2>/dev/null | grep ":5001" || echo "  ❌ Port 5001 not listening"
echo ""

# 6. Check environment variables
echo "6️⃣ Checking environment variables..."
if [ -f "/home/ubuntu/BRARAG/RAGFrontend/.env" ]; then
    echo "  ✅ .env file found"
    grep "N8N_WEBHOOK_URL" /home/ubuntu/BRARAG/RAGFrontend/.env || echo "  ⚠️  N8N_WEBHOOK_URL not found in .env"
else
    echo "  ❌ .env file not found at /home/ubuntu/BRARAG/RAGFrontend/.env"
fi
echo ""

# 7. Check SSL/TLS certificates
echo "7️⃣ Checking SSL/TLS connectivity..."
openssl s_client -connect n8n.cloudeka.ai:443 -servername n8n.cloudeka.ai </dev/null 2>/dev/null | grep -E "Verify return code" || echo "  ⚠️  SSL check failed"
echo ""

# 8. Test with Python directly
echo "8️⃣ Testing with Python aiohttp..."
python3 << 'PYTHON_TEST'
import asyncio
import aiohttp
import json

async def test_n8n():
    url = "https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1"
    payload = {
        "chatInput": "Python aiohttp test",
        "sessionId": "python-test",
        "currentMessage": "test"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                print(f"  ✅ Python aiohttp test successful!")
                print(f"  Status: {resp.status}")
                text = await resp.text()
                print(f"  Response length: {len(text)} bytes")
    except aiohttp.ClientError as e:
        print(f"  ❌ Python aiohttp error: {e}")
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")

asyncio.run(test_n8n())
PYTHON_TEST
echo ""

# 9. Check backend logs
echo "9️⃣ Checking recent backend logs (if available)..."
if [ -f "/var/log/rag-backend.log" ]; then
    echo "  Last 10 lines of backend log:"
    tail -10 /var/log/rag-backend.log
else
    echo "  ℹ️  No log file found at /var/log/rag-backend.log"
    echo "  Try checking: journalctl -u rag-backend -n 20"
fi
echo ""

# Summary
echo "=========================================="
echo "📊 DIAGNOSTIC SUMMARY"
echo "=========================================="
echo ""
echo "Common issues if chat doesn't work on VM:"
echo ""
echo "1. ❌ Missing aiohttp library"
echo "   Fix: pip install aiohttp"
echo ""
echo "2. ❌ Firewall blocking outbound HTTPS (port 443)"
echo "   Fix: sudo ufw allow out 443/tcp"
echo ""
echo "3. ❌ DNS resolution issues"
echo "   Fix: Check /etc/resolv.conf, add nameserver 8.8.8.8"
echo ""
echo "4. ❌ SSL certificate validation issues"
echo "   Fix: Update ca-certificates: sudo apt-get install ca-certificates"
echo ""
echo "5. ❌ Backend not loading .env file correctly"
echo "   Fix: Ensure .env is in correct location and readable"
echo ""
echo "6. ❌ Network proxy blocking requests"
echo "   Fix: Check HTTP_PROXY, HTTPS_PROXY environment variables"
echo ""
echo "=========================================="
