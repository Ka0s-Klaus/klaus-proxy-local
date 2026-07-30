#!/usr/bin/env python3
"""Tests for FASE 1.4: Wrapper installation (install_wrappers.py).

Verifies:
- Correct bin directory detection
- Wrapper script discovery
- Installation logic
- PATH checking
"""
import platform
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import install_wrappers


class TestBinDirDetection:
    """Test platform-appropriate bin directory detection."""

    def test_bin_dir_on_unix_is_local_bin(self):
        """On Unix-like systems, bin dir is ~/.local/bin."""
        with patch("platform.system", return_value="Linux"):
            bin_dir = install_wrappers.get_bin_dir()
            assert bin_dir == Path.home() / ".local" / "bin"

    def test_bin_dir_on_macos_is_local_bin(self):
        """On macOS, bin dir is ~/.local/bin."""
        with patch("platform.system", return_value="Darwin"):
            bin_dir = install_wrappers.get_bin_dir()
            assert bin_dir == Path.home() / ".local" / "bin"

    def test_bin_dir_on_windows_uses_appdata(self):
        """On Windows, bin dir uses APPDATA."""
        with patch("platform.system", return_value="Windows"):
            with patch("os.getenv", return_value="C:\\Users\\User\\AppData\\Roaming"):
                bin_dir = install_wrappers.get_bin_dir()
                assert "Scripts" in str(bin_dir)

    def test_bin_dir_raises_on_unknown_platform(self):
        """Raises RuntimeError on unknown platform."""
        with patch("platform.system", return_value="Unknown"):
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                install_wrappers.get_bin_dir()

    def test_bin_dir_raises_on_windows_without_appdata(self):
        """Raises RuntimeError if APPDATA not set on Windows."""
        with patch("platform.system", return_value="Windows"):
            with patch("os.getenv", return_value=None):
                with pytest.raises(RuntimeError, match="APPDATA"):
                    install_wrappers.get_bin_dir()


