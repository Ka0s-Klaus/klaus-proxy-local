#!/usr/bin/env pwsh
# 🔐 Claude Code with Klaus Proxy Local (PowerShell)
#
# Usage:
#   .\claude-with-proxy.ps1 "your question"
#   .\claude-with-proxy.ps1 read /path/to/file
#
# Or as a function in your PowerShell profile:
#   function claude-with-proxy { & 'path/to/claude-with-proxy.ps1' @args }
#
# This wrapper routes Claude Code through the local proxy at 127.0.0.1:8899
# Make sure to start the proxy first in another terminal:
#   claude-proxy
#
# The proxy pseudonymizes sensitive data before it leaves your machine.

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

# Function to check if proxy is running
function Test-ProxyRunning {
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $socket.Connect("127.0.0.1", 8899)
        $socket.Close()
        return $true
    }
    catch {
        return $false
    }
}

# Route through proxy
$env:HTTP_PROXY = "http://127.0.0.1:8899"
$env:HTTPS_PROXY = "http://127.0.0.1:8899"
$env:http_proxy = "http://127.0.0.1:8899"
$env:https_proxy = "http://127.0.0.1:8899"

# Optionally check proxy is running (uncomment to enable)
# if (-not (Test-ProxyRunning)) {
#     Write-Host "❌ Klaus Proxy not running!" -ForegroundColor Red
#     Write-Host ""
#     Write-Host "Please start the proxy in another terminal:" -ForegroundColor Yellow
#     Write-Host "  claude-proxy" -ForegroundColor Cyan
#     Write-Host ""
#     Write-Host "Then come back here and try again." -ForegroundColor Yellow
#     exit 1
# }

# Execute claude with all arguments passed through
& claude @Arguments
