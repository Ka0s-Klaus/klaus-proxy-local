#!/usr/bin/env python3
"""Tests for FASE 1.2: Auto-cert generation (certs.py).

Verifies:
- Mitmproxy cert detection
- Cert generation (mocked)
- Mitmproxy installation check
- Idempotent behavior
- Error handling
"""
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import certs


class TestMitmproxyCertPaths:
    """Test certificate path utilities."""

    def test_mitmproxy_cert_dir_is_home_mitmproxy(self):
        """mitmproxy_cert_dir() returns ~/.mitmproxy"""
        cert_dir = certs.mitmproxy_cert_dir()
        expected = Path.home() / ".mitmproxy"
        assert cert_dir == expected

    def test_mitmproxy_cert_file_is_pem(self):
        """mitmproxy_cert_file() returns ~/.mitmproxy/mitmproxy-ca-cert.pem"""
        cert_file = certs.mitmproxy_cert_file()
        expected = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
        assert cert_file == expected

    def test_cert_file_path_is_in_cert_dir(self):
        """Cert file is inside cert directory."""
        cert_dir = certs.mitmproxy_cert_dir()
        cert_file = certs.mitmproxy_cert_file()
        assert cert_file.parent == cert_dir


class TestMitmproxyDetection:
    """Test mitmproxy installation detection."""

    def test_is_mitmproxy_installed_returns_bool(self):
        """is_mitmproxy_installed() returns a boolean."""
        result = certs.is_mitmproxy_installed()
        assert isinstance(result, bool)

    def test_is_mitmproxy_installed_checks_version(self):
        """is_mitmproxy_installed() runs 'mitmproxy --version'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            certs.is_mitmproxy_installed()
            mock_run.assert_called_once()
            # Check that --version was in the call
            args = mock_run.call_args[0][0]
            assert "mitmproxy" in args
            assert "--version" in args

    def test_is_mitmproxy_installed_true_on_success(self):
        """is_mitmproxy_installed() returns True if mitmproxy --version succeeds."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = certs.is_mitmproxy_installed()
            assert result is True

    def test_is_mitmproxy_installed_false_on_nonzero_exit(self):
        """is_mitmproxy_installed() returns False if exit code != 0."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = certs.is_mitmproxy_installed()
            assert result is False

    def test_is_mitmproxy_installed_false_on_not_found(self):
        """is_mitmproxy_installed() returns False if mitmproxy not in PATH."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = certs.is_mitmproxy_installed()
            assert result is False

    def test_is_mitmproxy_installed_false_on_timeout(self):
        """is_mitmproxy_installed() returns False if check times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("mitmproxy", 5)
            result = certs.is_mitmproxy_installed()
            assert result is False

    def test_is_mitmproxy_installed_false_on_os_error(self):
        """is_mitmproxy_installed() returns False on OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            result = certs.is_mitmproxy_installed()
            assert result is False


class TestCertGeneration:
    """Test certificate generation."""

    def test_generate_mitmproxy_certs_runs_mitmproxy(self):
        """generate_mitmproxy_certs() runs 'mitmproxy -q'."""
        with patch("subprocess.run") as mock_run:
            with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
                mock_cert_file.return_value = Path("/tmp/test-cert.pem")
                mock_run.return_value = MagicMock()
                # Create the mock cert file
                with patch("pathlib.Path.exists", return_value=True):
                    result = certs.generate_mitmproxy_certs()

        assert result is True

    def test_generate_mitmproxy_certs_handles_timeout(self):
        """generate_mitmproxy_certs() handles timeout gracefully."""
        with patch("subprocess.run") as mock_run:
            with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
                mock_cert_file.return_value = Path("/tmp/test-cert.pem")
                # Timeout is expected behavior
                mock_run.side_effect = subprocess.TimeoutExpired("mitmproxy", 3)
                # Create the mock cert file
                with patch("pathlib.Path.exists", return_value=True):
                    result = certs.generate_mitmproxy_certs()

        # Should still return True if cert file exists after timeout
        assert result is True

    def test_generate_mitmproxy_certs_false_if_cert_missing(self):
        """generate_mitmproxy_certs() returns False if cert not created."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()
            with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
                cert_path = MagicMock()
                cert_path.exists.return_value = False
                mock_cert_file.return_value = cert_path
                result = certs.generate_mitmproxy_certs()

        assert result is False

    def test_generate_mitmproxy_certs_false_on_error(self):
        """generate_mitmproxy_certs() returns False on subprocess error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = certs.generate_mitmproxy_certs()

        assert result is False


