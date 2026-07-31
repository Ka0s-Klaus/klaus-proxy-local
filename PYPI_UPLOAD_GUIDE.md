# 📦 PyPI Upload Guide — Klaus Proxy Local v0.1.0

## Overview

This guide provides step-by-step instructions to build and upload Klaus Proxy Local v0.1.0 to PyPI.

**Status**: Ready to upload (code, tests, and documentation all complete)  
**Version**: 0.1.0  
**Repository**: https://github.com/Ka0s-Klaus/klaus-proxy-local  
**Git Tag**: v0.1.0 (already created and pushed)

---

## Prerequisites

1. **PyPI Account**
   - Create an account at https://pypi.org/account/register/
   - Or use TestPyPI first: https://test.pypi.org/account/register/

2. **PyPI API Token** (Recommended)
   - Generate token at: https://pypi.org/manage/account/
   - Store in `~/.pypirc` file

3. **Required Tools**
   - Python 3.10+ (required by project)
   - pip
   - build
   - twine

---

## Step 1: Setup Local Environment

```bash
# Clone repository if you haven't already
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local

# Verify you're on main branch with v0.1.0 tag
git branch
git tag -l | grep v0.1.0

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

---

## Step 2: Install Build Tools

```bash
# Install required packages
pip install --upgrade pip
pip install build twine

# Verify installations
python3 -m build --version
twine --version
```

---

## Step 3: Build Distribution

```bash
# Navigate to project root (if not already there)
cd /path/to/klaus-proxy-local

# Clean previous builds (optional)
rm -rf build/ dist/ *.egg-info

# Build wheel and source distribution
python3 -m build

# Verify build output
ls -lh dist/
# Expected files:
#   - Klaus-proxy-local-0.1.0-py3-none-any.whl
#   - Klaus-proxy-local-0.1.0.tar.gz
```

---

## Step 4: Test on TestPyPI (Recommended)

Before uploading to production PyPI, test on TestPyPI:

```bash
# Create PyPI credentials file for TestPyPI
# File: ~/.pypirc
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    testpypi
    pypi

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Your TestPyPI token

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmc...  # Your PyPI token
EOF

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ Klaus-proxy-local

# Verify installation works
python3 -c "import Klaus_proxy_local; print('✅ Klaus Proxy Local installed successfully')"
klaus-proxy --help
klaus-setup --help

