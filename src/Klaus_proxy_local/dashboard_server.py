"""Klaus Monitor Dashboard - FastAPI web server."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Klaus_proxy_local.monitor_data import DataSource


app = FastAPI(title="Klaus Monitor Dashboard")
data_source = DataSource()

# Store connected clients for WebSocket broadcasting
connected_clients = set()


@app.get("/")
async def get_dashboard():
    """Serve the dashboard HTML."""
    html_path = Path(__file__).parent / "dashboard.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)


@app.get("/api/stats")
async def get_stats():
    """Get current statistics."""
    stats = data_source.poll()
    requests = data_source.get_recent_requests(limit=15)

    return {
        "stats": {
            "total_requests": stats.total_requests,
            "pseudonymized_count": stats.pseudonymized_count,
            "blocked_count": stats.blocked_count,
            "vault_size": stats.vault_size,
            "detected_leaks": len(stats.detected_leaks),
            "requests_last_minute": stats.requests_last_minute,
            "uptime": str(stats.uptime),
            "last_audit_status": stats.last_audit_status,
            "last_audit_time": stats.last_audit_time.isoformat() if stats.last_audit_time else None,
        },
        "vault_types": dict(sorted(stats.vault_types.items(), key=lambda x: x[1], reverse=True)[:8]),
        "traffic": [
            {
                "time": req.timestamp.strftime("%H:%M:%S"),
                "client": f"{req.client_addr}:{req.client_port}" if req.client_addr and req.client_port else "unknown",
                "method": req.method,
                "endpoint": req.endpoint,
                "host": req.host,
                "status": req.status_code or "?",
                "pseudonymized": req.pseudonymized,
                "blocked": req.blocked,
            }
            for req in requests
        ],
        "detected_leaks": stats.detected_leaks[:5],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for live updates."""
    await websocket.accept()
    connected_clients.add(websocket)

    try:
        while True:
            # Poll data every 0.8 seconds
            stats = data_source.poll()
            requests = data_source.get_recent_requests(limit=15)

            data = {
                "stats": {
                    "total_requests": stats.total_requests,
                    "pseudonymized_count": stats.pseudonymized_count,
                    "blocked_count": stats.blocked_count,
                    "vault_size": stats.vault_size,
                    "detected_leaks": len(stats.detected_leaks),
                    "requests_last_minute": stats.requests_last_minute,
                    "uptime": str(stats.uptime),
                },
                "vault_types": dict(sorted(stats.vault_types.items(), key=lambda x: x[1], reverse=True)[:8]),
                "traffic": [
                    {
                        "time": req.timestamp.strftime("%H:%M:%S"),
                        "client": f"{req.client_addr}:{req.client_port}" if req.client_addr and req.client_port else "unknown",
                        "method": req.method,
                        "endpoint": req.endpoint[:40],
                        "host": req.host,
                        "status": req.status_code or "?",
                        "pseudonymized": req.pseudonymized,
                        "blocked": req.blocked,
                    }
                    for req in requests
                ],
            }

            await websocket.send_json(data)
            await asyncio.sleep(0.8)

    except Exception:
        pass
    finally:
        connected_clients.discard(websocket)


def main():
    """Launch the dashboard server."""
    print("🚀 Klaus Monitor Dashboard")
    print("=" * 60)
    print("📊 Open your browser: http://localhost:9999")
    print("=" * 60)
    print()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=9999,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
