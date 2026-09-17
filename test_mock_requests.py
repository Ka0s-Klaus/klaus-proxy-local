#!/usr/bin/env python3
"""Mock test requests through proxy (without API key)."""

import os
import json
import time
from pathlib import Path

def create_mock_request(idx: int):
    """Create a mock request file in captures/sent/."""

    captures_dir = Path.home() / ".klaus-proxy" / "captures" / "sent"
    captures_dir.mkdir(parents=True, exist_ok=True)

    # Mock request data
    request_data = {
        "timestamp": int(time.time() * 1000),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "method": "POST",
        "host": "api.anthropic.com",
        "path": f"/v1/messages",
        "status_code": 200,
        "pseudonymized": True,
        "blocked": False,
        "payload_size": 1024 + (idx * 100),
    }

    # Write to captures
    filename = captures_dir / f"request_{idx:04d}_{int(time.time()*1000)}.json"
    with open(filename, "w") as f:
        json.dump(request_data, f, indent=2)

    return filename

def main():
    """Create mock requests and display dashboard info."""

    print("🔌 Klaus Proxy Mock Test")
    print("=" * 60)
    print("Creating mock requests in captures/sent/...")
    print()

    # Create 5 mock requests
    for i in range(1, 6):
        filename = create_mock_request(i)
        print(f"✅ Created: {filename.name}")
        time.sleep(0.5)

    print()
    print("=" * 60)
    print("✅ Mock requests created!")
    print()
    print("📊 Check the dashboard at: http://localhost:9999")
    print()
    print("You should see:")
    print("  ✓ Total requests: 5")
    print("  ✓ Pseudonymized: 5")
    print("  ✓ Live traffic feed updating")
    print("  ✓ Vault coverage by type")
    print()
    print("💡 Tip: Refresh the dashboard to see updates")

if __name__ == "__main__":
    main()
