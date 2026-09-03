#!/usr/bin/env python3
"""Shell detection + auto-install for Klaus Proxy Local (FASE 1.5).

Detects user's shell and optionally adds Klaus Proxy auto-startup hook.

When enabled:
- Proxy starts automatically when shell starts
- No manual `claude-proxy` needed each time
- Can be disabled by removing hook from shell config

Usage:
  klaus-setup              # Interactive setup (ask user)
  or called directly:
  python3 -m Klaus_proxy_local.setup_shell
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional


def detect_shell() -> str:
    """Detect user's current shell.

    Returns:
      Shell name: "bash", "zsh", "fish", "powershell", or "unknown"

    Checks (in order):
      1. $SHELL environment variable (Unix-like)
      2. $PSVersionTable.PSVersion (PowerShell)
      3. Falls back to "unknown"
    """
    # Try SHELL env var (Unix-like)
    shell_env = os.environ.get("SHELL", "")
    if shell_env:
        shell_name = Path(shell_env).name
        if shell_name in ("bash", "zsh", "fish", "sh"):
            return shell_name

    # Try detecting PowerShell
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "exit"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return "powershell"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try cmd.exe on Windows
    if platform.system() == "Windows":
        return "cmd"

    return "unknown"


def get_shell_config_file() -> Optional[Path]:
    """Get path to shell configuration file for detected shell.

    Returns:
      Path to shell config file (e.g., ~/.bashrc, ~/.zshrc)
      None if shell not detected or config file doesn't exist yet

    Files checked:
      bash: ~/.bashrc, then ~/.bash_profile
      zsh: ~/.zshrc
      fish: ~/.config/fish/config.fish
      powershell: $PROFILE
    """
    shell = detect_shell()
    home = Path.home()

    if shell == "bash":
        # Try .bashrc first (interactive shells), then .bash_profile
        bashrc = home / ".bashrc"
        if bashrc.exists():
            return bashrc
        bash_profile = home / ".bash_profile"
        if bash_profile.exists():
            return bash_profile
        # If neither exists, prefer .bashrc (will be created)
        return bashrc

    elif shell == "zsh":
        return home / ".zshrc"

    elif shell == "fish":
        fish_config = home / ".config" / "fish" / "config.fish"
        return fish_config

    elif shell == "powershell":
        # PowerShell profile location varies by platform
        if platform.system() == "Windows":
            appdata = os.getenv("APPDATA", "")
            if appdata:
                return Path(appdata) / "PowerShell" / "profile.ps1"
        return None

    elif shell == "cmd":
        # CMD.exe doesn't support startup hooks easily
        return None

    return None


def get_shell_hook() -> str:
    """Get shell-specific hook code for Klaus Proxy startup.

    The hook:
    - Starts Klaus Proxy in background (if not already running)
    - Runs once per shell session
    - Non-blocking (doesn't slow down shell startup)

    Returns:
      Shell-specific code to add to config file

    Note:
      Code is idempotent - safe to source multiple times.
    """
    shell = detect_shell()

    # Common bash/zsh hook
    if shell in ("bash", "zsh"):
        return (
            "\n# 🔐 Klaus Proxy Local — Auto-startup (FASE 1.5)\n"
            "if ! pgrep -f 'claude-proxy|mitmdump' > /dev/null 2>&1; then\n"
            "  (claude-proxy > ~/.klaus-proxy/proxy.log 2>&1 &)\n"
            "fi\n"
        )

    # Fish shell hook
    elif shell == "fish":
        return (
            "\n# 🔐 Klaus Proxy Local — Auto-startup (FASE 1.5)\n"
            "if not pgrep -f 'claude-proxy|mitmdump' > /dev/null 2>&1\n"
            "  (claude-proxy > ~/.klaus-proxy/proxy.log 2>&1 &)\n"
            "end\n"
        )

    # PowerShell hook
    elif shell == "powershell":
        return (
            "\n# 🔐 Klaus Proxy Local — Auto-startup (FASE 1.5)\n"
            "$ProcessCheck = Get-Process -Name mitmdump -ErrorAction SilentlyContinue\n"
            "if (-not $ProcessCheck) {\n"
            "  Start-Process -WindowStyle Hidden -FilePath claude-proxy\n"
            "}\n"
        )

    # CMD batch doesn't support startup easily
    return ""


def ask_user_permission() -> bool:
    """Ask user if they want to enable Klaus Proxy auto-startup.

    Returns:
      True if user answers yes, False otherwise

    Shows:
      - Detected shell
      - Proposed config file
      - What will happen
    """
    shell = detect_shell()
    config_file = get_shell_config_file()

    print("🔐 Klaus Proxy Local — Setup")
    print()
    print(f"Shell detected:  {shell}")

    if config_file:
        print(f"Config file:     {config_file}")
    else:
        print("Config file:     (not found or not configurable)")

    print()
    print("Enable Klaus Proxy auto-startup?")
    print("  • Proxy starts automatically when shell opens")
    print("  • Hook added to your shell config file")
    print("  • Can be disabled by removing the hook")
    print()

    if not config_file:
        print(f"❌ Shell '{shell}' not supported for auto-startup")
        print()
        return False

    while True:
        response = input("Enable auto-startup? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            return True
        elif response in ("n", "no", ""):
            return False
        else:
            print("Please answer 'y' or 'n'")


def add_hook_to_shell_config(config_file: Path, hook_code: str) -> None:
    """Add Klaus Proxy hook to shell config file.

    Creates file if missing, appends hook code, ensures newline at end.

    Args:
      config_file: Path to shell config file
      hook_code: Shell-specific code to add

    Raises:
      IOError: If unable to write to config file
    """
    # Ensure config file parent directory exists
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Read existing content
    if config_file.exists():
        content = config_file.read_text()
    else:
        content = ""

    # Check if hook already present (idempotence)
    if "Klaus Proxy Local — Auto-startup" in content:
        print(f"✅ Hook already present in {config_file}")
        return

    # Append hook code
    if content and not content.endswith("\n"):
        content += "\n"
    content += hook_code

    # Write back with secure permissions (0o600 for sensitive files)
    try:
        config_file.write_text(content)
        config_file.chmod(0o600)
        print(f"✅ Added hook to {config_file}")
    except Exception as e:
        raise IOError(f"Failed to write to {config_file}: {e}")


def run_setup() -> None:
    """Run interactive Klaus Proxy setup.

    Orchestrates:
    1. Detect shell
    2. Ask user permission
    3. Add hook to shell config
    4. Install wrapper scripts
    5. Show next steps
    """
    print()
    shell = detect_shell()
    config_file = get_shell_config_file()

    if shell == "unknown":
        print("❌ Could not detect your shell")
        print("   Try setting $SHELL environment variable")
        sys.exit(1)

    # Ask permission
    if not ask_user_permission():
        print("⏭️  Setup skipped")
        print()
        print("To use Klaus Proxy manually:")
        print("  Terminal 1: claude-proxy")
        print("  Terminal 2: claude-with-proxy 'your question'")
        sys.exit(0)

    print()

    # Add hook to config
    if not config_file:
        print(f"❌ Shell '{shell}' not supported for auto-startup")
        sys.exit(1)

    hook_code = get_shell_hook()
    try:
        add_hook_to_shell_config(config_file, hook_code)
    except IOError as e:
        print(f"❌ Failed to setup: {e}", file=sys.stderr)
        sys.exit(1)

    # Install wrappers
    print()
    print("📦 Installing wrapper scripts...")
    try:
        from Klaus_proxy_local.install_wrappers import install_wrappers

        install_wrappers()
    except RuntimeError as e:
        print(f"⚠️  Warning: {e}")
        # Don't exit on wrapper install failure - hook is more important

    print()
    print("=" * 60)
    print("✅ Klaus Proxy setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Reload your shell:")
    print("     exec $SHELL")
    print()
    print("  2. Proxy will start automatically on next shell open")
    print()
    print("  3. Use Claude Code as normal:")
    print("     claude 'your question'")
    print()
    print("To disable auto-startup, remove the Klaus Proxy hook from:")
    print(f"  {config_file}")
    print()


def main() -> None:
    """Entry point for klaus-setup command."""
    try:
        run_setup()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n⏭️  Setup cancelled")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
