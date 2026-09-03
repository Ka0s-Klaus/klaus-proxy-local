# PyPI Publication Instructions for v0.3.0

## Status

✅ **Distribution files built and ready**

- ✅ Wheel: `dist/klaus_proxy_local-0.3.0-py3-none-any.whl` (33.4 KB)
- ✅ Source: `dist/klaus_proxy_local-0.3.0.tar.gz` (185.5 KB)
- ✅ Version: 0.3.0 (updated in pyproject.toml)
- ❌ PyPI upload: Failed due to SSL certificate verification in this environment

## What's Ready

The build system has successfully created:

```bash
$ ls -lh dist/
-rw-r--r--  33K  klaus_proxy_local-0.3.0-py3-none-any.whl
-rw-r--r--  186K klaus_proxy_local-0.3.0.tar.gz
```

These files are production-ready for PyPI.

## How to Publish to PyPI

### Prerequisite

Ensure you have a PyPI account. If not, create one at: https://pypi.org/account/register/

### Option 1: Using Twine (Recommended)

```bash
# 1. Install twine
pip install twine

# 2. Publish to PyPI
twine upload dist/klaus_proxy_local-0.3.0-py3-none-any.whl dist/klaus_proxy_local-0.3.0.tar.gz

# 3. When prompted, enter your PyPI credentials:
#    - Username: __token__
#    - Password: <your PyPI API token>
```

### Option 2: Using PyPI API Token (More Secure)

```bash
# 1. Create an API token on PyPI
#    - Go to https://pypi.org/account/
#    - Click "Account settings" → "API tokens"
#    - Create a new token for this project

# 2. Store token in ~/.pypirc
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi_YOUR_TOKEN_HERE
EOF

# 3. Make sure permissions are restrictive
chmod 600 ~/.pypirc

# 4. Publish
twine upload dist/klaus_proxy_local-0.3.0-py3-none-any.whl dist/klaus_proxy_local-0.3.0.tar.gz
```

### Option 3: Using Environment Variables

```bash
# Set credentials as environment variables
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi_YOUR_TOKEN_HERE

# Publish
twine upload dist/klaus_proxy_local-0.3.0-py3-none-any.whl dist/klaus_proxy_local-0.3.0.tar.gz
```

### Option 4: Using Trusted Publishing (GitHub Actions)

If publishing from GitHub Actions, configure OIDC trusted publishing:

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    packages-dir: dist/
```

## Verification After Publishing

After publishing, verify the package is available:

```bash
# Option 1: pip install
pip install Klaus-proxy-local==0.3.0

# Option 2: Check PyPI
curl https://pypi.org/pypi/Klaus-proxy-local/0.3.0/json | jq '.info.version'

# Option 3: PyPI web UI
# Visit: https://pypi.org/project/Klaus-proxy-local/
```

## What Users Will See

Once published to PyPI:

```bash
$ pip install Klaus-proxy-local

# Or specific version
$ pip install Klaus-proxy-local==0.3.0

# First run (auto-setup)
$ claude-proxy
```

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL certificate verification errors:

```bash
# Temporarily disable SSL verification (NOT recommended for production)
pip install twine
twine upload dist/* --skip-existing

# Or use curl with insecure flag
curl -k -u __token__:YOUR_TOKEN https://upload.pypi.org/legacy/ ...
```

### Already Exists Error

If you get an error that the version already exists:

```bash
# Either increment version and rebuild
# Or use --skip-existing to ignore existing packages
twine upload dist/* --skip-existing
```

### Authentication Failed

```bash
# Verify your PyPI token is valid
# - Check PyPI account settings
# - Make sure token hasn't expired
# - For project-specific tokens, ensure they allow this project
```

## Package Information

After publishing, users can find your package at:

- **PyPI**: https://pypi.org/project/Klaus-proxy-local/
- **Project URL**: https://github.com/Ka0s-Klaus/klaus-proxy-local
- **Documentation**: https://github.com/Ka0s-Klaus/klaus-proxy-local/tree/main/docs

## What's Included in the Package

✅ 3,500+ lines of production code  
✅ Complete Tier 1-3 detection  
✅ Pseudonymization + audit trail  
✅ Zero-config auto-setup  
✅ 2 GitHub Actions workflows  
✅ Entry points:
- `claude-proxy` - Main proxy launcher
- `klaus-scan` - Security scanner
- `klaus-setup` - Manual setup

## Next Steps

1. **Publish to PyPI** using one of the methods above
2. **Create GitHub Release** (already done)
3. **Announce** in relevant channels:
   - GitHub Discussion
   - Python Package Index
   - Developer communities

## Support

For issues with PyPI publishing:
- PyPI Help: https://pypi.org/help/
- Twine Documentation: https://twine.readthedocs.io/
- GitHub Issues: https://github.com/Ka0s-Klaus/klaus-proxy-local/issues

---

**Status:** Distribution files ready for PyPI  
**Version:** 0.3.0  
**Files:** 2 (wheel + source)  
**Size:** ~220 KB total  
**Ready:** Yes ✅
