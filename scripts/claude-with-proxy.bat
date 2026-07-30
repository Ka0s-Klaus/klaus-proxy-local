@echo off
REM 🔐 Claude Code with Klaus Proxy Local (CMD)
REM
REM Usage:
REM   claude-with-proxy.bat "your question"
REM   claude-with-proxy.bat read C:\path\to\file
REM
REM This wrapper routes Claude Code through the local proxy at 127.0.0.1:8899
REM Make sure to start the proxy first in another terminal:
REM   claude-proxy
REM
REM The proxy pseudonymizes sensitive data before it leaves your machine.

REM Route through proxy
set HTTP_PROXY=http://127.0.0.1:8899
set HTTPS_PROXY=http://127.0.0.1:8899
set http_proxy=http://127.0.0.1:8899
set https_proxy=http://127.0.0.1:8899

REM Execute claude with all arguments passed through
claude %*