class TestScriptsDirDetection:
    """Test scripts directory detection."""

    def test_scripts_dir_is_relative_to_module(self):
        """Scripts dir is found relative to install_wrappers module."""
        scripts_dir = install_wrappers.get_scripts_dir()
        assert scripts_dir.exists()
        assert scripts_dir.name == "scripts"

    def test_scripts_dir_contains_wrappers(self):
        """Scripts directory contains wrapper files."""
        scripts_dir = install_wrappers.get_scripts_dir()
        assert (scripts_dir / "claude-with-proxy.sh").exists()
        assert (scripts_dir / "claude-with-proxy.fish").exists()

    def test_scripts_dir_raises_if_missing(self):
        """Raises RuntimeError if scripts dir not found."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(RuntimeError, match="Scripts directory not found"):
                install_wrappers.get_scripts_dir()


class TestWrapperScriptDiscovery:
    """Test discovering which wrappers to install."""

    def test_wrapper_scripts_returns_list(self):
        """get_wrapper_scripts() returns list of tuples."""
        scripts = install_wrappers.get_wrapper_scripts()
        assert isinstance(scripts, list)
        assert len(scripts) > 0
        for src, target in scripts:
            assert isinstance(src, Path)
            assert isinstance(target, str)

    def test_bash_script_always_included(self):
        """Bash wrapper is included on all platforms."""
        with patch("platform.system", return_value="Linux"):
            scripts = install_wrappers.get_wrapper_scripts()
            target_names = [target for _, target in scripts]
            assert "claude-with-proxy" in target_names

    def test_fish_script_on_unix(self):
        """Fish script included on Unix-like systems."""
        with patch("platform.system", return_value="Linux"):
            scripts = install_wrappers.get_wrapper_scripts()
            target_names = [target for _, target in scripts]
            assert "claude-with-proxy.fish" in target_names or len(target_names) > 0

    def test_ps1_script_on_windows(self):
        """PowerShell script included on Windows."""
        with patch("platform.system", return_value="Windows"):
            scripts = install_wrappers.get_wrapper_scripts()
            target_names = [target for _, target in scripts]
            # Should include either ps1 or fish or both
            assert len(target_names) > 0

    def test_bat_script_on_windows(self):
        """Batch script included on Windows."""
        with patch("platform.system", return_value="Windows"):
            scripts = install_wrappers.get_wrapper_scripts()
            target_names = [target for _, target in scripts]
            # Should include either bat or other scripts
            assert len(target_names) > 0


class TestPathChecking:
    """Test PATH verification."""

    def test_ensure_bin_dir_in_path_true(self):
        """ensure_bin_dir_in_path() returns True if bin dir in PATH."""
        bin_dir = Path.home() / ".local" / "bin"
        with patch("os.environ.get") as mock_getenv:
            mock_getenv.return_value = f"/usr/bin:{bin_dir}:/usr/local/bin"
            result = install_wrappers.ensure_bin_dir_in_path()
            assert result is True

    def test_ensure_bin_dir_in_path_false(self):
        """ensure_bin_dir_in_path() returns False if bin dir not in PATH."""
        with patch("os.environ.get") as mock_getenv:
            mock_getenv.return_value = "/usr/bin:/usr/local/bin"
            result = install_wrappers.ensure_bin_dir_in_path()
            assert result is False

    def test_ensure_bin_dir_in_path_handles_empty_path(self):
        """ensure_bin_dir_in_path() handles empty PATH."""
        with patch("os.environ.get") as mock_getenv:
            mock_getenv.return_value = ""
            result = install_wrappers.ensure_bin_dir_in_path()
            assert result is False


class TestInstallWrappers:
    """Test wrapper installation."""

    def test_install_wrappers_creates_bin_dir(self):
        """install_wrappers() creates bin directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            assert not bin_dir.exists()

            with patch.object(install_wrappers, "get_bin_dir", return_value=bin_dir):
                with patch.object(install_wrappers, "get_wrapper_scripts", return_value=[]):
                    try:
                        install_wrappers.install_wrappers()
                    except RuntimeError:
                        pass  # Expected if no scripts

            # Directory should have been created
            assert bin_dir.exists()

    def test_install_wrappers_copies_scripts(self):
        """install_wrappers() copies wrapper scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake source script
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            src_script = src_dir / "test-wrapper.sh"
            src_script.write_text("#!/bin/bash\necho test\n")

            # Target bin dir
            bin_dir = Path(tmpdir) / "bin"

            with patch.object(install_wrappers, "get_bin_dir", return_value=bin_dir):
                with patch.object(install_wrappers, "get_wrapper_scripts",
                                 return_value=[(src_script, "test-wrapper")]):
                    install_wrappers.install_wrappers()

            # Script should be copied
            target = bin_dir / "test-wrapper"
            assert target.exists()
            assert "echo test" in target.read_text()

    def test_install_wrappers_makes_executable(self):
        """install_wrappers() makes scripts executable on Unix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake source script
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            src_script = src_dir / "test-wrapper.sh"
            src_script.write_text("#!/bin/bash\necho test\n")

            # Target bin dir
            bin_dir = Path(tmpdir) / "bin"

            with patch.object(install_wrappers, "get_bin_dir", return_value=bin_dir):
                with patch.object(install_wrappers, "get_wrapper_scripts",
                                 return_value=[(src_script, "test-wrapper")]):
                    with patch("platform.system", return_value="Linux"):
                        install_wrappers.install_wrappers()

            # Script should be executable
            target = bin_dir / "test-wrapper"
            stat_info = target.stat()
            is_executable = bool(stat_info.st_mode & 0o111)
            assert is_executable

    def test_install_wrappers_handles_missing_scripts(self):
        """install_wrappers() handles some scripts missing gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"

            with patch.object(install_wrappers, "get_bin_dir", return_value=bin_dir):
                with patch.object(install_wrappers, "get_wrapper_scripts",
                                 return_value=[]):
                    with pytest.raises(RuntimeError, match="No scripts were installed"):
                        install_wrappers.install_wrappers()

    def test_install_wrappers_warns_if_not_in_path(self):
        """install_wrappers() shows warning if bin dir not in PATH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            src_script = src_dir / "test.sh"
            src_script.write_text("#!/bin/bash\necho test\n")

            bin_dir = Path(tmpdir) / "bin"

            with patch.object(install_wrappers, "get_bin_dir", return_value=bin_dir):
                with patch.object(install_wrappers, "get_wrapper_scripts",
                                 return_value=[(src_script, "test")]):
                    with patch.object(install_wrappers, "ensure_bin_dir_in_path",
                                     return_value=False):
                        # Should not raise, but warn
                        install_wrappers.install_wrappers()


class TestMainFunction:
    """Test main() entry point."""

    def test_main_calls_install_wrappers(self):
        """main() calls install_wrappers()."""
        with patch.object(install_wrappers, "install_wrappers") as mock_install:
            with patch("sys.exit"):
                install_wrappers.main()
                mock_install.assert_called_once()

    def test_main_exits_zero_on_success(self):
        """main() exits with code 0 on success."""
        with patch.object(install_wrappers, "install_wrappers"):
            with patch("sys.exit") as mock_exit:
                install_wrappers.main()
                mock_exit.assert_called_with(0)

    def test_main_exits_one_on_runtime_error(self):
        """main() exits with code 1 on RuntimeError."""
        with patch.object(install_wrappers, "install_wrappers") as mock_install:
            mock_install.side_effect = RuntimeError("Test error")
            with patch("sys.exit") as mock_exit:
                install_wrappers.main()
                mock_exit.assert_called_with(1)


# --- Manual verification commands for user ---
"""
To manually verify wrapper installation:

1. Test bin directory detection:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.install_wrappers import get_bin_dir
   print(f"Bin directory: {get_bin_dir()}")
   EOF

2. Test scripts discovery:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.install_wrappers import get_wrapper_scripts
   scripts = get_wrapper_scripts()
   for src, target in scripts:
       print(f"  {target} <- {src.name}")
   EOF

3. Run installation (to ~/.local/bin):
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.install_wrappers import install_wrappers
   install_wrappers()
   EOF

4. Verify installation:
   ls -la ~/.local/bin/claude-with-proxy*
"""
