# Troubleshooting Guide

## Common Issues

### Proxy won't start

**Error:** `Address already in use` or `Port 8899 in use`

```bash
# Check what's using port 8899
lsof -i :8899
# Output: mitmdump 12345 user IPv4 TCP localhost:8899

# Kill the process
kill -9 12345

# Or use a different port
export ANTHROPIC_PROXY_PORT=9000
claude-proxy
```

**Error:** `Permission denied` on macOS/Linux

```bash
# Check permissions on .mitmproxy directory
ls -la ~/.mitmproxy/

# Fix if needed
chmod 700 ~/.mitmproxy/
chmod 600 ~/.mitmproxy/mitmproxy-ca.pem
```

### Certificate errors

**Error:** `certificate verify failed` or `CERTIFICATE_VERIFY_FAILED`

```bash
# The CA certificate isn't being used. Regenerate:
rm -rf ~/.mitmproxy/
claude-proxy
# Will auto-regenerate and output the path

# Then make sure you're setting NODE_EXTRA_CA_CERTS
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca.pem
```

**For Docker/containers:**

```bash
# Install the cert in the system store instead
docker exec <container> cp ~/.mitmproxy/mitmproxy-ca.pem /usr/local/share/ca-certificates/
docker exec <container> update-ca-certificates
```

### Claude Code not connecting

**Symptoms:** Proxy running, but Claude Code still talks directly to API

**Checks:**

```bash
# 1. Is proxy actually listening?
curl -x http://127.0.0.1:8899 https://api.anthropic.com
# Should return: "HTTP/1.0 200"

# 2. Are environment variables set?
echo $HTTPS_PROXY
echo $NODE_EXTRA_CA_CERTS
# Should show the proxy URL and cert path

# 3. Is Claude Code using them?
env | grep -i proxy
# Should see HTTPS_PROXY

# 4. Restart Claude Code after setting env vars
# (environment changes don't apply to already-running processes)
```

### Missing captures

**Symptom:** `~/.klaus-proxy/../captures/` is empty or doesn't exist

```bash
# Check config
cat ~/.klaus-proxy/config.json | jq '.capture_dir'

# Manually create if missing
mkdir -p ~/.klaus-proxy/../captures/

# Verify proxy is actually capturing
curl -x http://127.0.0.1:8899 -s https://api.anthropic.com | head

# Check proxy logs in Terminal 1
# (should show capture lines like "[anthropic-capture] POST /v1/messages")
```

### Vault corruption or sync issues

**Symptom:** Pseudonyms don't reverse correctly, or vault seems out of sync

```bash
# Check vault file integrity
cat ~/.klaus-proxy/../captures/.pseudonym_vault.json | jq '.real_to_pseudo | length'
# Should return a number > 0 if data exists

# Reset vault (will lose mapping, but subsequent runs recreate it)
rm ~/.klaus-proxy/../captures/.pseudonym_vault.json
claude-proxy
# Will auto-recreate on next request
```

### High memory usage

**Symptom:** Klaus Proxy consuming > 500MB RAM

```bash
# 1. Check how many captures exist
find ~/.klaus-proxy/../captures/ -type f | wc -l
# If > 10000 files, clean up:

# 2. Clean old captures
find ~/.klaus-proxy/../captures/ -mtime +7 -delete
# Removes captures older than 7 days

# 3. Or wipe everything and start fresh
rm -rf ~/.klaus-proxy/../captures/*
```

### Tests failing with "ANTHROPIC_PSEUDO_SALT not found"

**In CI/CD:** Set the environment variable before running tests

```bash
export ANTHROPIC_PSEUDO_SALT="test-salt-value-here-32-chars"
pytest
```

**In GitHub Actions:**

```yaml
- name: Run tests
  env:
    ANTHROPIC_PSEUDO_SALT: ${{ secrets.ANTHROPIC_PSEUDO_SALT }}
  run: pytest
```

### Shell integration not working

**Symptom:** `claude-with-proxy` command not found

```bash
# Re-run setup
klaus-setup

# Or manually add to your shell:
alias claude-with-proxy='HTTPS_PROXY=http://127.0.0.1:8899 \
  NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca.pem claude'

# For fish shell:
funcsave claude-with-proxy
```

## Performance Tuning

### Slow pseudonymization

Klaus Proxy should add < 5ms latency. If slower:

```bash
# 1. Check vault size
du -h ~/.klaus-proxy/../captures/.pseudonym_vault.json

# 2. If large (> 10MB), the vault is growing too much
# Solution: archive old captures
tar czf captures-archive-$(date +%Y%m%d).tar.gz ~/.klaus-proxy/../captures/
rm -rf ~/.klaus-proxy/../captures/*

# 3. Restart proxy
claude-proxy
```

### Slow file scanning

When using `klaus-scan`, it can be slow on large codebases:

```bash
# Only scan specific directories
klaus-scan --path ./src --path ./config

# Skip large directories
klaus-scan --exclude node_modules --exclude .git

# Or set in config.json
{
  "scan_exclude_paths": [".git", "node_modules", ".venv", "__pycache__"]
}
```

## Getting Help

If none of these fixes work:

1. **Check the proxy logs** (Terminal 1 where `claude-proxy` runs)
   - Look for error lines (red text)
   - Note the timestamp and exact error

2. **Gather debug info:**
   ```bash
   python -c "import sys; print(sys.version)"
   pip show Klaus-proxy-local | grep Version
   echo $HTTPS_PROXY
   ls -la ~/.mitmproxy/ ~/.klaus-proxy/
   ```

3. **File an issue:**
   - https://github.com/Ka0s-Klaus/klaus-proxy-local/issues
   - Include proxy logs and debug info above

4. **Security concern?**
   - Email: security@example.com
   - See SECURITY.md for responsible disclosure
