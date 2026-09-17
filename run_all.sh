#!/bin/bash
# Klaus Proxy Local - Start proxy + dashboard in separate terminals

set -e

echo "🚀 Klaus Proxy Local v0.4.0"
echo "============================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python and pip are available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Install/upgrade package if in development mode
echo "📦 Installing Klaus Proxy Local..."
pip install -e . > /dev/null 2>&1 || {
    echo "❌ Failed to install package"
    exit 1
}

echo "✅ Package installed"
echo ""

# Start proxy in background
echo "Starting proxy on port 8899..."
echo "To use the proxy, run in another terminal:"
echo "  export HTTPS_PROXY=http://127.0.0.1:8899"
echo ""

claude-proxy &
PROXY_PID=$!

# Give proxy time to start
sleep 2

# Start dashboard server
echo "Starting dashboard on http://localhost:9999..."
echo ""

python3 -m Klaus_proxy_local.dashboard_server &
DASHBOARD_PID=$!

# Give dashboard time to start
sleep 1

# Open browser if possible
if command -v open &> /dev/null; then
    open http://localhost:9999
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:9999
fi

echo ""
echo -e "${GREEN}✅ Klaus Proxy Local is running!${NC}"
echo ""
echo -e "📊 Dashboard: ${BLUE}http://localhost:9999${NC}"
echo -e "🔌 Proxy:     ${BLUE}127.0.0.1:8899${NC}"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Cleanup on exit
trap "kill $PROXY_PID $DASHBOARD_PID 2>/dev/null; echo ''; echo 'Stopped.'" EXIT

# Wait for processes
wait
