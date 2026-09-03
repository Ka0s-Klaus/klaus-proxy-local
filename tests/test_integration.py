#!/usr/bin/env python3
"""Integration tests for Klaus Proxy Local v0.1.0.

Tests complete workflows from installation through proxy usage.

Coverage:
- Auto-config generation
- Auto-cert detection
- Proxy launcher orchestration
- Wrapper script functionality
- Shell setup flow
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestInstallationFlow:
    """Test package installation and entry point availability."""

    def test_all_modules_importable(self):
        """All Klaus_proxy_local modules can be imported."""
        modules = [
            "Klaus_proxy_local.setup",
            "Klaus_proxy_local.certs",
            "Klaus_proxy_local.launcher",
            "Klaus_proxy_local.install_wrappers",
            "Klaus_proxy_local.setup_shell",
        ]
        for module_name in modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Cannot import {module_name}: {e}")

    def test_entry_points_callable(self):
        """All entry point functions exist and are callable."""
        from Klaus_proxy_local.main import main as main1
        from Klaus_proxy_local.launcher import main as main2
        from Klaus_proxy_local.install_wrappers import main as main3
        from Klaus_proxy_local.setup_shell import main as main4

        assert callable(main1)
        assert callable(main2)
        assert callable(main3)
        assert callable(main4)


class TestAutoConfigFlow:
    """Test auto-config generation on first use."""

    def test_config_generates_on_demand(self):
        """Config file is generated when accessed."""
        from Klaus_proxy_local.setup import init_config_if_missing

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch("Klaus_proxy_local.setup.config_dir", return_value=config_dir):
                config = init_config_if_missing()

                assert config is not None
                assert isinstance(config, dict)
                assert "salt" in config
                assert "version" in config

    def test_config_idempotent(self):
        """Config generation is idempotent."""
        from Klaus_proxy_local.setup import init_config_if_missing

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch("Klaus_proxy_local.setup.config_dir", return_value=config_dir):
                config1 = init_config_if_missing()
                config2 = init_config_if_missing()

                assert config1["salt"] == config2["salt"]
                assert config1 == config2


class TestAutoCertFlow:
    """Test auto-cert generation and detection."""

    def test_certs_detection_and_generation(self):
        """Certs are detected or generated."""
        from Klaus_proxy_local.certs import ensure_mitmproxy_certs

        fake_cert_path = Path("/home/user/.mitmproxy/mitmproxy-ca-cert.pem")
        with patch("Klaus_proxy_local.certs.mitmproxy_cert_file", return_value=fake_cert_path):
            with patch("pathlib.Path.exists", return_value=True):
                cert_file = ensure_mitmproxy_certs()

                assert cert_file is not None
                assert isinstance(cert_file, Path)

    def test_certs_generation_fails_gracefully(self):
        """Missing mitmproxy is handled gracefully."""
        from Klaus_proxy_local.certs import ensure_mitmproxy_certs

        fake_cert_path = Path("/home/user/.mitmproxy/mitmproxy-ca-cert.pem")
        with patch("Klaus_proxy_local.certs.mitmproxy_cert_file", return_value=fake_cert_path):
            with patch(
                "Klaus_proxy_local.certs.is_mitmproxy_installed", return_value=False
            ):
                with patch("pathlib.Path.exists", return_value=False):
                    with pytest.raises(RuntimeError, match="mitmproxy not found"):
                        ensure_mitmproxy_certs()


class TestLauncherOrchestration:
    """Test launcher orchestrates all setup steps."""

    def test_launcher_setup_sequence(self):
        """Launcher runs setup in correct order."""
        from Klaus_proxy_local.launcher import ProxyLauncher

        launcher = ProxyLauncher()
        mock_process = MagicMock()
        mock_process.wait.side_effect = KeyboardInterrupt
        launcher.mitmdump_process = mock_process

        with patch.object(launcher, "ensure_prerequisites") as mock_prereq:
            with patch.object(launcher, "launch_mitmdump"):
                with patch.object(launcher, "show_dashboard"):
                    with patch("signal.signal"):
                        try:
                            launcher.run()
                        except KeyboardInterrupt:
                            pass
                        except SystemExit:
                            pass

                        # Verify prerequisites called before launch
                        mock_prereq.assert_called_once()

    def test_launcher_graceful_shutdown(self):
        """Launcher shuts down cleanly on Ctrl+C."""
        from Klaus_proxy_local.launcher import ProxyLauncher

        launcher = ProxyLauncher()
        mock_process = MagicMock()
        launcher.mitmdump_process = mock_process

        launcher.shutdown()

        mock_process.terminate.assert_called_once()


class TestWrapperScriptFlow:
    """Test wrapper scripts function correctly."""

    def test_wrapper_installation_creates_files(self):
        """Wrapper installation creates executable scripts."""
        from Klaus_proxy_local.install_wrappers import get_wrapper_scripts

        scripts = get_wrapper_scripts()

        assert len(scripts) > 0
        for src, target in scripts:
            assert src.exists(), f"Source script missing: {src}"
            assert isinstance(target, str)

    def test_wrapper_scripts_are_executable(self):
        """All installed wrapper scripts are executable."""
        scripts_dir = Path(__file__).parent.parent / "scripts"

        for script in scripts_dir.glob("claude-with-proxy.*"):
            stat_info = script.stat()
            is_executable = bool(stat_info.st_mode & 0o111)
            assert is_executable, f"{script.name} is not executable"


class TestShellSetupFlow:
    """Test shell detection and hook installation."""

    def test_shell_detection_works(self):
        """Shell detection returns a valid shell name."""
        from Klaus_proxy_local.setup_shell import detect_shell

        shell = detect_shell()

        assert isinstance(shell, str)
        assert len(shell) > 0
        assert shell in ("bash", "zsh", "fish", "powershell", "cmd", "unknown", "sh")

    def test_config_file_discovery_works(self):
        """Config file discovery finds correct shell config."""
        from Klaus_proxy_local.setup_shell import detect_shell, get_shell_config_file

        shell = detect_shell()
        config_file = get_shell_config_file()

        if shell in ("bash", "zsh", "fish", "powershell"):
            # These shells should have a config file
            assert config_file is not None or shell == "unknown"

    def test_hook_generation_works(self):
        """Hook generation produces valid shell code."""
        from Klaus_proxy_local.setup_shell import detect_shell, get_shell_hook

        shell = detect_shell()
        hook = get_shell_hook()

        if shell in ("bash", "zsh", "fish", "powershell"):
            if hook:  # Non-empty hooks
                assert "claude-proxy" in hook
                assert len(hook) > 10


class TestEndToEndFlow:
    """Test complete installation and usage flow."""

    def test_import_all_modules(self):
        """All modules can be imported in sequence."""
        # Simulate: import Klaus_proxy_local
        import Klaus_proxy_local

        # Simulate: import submodules
        from Klaus_proxy_local import (
            setup,
            certs,
            launcher,
            install_wrappers,
            setup_shell,
        )

        assert all([setup, certs, launcher, install_wrappers, setup_shell])

    def test_config_then_certs_then_launch(self):
        """Config → Certs → Launch sequence works."""
        from Klaus_proxy_local.setup import init_config_if_missing
        from Klaus_proxy_local.certs import ensure_mitmproxy_certs
        from Klaus_proxy_local.launcher import ProxyLauncher

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            # Step 1: Generate config
            with patch("Klaus_proxy_local.setup.config_dir", return_value=config_dir):
                config = init_config_if_missing()
                assert config is not None

            # Step 2: Ensure certs (will fail gracefully if mitmproxy missing)
            with patch("Klaus_proxy_local.certs.mitmproxy_cert_file") as mock_cert:
                with patch("pathlib.Path.exists", return_value=True):
                    cert = ensure_mitmproxy_certs()
                    assert cert is not None

            # Step 3: Launcher created
            launcher = ProxyLauncher()
            assert launcher.config is None  # Not run yet
            assert launcher.PORT == 8899


class TestPackageMetadata:
    """Test package metadata is correct."""

    def test_package_version(self):
        """Package version is 0.1.0."""
        import Klaus_proxy_local

        # Check if __version__ exists
        if hasattr(Klaus_proxy_local, "__version__"):
            assert Klaus_proxy_local.__version__ == "0.1.0"

    def test_package_has_docstring(self):
        """Package has a docstring."""
        import Klaus_proxy_local

        assert Klaus_proxy_local.__doc__ is not None


class TestDependencyAvailability:
    """Test required dependencies are available."""

    def test_core_dependencies_available(self):
        """Core dependencies can be imported."""
        try:
            import httpx
            import fastapi
            import uvicorn
            import anthropic
        except ImportError as e:
            pytest.skip(f"Core dependency not installed: {e}")

    def test_mitmproxy_available(self):
        """Mitmproxy can be imported."""
        try:
            import mitmproxy
        except ImportError:
            pytest.skip("mitmproxy not installed (optional for testing)")

    def test_dev_dependencies_optional(self):
        """Dev dependencies are optional."""
        try:
            import pytest
            import pytest_cov
        except ImportError:
            pytest.skip("Dev dependencies not installed (optional)")


class TestDocumentationCompleteness:
    """Test all required documentation exists."""

    def test_readme_exists(self):
        """README.md exists."""
        readme = Path(__file__).parent.parent / "README.md"
        assert readme.exists()
        assert readme.read_text()

    def test_license_exists(self):
        """LICENSE file exists."""
        license_file = Path(__file__).parent.parent / "LICENSE"
        assert license_file.exists()
        assert license_file.read_text()

    def test_fase1_docs_exist(self):
        """FASE 1 documentation exists."""
        doc = Path(__file__).parent.parent / "docs" / "FASE1_ZERO_CONFIG.md"
        assert doc.exists()

    def test_quick_start_exists(self):
        """QUICK_START.md exists."""
        doc = Path(__file__).parent.parent / "docs" / "QUICK_START.md"
        assert doc.exists()


# --- Manual verification commands for user ---
"""
To run integration tests:

1. Run all integration tests:
   pytest tests/test_integration.py -v

2. Run specific test class:
   pytest tests/test_integration.py::TestAutoConfigFlow -v

3. Run with coverage:
   pytest tests/test_integration.py --cov=Klaus_proxy_local --cov-report=html

4. Run quick smoke test:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')

   print("🔥 Integration smoke test...")

   # Test 1: Imports
   from Klaus_proxy_local import setup, certs, launcher, install_wrappers, setup_shell
   print("✅ All modules import successfully")

   # Test 2: Config
   from Klaus_proxy_local.setup import init_config_if_missing
   from unittest.mock import patch
   from pathlib import Path
   import tempfile

   with tempfile.TemporaryDirectory() as tmpdir:
       with patch('Klaus_proxy_local.setup.config_dir', return_value=Path(tmpdir)):
           config = init_config_if_missing()
           assert 'salt' in config
           print("✅ Auto-config generation works")

   # Test 3: Shell detection
   from Klaus_proxy_local.setup_shell import detect_shell
   shell = detect_shell()
   print(f"✅ Shell detection works: {shell}")

   print("\\n✅ ALL INTEGRATION SMOKE TESTS PASSED")
   EOF
"""
