# VM Troubleshooting Guide - Chat Not Working

## Problem: Chat works locally but not on VM

Based on your `.env` file, here are the most likely causes and solutions:

---

## 🔍 **Most Likely Issues**

### 1. **Missing `aiohttp` Library** ⭐ (MOST COMMON)

**Symptom:** Backend returns 200 OK but doesn't actually call n8n

**Check:**

```bash
python3 -c "import aiohttp; print(aiohttp.__version__)"
```

**Fix:**

```bash
cd /home/ubuntu/BRARAG/RAGFrontend/backend
pip install aiohttp
# Or reinstall all requirements
pip install -r requirements.txt
```

**Then restart backend:**

```bash
# If running directly
pkill -f BackendFastapi
python3 backend/BackendFastapi.py

# If using systemd
sudo systemctl restart rag-backend
```

---

### 2. **Firewall Blocking Outbound HTTPS**

**Symptom:** Network timeout when trying to reach n8n

**Check:**

```bash
curl https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1
```

**Fix:**

```bash
# Allow outbound HTTPS
sudo ufw allow out 443/tcp

# Or disable firewall temporarily for testing
sudo ufw disable
# Test, then re-enable
sudo ufw enable
```

---

### 3. **DNS Resolution Issues**

**Symptom:** Cannot resolve n8n.cloudeka.ai

**Check:**

```bash
nslookup n8n.cloudeka.ai
ping n8n.cloudeka.ai
```

**Fix:**

```bash
# Add Google DNS to /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf
```

---

### 4. **SSL Certificate Issues**

**Symptom:** SSL verification errors in logs

**Check:**

```bash
openssl s_client -connect n8n.cloudeka.ai:443 -servername n8n.cloudeka.ai
```

**Fix:**

```bash
# Update CA certificates
sudo apt-get update
sudo apt-get install -y ca-certificates
sudo update-ca-certificates
```

---

### 5. **Backend Not Loading .env File**

**Symptom:** N8N_WEBHOOK_URL is empty or using default

**Check:**

```bash
# Verify .env location
ls -la /home/ubuntu/BRARAG/RAGFrontend/.env

# Check if backend can read it
cat /home/ubuntu/BRARAG/RAGFrontend/.env | grep N8N_WEBHOOK_URL
```

**Fix:**

```bash
# Ensure .env is in the correct location
# Your backend expects it at: /home/ubuntu/BRARAG/RAGFrontend/.env

# Make sure it's readable
chmod 644 /home/ubuntu/BRARAG/RAGFrontend/.env
```

---

### 6. **Corporate Proxy Blocking Requests**

**Symptom:** Requests timeout or get blocked

**Check:**

```bash
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

**Fix:**

```bash
# If you have a proxy, set it
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# Or unset if not needed
unset HTTP_PROXY
unset HTTPS_PROXY
```

---

## 🧪 **Quick Diagnostic Steps**

### Step 1: Run the diagnostic script

```bash
cd /home/ubuntu/BRARAG/RAGFrontend
bash vm_diagnostic.sh
```

### Step 2: Test n8n directly

```bash
curl -X POST https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1 \
  -H "Content-Type: application/json" \
  -d '{"chatInput": "test", "sessionId": "test"}'
```

**Expected:** You should get a response (even if it's an error, it means connectivity works)

### Step 3: Check backend logs

```bash
# If running with systemd
sudo journalctl -u rag-backend -f

# If running directly, check the terminal output
# Look for errors like:
# - "Error streaming from n8n"
# - "Network error"
# - "Connection refused"
```

### Step 4: Test with Python directly

```bash
python3 << 'EOF'
import asyncio
import aiohttp

async def test():
    url = "https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={"chatInput": "test"}) as resp:
            print(f"Status: {resp.status}")
            print(f"Response: {await resp.text()}")

asyncio.run(test())
EOF
```

---

## 🔧 **Most Likely Fix (90% of cases)**

Based on your symptoms, the issue is most likely **missing `aiohttp`**:

```bash
# Navigate to backend directory
cd /home/ubuntu/BRARAG/RAGFrontend/backend

# Install aiohttp
pip install aiohttp

# Restart backend
pkill -f BackendFastapi
python3 BackendFastapi.py
```

---

## 📝 **Verify Installation**

After fixing, verify everything works:

```bash
# 1. Check aiohttp is installed
python3 -c "import aiohttp; print('✅ aiohttp installed')"

# 2. Test n8n connectivity
curl https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1

# 3. Restart backend
pkill -f BackendFastapi
cd /home/ubuntu/BRARAG/RAGFrontend/backend
python3 BackendFastapi.py

# 4. Test chat from frontend
# Send a message and check backend logs for:
# "Sending chat request to n8n: conversation_id=..."
```

---

## 🆘 **Still Not Working?**

If none of the above works, collect this information:

```bash
# 1. Python version
python3 --version

# 2. Installed packages
pip list | grep -E "aiohttp|fastapi|requests"

# 3. Network test
curl -v https://n8n.cloudeka.ai/webhook/c533dbdd-48b0-464f-a114-6311b0727cd1

# 4. Backend logs (last 50 lines)
# Paste the output when you send a chat message

# 5. Environment check
cat /home/ubuntu/BRARAG/RAGFrontend/.env | grep N8N_WEBHOOK_URL
```

---

## ✅ **Success Indicators**

You'll know it's working when you see in the backend logs:

```
INFO:     127.0.0.1:xxxxx - "POST /api/chat/send HTTP/1.1" 200 OK
INFO:chatBackend:Sending chat request to n8n: conversation_id=xxx
```

And your n8n workflow receives the webhook!
