# 🚀 Klaus Proxy Local - Deployment Runbook

## Pre-Deployment Checklist

- [ ] All tests passing (459/462 for v0.3.0)
- [ ] Security scan clean (Bandit, pip-audit)
- [ ] Documentation updated
- [ ] Changelog reviewed
- [ ] Git tags created
- [ ] PyPI credentials ready

## Installation from Source

```bash
# Clone and setup
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local

# Setup Python 3.13+
python3.13 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install production
pip install -e .

# Install development (if contributing)
pip install -e ".[dev]"
```

## Installation from PyPI

```bash
# Standard installation
pip install Klaus-proxy-local

# Specific version
pip install Klaus-proxy-local==0.3.0

# With all extras
pip install "Klaus-proxy-local[dev]"
```

## Quick Start

```bash
# Terminal 1: Start proxy (auto-setup on first run)
claude-proxy

# Terminal 2: Use Claude Code with proxy
HTTPS_PROXY=http://127.0.0.1:8899 \
NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca.pem \
claude "your prompt here"
```

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_CAPTURE_HOSTS` | Hosts to audit (comma-sep) | `api.anthropic.com,llm.tools.cloud.*` |
| `ANTHROPIC_CAPTURE_DIR` | Capture output directory | `./captures/` |
| `ANTHROPIC_PSEUDO_ENABLE` | Enable pseudonymization | `1` |
| `ANTHROPIC_PSEUDO_SALT` | Vault salt (REQUIRED for prod) | Generated auto on first run |

### First Run (Auto-Setup)

1. `claude-proxy` creates `~/.klaus-proxy/config.json`
2. Auto-generates TLS certificates in `~/.mitmproxy/`
3. Generates `ANTHROPIC_PSEUDO_SALT` in `~/.klaus-proxy/.salt`
4. Sets up shell integration for bash/zsh/fish
5. Ready for use

## Troubleshooting

### Port 8899 Already in Use

```bash
# Find what's using it
lsof -i :8899

# Kill the process (macOS/Linux)
kill -9 <PID>

# Use different port (environment variable)
ANTHROPIC_PROXY_PORT=9000 claude-proxy
```

### SSL Certificate Issues

```bash
# Regenerate certificates
rm -rf ~/.mitmproxy/
claude-proxy  # Will regenerate

# Or manually
mkdir -p ~/.mitmproxy
mitmproxy --version  # Initialize
```

### Lost Configuration

```bash
# Reset everything (WARNING: will regenerate)
rm -rf ~/.klaus-proxy/ ~/.mitmproxy/
claude-proxy  # Fresh setup
```

## Verification

```bash
# Check proxy is running
curl -x http://127.0.0.1:8899 https://api.anthropic.com

# Check captures are being made
ls ~/.klaus-proxy/../captures/

# Verify salt exists
cat ~/.klaus-proxy/.salt
```

## CI/CD Deployment

### GitHub Actions (Automatic)

```yaml
# In your workflow:
- name: Run Klaus Proxy Tests
  env:
    ANTHROPIC_PSEUDO_SALT: ${{ secrets.ANTHROPIC_PSEUDO_SALT }}
  run: pytest --tb=short
```

### Docker (Future)

```dockerfile
FROM python:3.13-slim
RUN pip install Klaus-proxy-local
ENTRYPOINT ["claude-proxy"]
```

## Rollback Procedure

If issues detected after deployment:

```bash
# Rollback to v0.2.0
pip install Klaus-proxy-local==0.2.0

# Check version
python -c "import Klaus_proxy_local; print(Klaus_proxy_local.__version__)"

# Report issue
# https://github.com/Ka0s-Klaus/klaus-proxy-local/issues
```

## Support

- **Issues:** GitHub Issues
- **Security:** security@example.com
- **Discussions:** GitHub Discussions
