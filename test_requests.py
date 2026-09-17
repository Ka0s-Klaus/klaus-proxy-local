#!/usr/bin/env python3
"""Test script to send requests through Klaus Proxy."""

import os
import sys
import time
import anthropic

def test_proxy():
    """Send test requests through the proxy."""
    
    # Set proxy
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:8899"
    
    # Verify we have API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        print("   Set it with: export ANTHROPIC_API_KEY=your_key")
        sys.exit(1)
    
    print("🔌 Testing Klaus Proxy with Anthropic API")
    print("=" * 60)
    print(f"Proxy: http://127.0.0.1:8899")
    print(f"API Key: {api_key[:10]}...")
    print("=" * 60)
    print()
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompts = [
        "What is the capital of France?",
        "Tell me a short joke",
        "How many planets are in our solar system?",
        "What is 2+2?",
        "Say hello in Spanish",
    ]
    
    for i, prompt in enumerate(prompts, 1):
        try:
            print(f"📤 Request {i}/5: {prompt[:40]}...")
            
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response = message.content[0].text[:50]
            print(f"   ✅ Response: {response}...")
            print()
            
            # Small delay between requests
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            print()

if __name__ == "__main__":
    test_proxy()
    
    print("=" * 60)
    print("✅ Test complete!")
    print()
    print("Check the dashboard at: http://localhost:9999")
    print("You should see:")
    print("  - Total requests: 5")
    print("  - Live traffic with all requests")
    print("  - Vault coverage with pseudonymized data")
