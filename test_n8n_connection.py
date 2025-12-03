#!/usr/bin/env python3
"""
Quick test script to verify n8n connectivity from VM
Run this on your VM to test if the backend can reach n8n
"""

import asyncio
import aiohttp
import json
import sys

N8N_WEBHOOK_URL = ""


async def test_n8n_connection():
    """Test n8n webhook connectivity"""

    print("=" * 80)
    print("🧪 Testing n8n Webhook Connectivity")
    print("=" * 80)
    print(f"\nWebhook URL: {N8N_WEBHOOK_URL}\n")

    payload = {
        "chatInput": "Test message from VM diagnostic script",
        "sessionId": "test-session-123",
        "currentMessage": "Hello from VM",
        "systemPrompt": "",
        "messages": [],
    }

    print("📤 Sending test payload:")
    print(json.dumps(payload, indent=2))
    print("\n" + "=" * 80)

    try:
        print("\n🔄 Creating aiohttp session...")
        async with aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            print("📡 Sending POST request to n8n...")
            async with session.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                print(f"\n✅ Response received!")
                print(f"   Status Code: {resp.status}")
                print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
                print(
                    f"   Transfer-Encoding: {resp.headers.get('Transfer-Encoding', 'N/A')}"
                )

                # Read response
                response_text = await resp.text()
                print(f"\n📥 Response body ({len(response_text)} bytes):")
                print("-" * 80)

                # Print first 500 chars of response
                if len(response_text) > 500:
                    print(response_text[:500] + "...")
                else:
                    print(response_text)

                print("-" * 80)

                if resp.status == 200:
                    print("\n✅ SUCCESS! n8n webhook is reachable and responding!")
                    return True
                else:
                    print(f"\n⚠️  WARNING: n8n returned status {resp.status}")
                    return False

    except aiohttp.ClientConnectorError as e:
        print(f"\n❌ CONNECTION ERROR: Cannot connect to n8n")
        print(f"   Error: {e}")
        print(f"\n   Possible causes:")
        print(f"   - Firewall blocking outbound HTTPS (port 443)")
        print(f"   - DNS resolution failure")
        print(f"   - Network connectivity issue")
        return False

    except aiohttp.ClientError as e:
        print(f"\n❌ CLIENT ERROR: {type(e).__name__}")
        print(f"   Error: {e}")
        return False

    except asyncio.TimeoutError:
        print(f"\n❌ TIMEOUT ERROR: Request took longer than 30 seconds")
        print(f"   Possible causes:")
        print(f"   - Network latency")
        print(f"   - n8n webhook is slow to respond")
        return False

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}")
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_with_streaming():
    """Test streaming response handling"""

    print("\n" + "=" * 80)
    print("🧪 Testing Streaming Response Handling")
    print("=" * 80)

    payload = {
        "chatInput": "Test streaming response",
        "sessionId": "test-stream",
        "currentMessage": "Test",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                is_streaming = (
                    "stream" in content_type
                    or "text/plain" in content_type
                    or resp.headers.get("Transfer-Encoding") == "chunked"
                )

                print(f"   Is streaming: {is_streaming}")
                print(f"   Content-Type: {content_type}")

                if is_streaming:
                    print("\n📡 Reading streaming chunks...")
                    chunk_count = 0
                    async for chunk in resp.content.iter_any():
                        if chunk:
                            chunk_count += 1
                            print(f"   Chunk {chunk_count}: {len(chunk)} bytes")
                            if chunk_count >= 5:
                                print("   (stopping after 5 chunks...)")
                                break
                else:
                    print("\n📄 Non-streaming response")

                print("\n✅ Streaming test complete!")
                return True

    except Exception as e:
        print(f"\n❌ Streaming test failed: {e}")
        return False


def main():
    print("\n" + "=" * 80)
    print("🚀 Starting n8n Connectivity Tests")
    print("=" * 80)

    # Test 1: Basic connectivity
    result1 = asyncio.run(test_n8n_connection())

    # Test 2: Streaming (only if basic test passed)
    if result1:
        result2 = asyncio.run(test_with_streaming())
    else:
        result2 = False
        print("\n⏭️  Skipping streaming test due to connection failure")

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"   Basic connectivity: {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"   Streaming support: {'✅ PASS' if result2 else '❌ FAIL'}")

    if result1 and result2:
        print("\n✅ ALL TESTS PASSED!")
        print("   Your VM can successfully communicate with n8n.")
        print("   The issue is likely in the backend code or configuration.")
        sys.exit(0)
    elif result1:
        print("\n⚠️  PARTIAL SUCCESS")
        print("   Basic connectivity works, but streaming may have issues.")
        sys.exit(1)
    else:
        print("\n❌ TESTS FAILED")
        print("   Your VM cannot reach n8n webhook.")
        print("   Check firewall, DNS, and network connectivity.")
        sys.exit(2)


if __name__ == "__main__":
    main()
