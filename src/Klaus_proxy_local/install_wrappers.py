#!/usr/bin/env python3
r"""Install wrapper scripts to user's PATH (FASE 1.4).

Copies claude-with-proxy.* scripts to ~/.local/bin/ on Unix-like systems
or %APPDATA%\Scripts on Windows, making them available system-wide.

Usage:
  python3 -m Klaus_proxy_local.install_wrappers
  Or called automatically during pip install setup.
"""
import os
import platform
import shutil
import sys
from pathlib import Path


def get_bin_dir() -> Path:
    r"""Get platform-appropriate bin directory for user scripts.

    Returns:
      ~/.local/bin on Unix-like systems
      %APPDATA%\Scripts on Windows

    Raises:
      RuntimeError: If bin directory cannot be determined.
    """
    system = platform.system()

    if system in ("Linux", "Darwin"):
        # Unix-like (Linux, macOS)
        return Path.home() / ".local" / "bin"
    elif system == "Windows":
        # Windows
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise RuntimeError("Cannot determine APPDATA on Windows")
        return Path(appdata) / "Scripts"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def get_scripts_dir() -> Path:
    """Get the scripts directory in the Klaus package.

    Returns:
      Path to scripts/ directory in package root.

    Raises:
      RuntimeError: If scripts directory not found.
    """
    # Scripts are in repo root: /scripts/
    # When installed, they're in package: site-packages/Klaus_proxy_local/../../../scripts/
    # Easiest: look for scripts relative to this module
    module_dir = Path(__file__).resolve().parent
    repo_root = module_dir.parents[1]  # src/Klaus_proxy_local -> src -> repo_root
    scripts_dir = repo_root / "scripts"

    if not scripts_dir.exists():
        raise RuntimeError(
            f"Scripts directory not found at {scripts_dir}\n"
            f"Make sure Klaus Proxy is installed correctly."
        )

    return scripts_dir


def get_wrapper_scripts() -> list[tuple[Path, str]]:
    """Get list of wrapper scripts to install.

    Returns:
      List of (source_path, target_name) tuples.
      target_name is the name the script will have in bin dir.
    """
    scripts_dir = get_scripts_dir()
    system = platform.system()

    scripts = []

    # All platforms: install bash version with simple name
    bash_script = scripts_dir / "claude-with-proxy.sh"
    if bash_script.exists():
        scripts.append((bash_script, "claude-with-proxy"))

    # Platform-specific versions (optional, for advanced users)
    if system in ("Linux", "Darwin"):
        fish_script = scripts_dir / "claude-with-proxy.fish"
        if fish_script.exists():
            scripts.append((fish_script, "claude-with-proxy.fish"))

    elif system == "Windows":
        ps1_script = scripts_dir / "claude-with-proxy.ps1"
        bat_script = scripts_dir / "claude-with-proxy.bat"
        if ps1_script.exists():
            scripts.append((ps1_script, "claude-with-proxy.ps1"))
        if bat_script.exists():
            scripts.append((bat_script, "claude-with-proxy.bat"))

    return scripts


def ensure_bin_dir_in_path() -> bool:
    """Check if bin directory is in user's PATH.

    Returns:
      True if already in PATH, False otherwise.
    """
    bin_dir = get_bin_dir()
    path = os.environ.get("PATH", "")
    return str(bin_dir) in path


def install_wrappers() -> None:
    """Install wrapper scripts to user's bin directory.

    Creates directory if missing, copies scripts with executable permissions.
    Shows helpful messages about PATH setup if needed.

    Raises:
      RuntimeError: If installation fails.
    """
    print("📦 Installing Klaus Proxy wrapper scripts...\n")

    try:
        bin_dir = get_bin_dir()
        scripts = get_wrapper_scripts()

        # Create bin directory if missing
        bin_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Bin directory: {bin_dir}\n")

        # Copy each script
        installed = 0
        for src, target_name in scripts:
            target = bin_dir / target_name
            try:
                shutil.copy2(src, target)
                # Ensure executable on Unix-like systems
                if platform.system() in ("Linux", "Darwin"):
                    target.chmod(0o755)
                print(f"✅ Installed: {target_name}")
                installed += 1
            except Exception as e:
                print(f"⚠️  Failed to install {target_name}: {e}")

        if installed == 0:
            raise RuntimeError("No scripts were installed")

        print(f"\n✅ Installed {installed} wrapper script(s)")

        # Check PATH and warn if needed
        if not ensure_bin_dir_in_path():
            print(f"\n⚠️  {bin_dir} is not in your PATH")
            print("\nAdd it to your shell config:")

            if platform.system() in ("Linux", "Darwin"):
                print("  # Add to ~/.bashrc, ~/.zshrc, or equivalent:")
                print(f'  export PATH="{bin_dir}:$PATH"')
            elif platform.system() == "Windows":
                print("  Windows: Scripts folder is usually in PATH automatically")

        print()

    except Exception as e:
        raise RuntimeError(f"❌ Failed to install wrappers: {e}")


def main() -> None:
    """Entry point for wrapper installation."""
    try:
        install_wrappers()
        sys.exit(0)
    except RuntimeError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
