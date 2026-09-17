#!/bin/bash
# Klaus Proxy Local - Start proxy and dashboard

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Klaus Proxy Local v0.4.0"
echo "============================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Install package
echo "📦 Installing Klaus Proxy Local..."
pip install -e . > /dev/null 2>&1 || {
    echo "❌ Failed to install"
    exit 1
}

# Try using tmux for cleaner terminal management
if command -v tmux &> /dev/null; then
    echo "✅ Using tmux for terminal management"
    echo ""

    # Create new tmux session
    SESSION="klaus-$(date +%s)"
    tmux new-session -d -s "$SESSION" -x 120 -y 30

    # Window 1: Proxy
    tmux send-keys -t "$SESSION:0" "cd '$PROJECT_DIR' && claude-proxy" Enter
    tmux rename-window -t "$SESSION:0" "proxy"

    # Window 2: Dashboard
    sleep 2
    tmux new-window -t "$SESSION" -n "dashboard"
    tmux send-keys -t "$SESSION:1" "cd '$PROJECT_DIR' && python3 -m Klaus_proxy_local.dashboard_server" Enter

    sleep 1

    echo ""
    echo "📊 Dashboard: http://localhost:9999"
    echo "🔌 Proxy:     127.0.0.1:8899"
    echo ""
    echo "Tmux session: $SESSION"
    echo "Attach with:  tmux attach -t $SESSION"
    echo ""
else
    # Fallback: simple background processes
    echo "Starting services in background..."
    echo ""

    claude-proxy &
    PROXY_PID=$!

    sleep 2

    python3 -m Klaus_proxy_local.dashboard_server &
    DASHBOARD_PID=$!

    sleep 1

    # Open browser
    if command -v open &> /dev/null; then
        open http://localhost:9999
    fi

    echo ""
    echo "✅ Services running:"
    echo "📊 Dashboard: http://localhost:9999 (proxy: $PROXY_PID, dashboard: $DASHBOARD_PID)"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""

    # Wait
    trap "kill $PROXY_PID $DASHBOARD_PID 2>/dev/null; echo ''; echo 'Stopped'" EXIT
    wait
fi