class TestEnsureMitmproxyCerts:
    """Test the main ensure_mitmproxy_certs() function."""

    def test_returns_cert_path(self):
        """ensure_mitmproxy_certs() returns a Path object."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = Path("/tmp/test.pem")
            mock_cert_file.return_value = cert_path
            with patch("pathlib.Path.exists", return_value=True):
                result = certs.ensure_mitmproxy_certs()

        assert isinstance(result, Path)

    def test_returns_existing_cert_immediately(self):
        """ensure_mitmproxy_certs() returns existing cert without regenerating."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = MagicMock()
            cert_path.exists.return_value = True
            mock_cert_file.return_value = cert_path

            result = certs.ensure_mitmproxy_certs()

            assert result == cert_path
            # Should not try to generate if cert exists
            cert_path.exists.assert_called_once()

    def test_raises_if_mitmproxy_not_installed(self):
        """ensure_mitmproxy_certs() raises RuntimeError if mitmproxy not installed."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = MagicMock()
            cert_path.exists.return_value = False
            mock_cert_file.return_value = cert_path

            with patch.object(certs, "is_mitmproxy_installed", return_value=False):
                with pytest.raises(RuntimeError, match="mitmproxy not found"):
                    certs.ensure_mitmproxy_certs()

    def test_raises_if_cert_generation_fails(self):
        """ensure_mitmproxy_certs() raises RuntimeError if cert generation fails."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = MagicMock()
            cert_path.exists.return_value = False
            mock_cert_file.return_value = cert_path

            with patch.object(certs, "is_mitmproxy_installed", return_value=True):
                with patch.object(certs, "generate_mitmproxy_certs", return_value=False):
                    with pytest.raises(RuntimeError, match="Failed to generate"):
                        certs.ensure_mitmproxy_certs()

    def test_idempotent_same_path(self):
        """Calling ensure_mitmproxy_certs() twice returns same path."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = Path("/tmp/test.pem")
            mock_cert_file.return_value = cert_path

            with patch("pathlib.Path.exists", return_value=True):
                result1 = certs.ensure_mitmproxy_certs()
                result2 = certs.ensure_mitmproxy_certs()

            assert result1 == result2
            # Second call should not try to regenerate
            mock_cert_file.assert_called()


class TestErrorMessages:
    """Test error messages are helpful."""

    def test_mitmproxy_not_found_suggests_install(self):
        """RuntimeError message includes installation instructions."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = MagicMock()
            cert_path.exists.return_value = False
            mock_cert_file.return_value = cert_path

            with patch.object(certs, "is_mitmproxy_installed", return_value=False):
                with pytest.raises(RuntimeError) as exc_info:
                    certs.ensure_mitmproxy_certs()

                error_msg = str(exc_info.value)
                # Should suggest installation
                assert "brew install" in error_msg or "pip install" in error_msg

    def test_cert_generation_failure_shows_path(self):
        """RuntimeError message shows expected cert path."""
        with patch.object(certs, "mitmproxy_cert_file") as mock_cert_file:
            cert_path = Path("/home/user/.mitmproxy/mitmproxy-ca-cert.pem")
            mock_cert_file.return_value = cert_path

            with patch.object(certs, "is_mitmproxy_installed", return_value=True):
                with patch.object(certs, "generate_mitmproxy_certs", return_value=False):
                    with pytest.raises(RuntimeError) as exc_info:
                        certs.ensure_mitmproxy_certs()

                error_msg = str(exc_info.value)
                # Should show the expected path
                assert str(cert_path) in error_msg


# --- Manual verification commands for user ---
"""
To manually verify certs.py works (without actually generating certs):

1. Check detection (if mitmproxy installed):
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.certs import is_mitmproxy_installed

   installed = is_mitmproxy_installed()
   print(f"Mitmproxy installed: {installed}")
   EOF

2. Check paths:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.certs import mitmproxy_cert_dir, mitmproxy_cert_file

   print(f"Cert dir:  {mitmproxy_cert_dir()}")
   print(f"Cert file: {mitmproxy_cert_file()}")
   EOF

3. Full integration (if mitmproxy installed):
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.certs import ensure_mitmproxy_certs

   try:
       cert = ensure_mitmproxy_certs()
       print(f"✅ Cert ready at: {cert}")
   except RuntimeError as e:
       print(f"❌ Error: {e}")
   EOF
"""
