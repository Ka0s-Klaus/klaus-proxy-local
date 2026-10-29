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
import re
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


HOOK_BEGIN = "# >>> Klaus Proxy Local (klaus-setup) >>>"
HOOK_END = "# <<< Klaus Proxy Local (klaus-setup) <<<"
# Hook de versiones anteriores: arrancaba el proxy pero no exportaba
# HTTPS_PROXY (#105). Se sustituye al volver a ejecutar klaus-setup.
LEGACY_HOOK_RE = re.compile(
    r"\n?# 🔐 Klaus Proxy Local — Auto-startup \(FASE 1\.5\)\n.*?\n(?:fi|end|\})\n",
    re.S,
)


def _proxy_url() -> str:
    from Klaus_proxy_local.launcher import ProxyLauncher

    return f"http://{ProxyLauncher.HOST}:{ProxyLauncher.PORT}"


def get_shell_hook() -> str:
    """Generate shell-specific Klaus Proxy hook (#105).

    The hook, on every new shell:
    - Sources ~/.klaus-proxy/klaus-env.sh (trust in the proxy CA)
    - Starts claude-proxy in the background (nohup) if it is not running,
      logging to ~/.klaus-proxy/logs/autostart.log
    - Exports HTTPS_PROXY, so ``claude`` (and any HTTPS client of the
      shell) goes through the proxy; NO_PROXY keeps loopback direct
    - Defines ``klaus-off`` / ``klaus-on`` to drop or restore HTTPS_PROXY
      in the current shell

    Returns:
      Shell-specific code between HOOK_BEGIN and HOOK_END, or "" if the
      shell is not supported (Windows shells are not supported).
    """
    shell = detect_shell()
    url = _proxy_url()
    host = url.split("//", 1)[1].rsplit(":", 1)[0]
    no_proxy = f"localhost,{host},::1"
    log = "~/.klaus-proxy/logs/autostart.log"
    running = "pgrep -f 'bin/mitmdump|bin/claude-proxy' >/dev/null 2>&1"

    if shell in ("bash", "zsh"):
        body = (
            "# Confianza en la CA del proxy, arranque en segundo plano si no está\n"
            "# en marcha y HTTPS de esta terminal por el proxy (#105).\n"
            '[ -f "$HOME/.klaus-proxy/klaus-env.sh" ] && . "$HOME/.klaus-proxy/klaus-env.sh"\n'
            f"if command -v claude-proxy >/dev/null 2>&1 && ! {running}; then\n"
            '  mkdir -p "$HOME/.klaus-proxy/logs"\n'
            f"  (nohup claude-proxy >>{log} 2>&1 </dev/null &)\n"
            "fi\n"
            f"export HTTPS_PROXY={url}\n"
            f'export NO_PROXY="{no_proxy}"\n'
            'klaus-off() { unset HTTPS_PROXY; echo "Klaus Proxy: HTTPS directo en esta terminal"; }\n'
            f'klaus-on() {{ export HTTPS_PROXY={url}; echo "Klaus Proxy: HTTPS por el proxy"; }}\n'
        )
    elif shell == "fish":
        body = (
            "# Confianza en la CA del proxy, arranque en segundo plano si no está\n"
            "# en marcha y HTTPS de esta terminal por el proxy (#105).\n"
            "test -f ~/.klaus-proxy/klaus-env.sh; and source ~/.klaus-proxy/klaus-env.sh\n"
            f"if command -q claude-proxy; and not {running}\n"
            "  mkdir -p ~/.klaus-proxy/logs\n"
            f"  nohup claude-proxy >>{log} 2>&1 </dev/null &\n"
            "  disown\n"
            "end\n"
            f"set -gx HTTPS_PROXY {url}\n"
            f"set -gx NO_PROXY {no_proxy}\n"
            'function klaus-off; set -e HTTPS_PROXY; echo "Klaus Proxy: HTTPS directo en esta terminal"; end\n'
            f'function klaus-on; set -gx HTTPS_PROXY {url}; echo "Klaus Proxy: HTTPS por el proxy"; end\n'
        )
    else:
        return ""
    return f"\n{HOOK_BEGIN}\n{body}{HOOK_END}\n"


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
    print("Enable Klaus Proxy in every new terminal?")
    print("  • Starts claude-proxy in the background if it is not running")
    print("    (from the folder where the terminal opens; log in")
    print("    ~/.klaus-proxy/logs/autostart.log)")
    print("  • Exports HTTPS_PROXY: claude AND any other HTTPS client of the")
    print("    terminal (pip, git, curl…) go through the proxy and are logged.")
    print("    Only the LLM API is decrypted; the rest is tunnelled with its")
    print("    real certificate, so there are no certificate errors")
    print("  • Remove the block between the Klaus Proxy markers to disable it")
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

    # Idempotente: sustituye el bloque de una ejecución anterior y el hook
    # antiguo, que no exportaba HTTPS_PROXY (#105).
    if hook_code.strip() and hook_code.strip() in content:
        print(f"✅ Hook already present in {config_file}")
        return
    content = LEGACY_HOOK_RE.sub("\n", content)
    begin, end = content.find(HOOK_BEGIN), content.find(HOOK_END)
    if begin != -1 and end != -1:
        content = (
            content[:begin].rstrip("\n")
            + "\n"
            + content[end + len(HOOK_END) :].lstrip("\n")
        )

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
        print()
        print("  Terminal 2: source ~/.klaus-proxy/klaus-env.sh")
        print("              export HTTPS_PROXY=http://127.0.0.1:8899")
        print("              claude 'your question'")
        return

    print()

    # Add hook to config
    if not config_file:
        print(f"❌ Shell '{shell}' not supported for auto-startup")
        sys.exit(1)

    hook_code = get_shell_hook()
    if not hook_code:
        print(f"❌ Shell '{shell}' not supported (macOS/Linux: bash, zsh, fish)")
        sys.exit(1)
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
    print("  2. In every new terminal the proxy starts if needed and")
    print("     HTTPS_PROXY is set: just run `claude`")
    print()
    print("  3. klaus-off / klaus-on: drop or restore HTTPS_PROXY in a terminal")
    print()
    print("To disable it, remove the Klaus Proxy block from:")
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