# Uninstall test version
pip uninstall Klaus-proxy-local
```

---

## Step 5: Upload to Production PyPI

### Method 1: Using .pypirc (Recommended)

```bash
# If you've already created ~/.pypirc with credentials (see Step 4)
twine upload dist/*

# You'll see:
# Uploading Klaus-proxy-local-0.1.0-py3-none-any.whl
# Uploading Klaus-proxy-local-0.1.0.tar.gz
# View at https://pypi.org/project/Klaus-proxy-local/0.1.0/
```

### Method 2: Using Command-Line Credentials

```bash
# Upload with username/password (will prompt for password)
twine upload -u __token__ dist/*

# Or with token inline (less secure, not recommended)
# twine upload -u __token__ -p "pypi-AgEIcHlwaS5vcmc..." dist/*
```

### Method 3: Using Environment Variables

```bash
# Set environment variables
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-AgEIcHlwaS5vcmc..."

# Upload
twine upload dist/*

# Unset for security
unset TWINE_USERNAME
unset TWINE_PASSWORD
```

---

## Step 6: Verify Upload

### On PyPI Package Page

1. Visit: https://pypi.org/project/Klaus-proxy-local/0.1.0/
2. Verify:
   - ✅ Version 0.1.0 is latest
   - ✅ README.md renders correctly
   - ✅ Both wheel (.whl) and source (.tar.gz) are available
   - ✅ Project description is correct

### Installation Test (Production)

```bash
# Install from PyPI
pip install Klaus-proxy-local

# Verify it works
python3 -c "import Klaus_proxy_local; print('✅ Installed from PyPI')"

# Check entry points
which claude-proxy
which klaus-setup
which klaus-install-wrappers

# Test functionality
klaus-setup --help
```

---

## Step 7: Create GitHub Release (Optional but Recommended)

```bash
# Create a GitHub release from the v0.1.0 tag
gh release create v0.1.0 \
  --title "Klaus Proxy Local v0.1.0" \
  --notes "$(cat <<'EOF'
## Zero-Config Privacy Proxy for Individual Developers

### Installation
\`\`\`bash
pip install Klaus-proxy-local
\`\`\`

### Quick Start
\`\`\`bash
klaus-setup
claude "your question"
\`\`\`

### Features
- ✅ Zero-config setup (auto-config + auto-certs)
- ✅ Cross-platform (bash/zsh, fish, PowerShell, CMD)
- ✅ 225+ tests (all passing)
- ✅ Secure by default (0o600 config, 0o700 dirs)

See [QUICK_START.md](docs/QUICK_START.md) for complete documentation.
EOF
)" \
  dist/Klaus-proxy-local-0.1.0*.whl

# Or attach distributions manually:
gh release upload v0.1.0 dist/*
```

---

## Troubleshooting

### "403 Forbidden" Error

**Problem**: Invalid PyPI credentials  
**Solution**:
1. Verify token at https://pypi.org/manage/account/
2. Check `~/.pypirc` has correct token
3. Ensure token hasn't expired
4. Re-generate token if needed

### "Filename already exists" Error

**Problem**: Trying to upload same version twice  
**Solution**: PyPI doesn't allow re-uploading the same version
- You must bump the version (e.g., 0.1.1)
- Or delete the previous version from PyPI (if it's recent)

### "Setup.py Not Found" Error

**Problem**: Build tool can't find setup configuration  
**Solution**: Ensure you're in the project root directory where `pyproject.toml` exists

### Network/SSL Issues

**Problem**: Certificate verification failed  
**Solution**:
```bash
# Try with SSL verification disabled (temporary workaround)
pip install --trusted-host pypi.python.org --trusted-host files.pythonhosted.org build twine

# Or use system Python's certificates
pip install --cert /etc/ssl/certs/ca-certificates.crt build twine
```

---

## Final Checklist

Before uploading, verify:

- [ ] Running on main branch: `git branch`
- [ ] v0.1.0 tag exists: `git tag -l | grep v0.1.0`
- [ ] Working directory clean: `git status`
- [ ] Version in pyproject.toml is 0.1.0
- [ ] Build succeeds: `python3 -m build`
- [ ] dist/ contains 2 files (wheel + source)
- [ ] PyPI credentials configured in `~/.pypirc`
- [ ] TestPyPI upload works (optional but recommended)
- [ ] README.md renders on TestPyPI page

---

## Post-Upload

After successful upload to PyPI:

1. **Announce Release** (optional)
   - Tweet/post: "Klaus Proxy Local v0.1.0 is now on PyPI!"
   - Share: https://pypi.org/project/Klaus-proxy-local/

2. **Update Project Links** (optional)
   - Update README.md installation link
   - Update website/docs to point to PyPI

3. **Monitor Package**
   - Watch PyPI page for downloads
   - Monitor for issues/feedback

---

## Support

For issues during upload:

1. **PyPI Help**: https://packaging.python.org/
2. **Twine Docs**: https://twine.readthedocs.io/
3. **GitHub Issues**: Report any problems at the repository

---

## Summary

Klaus Proxy Local v0.1.0 is production-ready and can be installed by any user with:

```bash
pip install Klaus-proxy-local
```

This guide covers all steps from build to verification. Follow it step-by-step for a smooth PyPI upload.

---

**Status**: 🚀 Ready for distribution

See [FASE5_RELEASE.md](docs/FASE5_RELEASE.md) for the complete release documentation.
