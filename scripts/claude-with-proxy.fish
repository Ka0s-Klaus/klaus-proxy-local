#!/usr/bin/env fish
# 🔐 Claude Code with Klaus Proxy Local (fish)
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

# Check if proxy is running
function check_proxy
    if not nc -z 127.0.0.1 8899 2>/dev/null
        echo "❌ Klaus Proxy not running!" >&2
        echo "" >&2
        echo "Please start the proxy in another terminal:" >&2
        echo "  claude-proxy" >&2
        echo "" >&2
        echo "Then come back here and try again." >&2
        exit 1
    end
end

# Route through proxy
set -x HTTP_PROXY "http://127.0.0.1:8899"
set -x HTTPS_PROXY "http://127.0.0.1:8899"
set -x http_proxy "http://127.0.0.1:8899"
set -x https_proxy "http://127.0.0.1:8899"

# Optionally check proxy is running (comment out to skip)
# check_proxy

# Execute claude with all arguments passed through
exec claude $argv
