#!/usr/bin/env bash
# 🔐 Claude Code with Klaus Proxy Local (bash/zsh)
#
# Usage:
#   claude-with-proxy "your question"
#   claude-with-proxy read /path/to/file
#
# This wrapper routes Claude Code through the local proxy at 127.0.0.1:8899
# Make sure to start the proxy first in another terminal:
#   claude-proxy
#
# The proxy pseudonymizes sensitive data before it leaves your machine.

set -e

# Check if proxy is running
check_proxy() {
    if ! nc -z 127.0.0.1 8899 2>/dev/null; then
        cat >&2 << 'EOF'
❌ Klaus Proxy not running!

Please start the proxy in another terminal:
  claude-proxy

Then come back here and try again.
EOF
        exit 1
    fi
}

# Route through proxy
export HTTP_PROXY="http://127.0.0.1:8899"
export HTTPS_PROXY="http://127.0.0.1:8899"
export http_proxy="http://127.0.0.1:8899"
export https_proxy="http://127.0.0.1:8899"

# Optionally check proxy is running (comment out to skip)
# check_proxy

# Execute claude with all arguments passed through
exec claude "$@"
