# Klaus Proxy Local - Python 3.13 Setup Guide

## Quick Start

### 1. Install Python 3.13 (if not already installed)

```bash
# macOS with Homebrew
brew install python@3.13

# Ubuntu/Debian
sudo apt install python3.13 python3.13-venv

# Fedora/RHEL
sudo dnf install python3.13 python3.13-devel
```

### 2. Activate the Klaus Proxy Environment

```bash
source activate-klaus
```

This will:
- ✅ Create a Python 3.13 virtual environment (`.venv-py313`)
- ✅ Activate the environment
- ✅ Make Klaus Proxy commands available

### 3. Verify Installation

```bash
# Check Python version
python --version
# Should output: Python 3.13.x

# Check Klaus Proxy installer
klaus-install-python
# Should output: ✅ Python 3.13 is compatible!
```

## Available Commands

Once activated with `source activate-klaus`:

| Command | Purpose |
|---------|---------|
| `klaus-install-python` | Check/install Python 3.13+ |
| `claude-proxy` | Start the audit proxy server |
| `klaus-scan` | Scan for sensitive data in code |

## Virtual Environment

The virtual environment is located at `.venv-py313/`:

```bash
# Activate manually
source .venv-py313/bin/activate

# Deactivate
deactivate

# View installed packages
pip list
```

## Troubleshooting

### SSL Certificate Errors

If you see SSL certificate errors when running `pip install`:

```bash
# Option 1: Try again later (PyPI connectivity issue)
# Option 2: Install with --trusted-host flag
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

### Command Not Found

If commands aren't found after activation:

```bash
# Ensure venv is activated
source activate-klaus

# Verify activation
which python
# Should show: /path/to/.venv-py313/bin/python
```

### Permission Denied

If you get "Permission denied" errors:

```bash
# Fix script permissions
chmod +x .venv-py313/bin/klaus-*
chmod +x .venv-py313/bin/claude-*
```

## Development Workflow

### Using Klaus Proxy for auditing

```bash
# Terminal 1: Start the proxy
source activate-klaus
claude-proxy

# Terminal 2: In another terminal, use Claude with the proxy
export HTTP_PROXY=http://localhost:8899
export HTTPS_PROXY=http://localhost:8899
claude 'your question here'
```

### Scanning for sensitive data

```bash
source activate-klaus
klaus-scan /path/to/code
```

## Deactivating the Environment

```bash
deactivate
```

This returns you to your system Python.

## Additional Resources

- [Python 3.13 Release Notes](https://docs.python.org/3.13/whatsnew/3.13.html)
- [Klaus Proxy Documentation](README.md)
- [Virtual Environments Guide](https://docs.python.org/3.13/tutorial/venv.html)
