#!/bin/bash
# Klaus Menu Installer

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KLAUS_SCRIPT="$SCRIPT_DIR/klaus"
INSTALL_DIR="${HOME}/.local/bin"

# Colors
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

echo "🔐 Klaus Menu Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if source exists
if [ ! -f "$KLAUS_SCRIPT" ]; then
    echo "❌ Error: $KLAUS_SCRIPT not found"
    echo "   Make sure you're in the Klaus Proxy Local project directory"
    exit 1
fi

# Create ~/.local/bin if it doesn't exist
if [ ! -d "$INSTALL_DIR" ]; then
    echo "📁 Creating $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
fi

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "⚠️  Warning: $INSTALL_DIR is not in your PATH"
    echo "   Add this line to your ~/.bashrc or ~/.zshrc:"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# Install the script
echo "📋 Installing Klaus Menu..."
cp "$KLAUS_SCRIPT" "$INSTALL_DIR/klaus"
chmod +x "$INSTALL_DIR/klaus"

echo ""
echo -e "${GREEN}✅ Installation complete!${RESET}"
echo ""
echo "🚀 Quick start:"
echo "   $ klaus          # Interactive menu"
echo "   $ klaus --help   # Show help"
echo ""
echo "📖 Documentation: docs/KLAUS_MENU.md"
echo ""
