#!/usr/bin/env python3
"""Python version checker and installer for Klaus Proxy Local.

Detects the current Python version and installs Python 3.13+ if needed.
Supports macOS (Homebrew), Ubuntu/Debian (apt), Fedora (dnf), and Windows (Python installer).

Usage:
  python3 install_python.py
  Or: pip install Klaus-proxy-local  # Automatically checks Python version
"""
import platform
import subprocess
import sys
from pathlib import Path


def get_python_version() -> tuple[int, int]:
    """Get current Python version as (major, minor) tuple."""
    return (sys.version_info.major, sys.version_info.minor)


def version_string(version: tuple[int, int]) -> str:
    """Convert version tuple to string (e.g., (3, 13) -> '3.13')."""
    return f"{version[0]}.{version[1]}"


def is_python_313_or_newer() -> bool:
    """Check if current Python is 3.13 or newer."""
    major, minor = get_python_version()
    return (major, minor) >= (3, 13)


def get_os_info() -> tuple[str, str]:
    """Get OS and detect package manager.
    
    Returns:
      (os_name, package_manager) where os_name is 'darwin', 'linux', 'windows'
      and package_manager is 'brew', 'apt', 'dnf', 'choco', or 'unknown'
    """
    system = platform.system()
    
    if system == "Darwin":
        # macOS with Homebrew
        if subprocess.run(["which", "brew"], capture_output=True).returncode == 0:
            return ("darwin", "brew")
        return ("darwin", "unknown")
    
    elif system == "Linux":
        # Try common package managers
        if subprocess.run(["which", "apt"], capture_output=True).returncode == 0:
            return ("linux", "apt")
        elif subprocess.run(["which", "dnf"], capture_output=True).returncode == 0:
            return ("linux", "dnf")
        elif subprocess.run(["which", "pacman"], capture_output=True).returncode == 0:
            return ("linux", "pacman")
        return ("linux", "unknown")
    
    elif system == "Windows":
        if subprocess.run(["where", "choco"], capture_output=True).returncode == 0:
            return ("windows", "choco")
        return ("windows", "unknown")
    
    return ("unknown", "unknown")


def install_python_macos() -> bool:
    """Install Python 3.13 on macOS using Homebrew.
    
    Returns:
      True if installation successful, False otherwise.
    """
    print("🍎 Installing Python 3.13 via Homebrew...\n")
    
    try:
        # Update Homebrew
        print("  Updating Homebrew...")
        subprocess.run(["brew", "update"], check=True, capture_output=True)
        
        # Install Python 3.13
        print("  Installing Python 3.13...")
        subprocess.run(["brew", "install", "python@3.13"], check=True, capture_output=True)
        
        print("\n✅ Python 3.13 installed successfully!\n")
        print("  Run this to use Python 3.13:")
        print("  python3.13 -m pip install -e .\n")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python 3.13: {e}\n")
        return False


def install_python_ubuntu() -> bool:
    """Install Python 3.13 on Ubuntu/Debian using apt.
    
    Returns:
      True if installation successful, False otherwise.
    """
    print("🐧 Installing Python 3.13 via apt...\n")
    
    try:
        print("  Updating package lists...")
        subprocess.run(["sudo", "apt", "update"], check=True, capture_output=True)
        
        print("  Installing Python 3.13...")
        subprocess.run(
            ["sudo", "apt", "install", "-y", "python3.13", "python3.13-venv", "python3.13-dev"],
            check=True,
            capture_output=True
        )
        
        print("\n✅ Python 3.13 installed successfully!\n")
        print("  Run this to use Python 3.13:")
        print("  python3.13 -m pip install -e .\n")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python 3.13: {e}\n")
        return False


def install_python_fedora() -> bool:
    """Install Python 3.13 on Fedora using dnf.
    
    Returns:
      True if installation successful, False otherwise.
    """
    print("🔴 Installing Python 3.13 via dnf...\n")
    
    try:
        print("  Installing Python 3.13...")
        subprocess.run(
            ["sudo", "dnf", "install", "-y", "python3.13", "python3.13-devel"],
            check=True,
            capture_output=True
        )
        
        print("\n✅ Python 3.13 installed successfully!\n")
        print("  Run this to use Python 3.13:")
        print("  python3.13 -m pip install -e .\n")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python 3.13: {e}\n")
        return False


def install_python_windows() -> bool:
    """Install Python 3.13 on Windows using chocolatey or direct download.
    
    Returns:
      True if installation successful, False otherwise.
    """
    print("🪟 Installing Python 3.13 on Windows...\n")
    
    # Try Chocolatey first
    if subprocess.run(["where", "choco"], capture_output=True).returncode == 0:
        print("  Using Chocolatey to install Python 3.13...")
        try:
            subprocess.run(["choco", "install", "python313", "-y"], check=True)
            print("\n✅ Python 3.13 installed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Chocolatey installation failed: {e}")
    
    # Fallback: direct download
    print("\n  Please download Python 3.13 from:")
    print("  https://www.python.org/downloads/release/python-3130/\n")
    print("  1. Download the Windows installer")
    print("  2. Run it and check 'Add Python to PATH'")
    print("  3. Then run: pip install -e .\n")
    return False


def show_version_mismatch_message(current_version: tuple[int, int]) -> None:
    """Show error message about Python version mismatch."""
    current = version_string(current_version)
    print("\n" + "=" * 70)
    print(f"❌ PYTHON VERSION MISMATCH")
    print("=" * 70)
    print(f"Current version: {current}")
    print(f"Required version: 3.13+")
    print("\nKlaus Proxy Local requires Python 3.13 or newer.")
    print("=" * 70 + "\n")


def main() -> int:
    """Check Python version and install if needed.
    
    Returns:
      0 if Python 3.13+ is available (or successfully installed)
      1 if installation failed
    """
    current = get_python_version()
    current_str = version_string(current)
    
    print(f"\n🔍 Checking Python version... (found: {current_str})\n")
    
    # Python 3.13+ already available
    if is_python_313_or_newer():
        print(f"✅ Python {current_str} is compatible!\n")
        return 0
    
    # Show version mismatch
    show_version_mismatch_message(current)
    
    # Detect OS and package manager
    os_type, pkg_manager = get_os_info()
    
    # Attempt installation based on OS
    if os_type == "darwin":
        if pkg_manager == "brew":
            success = install_python_macos()
        else:
            print("❌ Homebrew not found. Please install Homebrew:")
            print("   /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n")
            success = False
    
    elif os_type == "linux":
        if pkg_manager == "apt":
            success = install_python_ubuntu()
        elif pkg_manager == "dnf":
            success = install_python_fedora()
        else:
            print("❌ Supported package manager (apt/dnf) not found.")
            print("   Please install Python 3.13 manually:\n")
            print("   Ubuntu/Debian: sudo apt install python3.13")
            print("   Fedora/RHEL: sudo dnf install python3.13\n")
            success = False
    
    elif os_type == "windows":
        success = install_python_windows()
    
    else:
        print(f"❌ Unsupported OS: {os_type}\n")
        success = False
    
    if success:
        print("✅ Klaus Proxy Local is ready to use!\n")
        return 0
    else:
        print("⚠️  Please install Python 3.13+ manually and try again.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
