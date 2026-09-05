#!/bin/bash
# Script para crear release v0.3.0 en GitHub

set -e

echo "🚀 Creating GitHub Release v0.3.0..."
echo ""

# Option 1: Using GitHub CLI (if certificate issue is resolved)
echo "📝 Attempting release creation with GitHub CLI..."
echo ""

if command -v gh &> /dev/null; then
    echo "✅ GitHub CLI found"
    echo ""
    echo "Two options:"
    echo "  1. Use gh command (may have TLS issues)"
    echo "  2. Manual creation on GitHub web"
    echo ""
    read -p "Choose (1/2): " choice

    case $choice in
        1)
            echo "Creating release with gh..."
            # Try with SSL bypass if needed
            GIT_SSL_NO_VERIFY=false gh release create v0.3.0 \
                --title "Klaus Proxy Local v0.3.0 — Complete Audit & Auto-Fix System" \
                --notes-file RELEASE_v0.3.0_NOTES.md \
                --draft=false

            echo "✅ Release created successfully!"
            echo ""
            echo "View release at:"
            echo "https://github.com/Ka0s-Klaus/klaus-proxy-local/releases/tag/v0.3.0"
            ;;
        2)
            echo ""
            echo "📖 Manual Release Creation Instructions:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "1. Go to: https://github.com/Ka0s-Klaus/klaus-proxy-local/releases"
            echo ""
            echo "2. Click 'Draft a new release'"
            echo ""
            echo "3. Fill in:"
            echo "   Tag version: v0.3.0"
            echo "   Release title: Klaus Proxy Local v0.3.0 — Complete Audit & Auto-Fix System"
            echo ""
            echo "4. Copy release notes from: RELEASE_v0.3.0_NOTES.md"
            echo ""
            echo "5. Upload any binaries/artifacts (optional)"
            echo ""
            echo "6. Click 'Publish release'"
            echo ""
            echo "📋 Release notes file ready: RELEASE_v0.3.0_NOTES.md"
            ;;
    esac
else
    echo "❌ GitHub CLI not found"
    echo ""
    echo "Install with:"
    echo "  brew install gh  (macOS)"
    echo "  apt install gh   (Ubuntu)"
    echo ""
    echo "Or create release manually at:"
    echo "  https://github.com/Ka0s-Klaus/klaus-proxy-local/releases"
fi
