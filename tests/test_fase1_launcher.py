#!/usr/bin/env python3
"""Tests for FASE 1.3: Smart proxy launcher (launcher.py).

Verifies:
- Auto-config generation on launch
- Auto-cert generation on launch
- mitmdump subprocess management
- Signal handling (Ctrl+C)
- Dashboard output
- Error handling
"""
import signal
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local.launcher import ProxyLauncher


class TestProxyLauncherInit:
    """Test ProxyLauncher initialization."""

    def test_launcher_initializes(self):
        """ProxyLauncher() creates a launcher instance."""
        launcher = ProxyLauncher()
        assert launcher is not None
        assert launcher.config is None
        assert launcher.cert_file is None
        assert launcher.mitmdump_process is None

    def test_launcher_has_correct_host_port(self):
        """ProxyLauncher has correct HOST and PORT."""
        assert ProxyLauncher.HOST == "127.0.0.1"
        assert ProxyLauncher.PORT == 8899


class TestEnsurePrerequisites:
    """Test prerequisite setup (config + certs)."""

    def test_ensure_prerequisites_calls_config_setup(self):
        """ensure_prerequisites() calls init_config_if_missing()."""
        launcher = ProxyLauncher()
        with patch("Klaus_proxy_local.launcher.init_config_if_missing") as mock_config:
            with patch("Klaus_proxy_local.launcher.ensure_mitmproxy_certs") as mock_certs:
                mock_config.return_value = {"version": "0.1.0"}
                mock_certs.return_value = Path("/tmp/cert.pem")

                launcher.ensure_prerequisites()
                mock_config.assert_called_once()

    def test_ensure_prerequisites_calls_cert_setup(self):
        """ensure_prerequisites() calls ensure_mitmproxy_certs()."""
        launcher = ProxyLauncher()
        with patch("Klaus_proxy_local.launcher.init_config_if_missing") as mock_config:
            with patch("Klaus_proxy_local.launcher.ensure_mitmproxy_certs") as mock_certs:
                mock_config.return_value = {"version": "0.1.0"}
                mock_certs.return_value = Path("/tmp/cert.pem")

                launcher.ensure_prerequisites()
                mock_certs.assert_called_once()

    def test_ensure_prerequisites_stores_config(self):
        """ensure_prerequisites() stores config in self.config."""
        launcher = ProxyLauncher()
        test_config = {"version": "0.1.0", "salt": "test"}
        with patch("Klaus_proxy_local.launcher.init_config_if_missing") as mock_config:
            with patch("Klaus_proxy_local.launcher.ensure_mitmproxy_certs") as mock_certs:
                mock_config.return_value = test_config
                mock_certs.return_value = Path("/tmp/cert.pem")

                launcher.ensure_prerequisites()
                assert launcher.config == test_config

    def test_ensure_prerequisites_stores_cert_file(self):
        """ensure_prerequisites() stores cert path in self.cert_file."""
        launcher = ProxyLauncher()
        cert_path = Path("/home/user/.mitmproxy/cert.pem")
        with patch("Klaus_proxy_local.launcher.init_config_if_missing") as mock_config:
            with patch("Klaus_proxy_local.launcher.ensure_mitmproxy_certs") as mock_certs:
                mock_config.return_value = {"version": "0.1.0"}
                mock_certs.return_value = cert_path

                launcher.ensure_prerequisites()
                assert launcher.cert_file == cert_path

    def test_ensure_prerequisites_raises_on_config_error(self):
        """ensure_prerequisites() raises if config setup fails."""
        launcher = ProxyLauncher()
        with patch("Klaus_proxy_local.launcher.init_config_if_missing") as mock_config:
            mock_config.side_effect = Exception("Config error")

            with pytest.raises(RuntimeError, match="Config setup failed"):
                launcher.ensure_prerequisites()

    def test_ensure_prerequisites_raises_on_cert_error(self):
        """ensure_prerequisites() raises if cert setup fails."""
        launcher = ProxyLauncher()
        with patch("Klaus_proxy_local.launcher.init_config_if_missing") as mock_config:
            with patch("Klaus_proxy_local.launcher.ensure_mitmproxy_certs") as mock_certs:
                mock_config.return_value = {"version": "0.1.0"}
                mock_certs.side_effect = RuntimeError("Cert error")

                with pytest.raises(RuntimeError, match="Cert setup failed"):
                    launcher.ensure_prerequisites()


class TestShowDashboard:
    """Test dashboard output."""

    def test_show_dashboard_outputs_host_port(self, capsys):
        """show_dashboard() outputs HOST and PORT."""
        launcher = ProxyLauncher()
        launcher.cert_file = Path("/tmp/cert.pem")

        launcher.show_dashboard()
        captured = capsys.readouterr()

        assert "127.0.0.1" in captured.out
        assert "8899" in captured.out

    def test_show_dashboard_outputs_config_path(self, capsys):
        """show_dashboard() outputs config path."""
        launcher = ProxyLauncher()
        launcher.cert_file = Path("/tmp/cert.pem")

        launcher.show_dashboard()
        captured = capsys.readouterr()

        assert "~/.klaus-proxy/config.json" in captured.out

    def test_show_dashboard_outputs_captures_path(self, capsys):
        """show_dashboard() outputs captures path."""
        launcher = ProxyLauncher()
        launcher.cert_file = Path("/tmp/cert.pem")

        launcher.show_dashboard()
        captured = capsys.readouterr()

        assert "~/.klaus-proxy/captures/" in captured.out

    def test_show_dashboard_outputs_cert_path(self, capsys):
        """show_dashboard() outputs certificate path."""
        launcher = ProxyLauncher()
        launcher.cert_file = Path("/home/user/.mitmproxy/cert.pem")

        launcher.show_dashboard()
        captured = capsys.readouterr()

        assert "/home/user/.mitmproxy/cert.pem" in captured.out

    def test_show_dashboard_outputs_usage_instructions(self, capsys):
        """show_dashboard() outputs usage instructions."""
        launcher = ProxyLauncher()
        launcher.cert_file = Path("/tmp/cert.pem")

        launcher.show_dashboard()
        captured = capsys.readouterr()

        assert "HTTP_PROXY" in captured.out
        assert "HTTPS_PROXY" in captured.out


class TestLaunchMitmdump:
    """Test mitmdump subprocess launch."""

    def test_launch_mitmdump_calls_subprocess(self):
        """launch_mitmdump() calls subprocess.Popen."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_process = MagicMock()
                mock_process.poll.return_value = None  # Still running
                mock_popen.return_value = mock_process

                with patch("time.sleep"):
                    launcher.launch_mitmdump()

                mock_popen.assert_called_once()

    def test_launch_mitmdump_includes_pseudonymize_addon(self):
        """launch_mitmdump() includes pseudonymization addon."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_process = MagicMock()
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                with patch("time.sleep"):
                    launcher.launch_mitmdump()

                call_args = mock_popen.call_args[0][0]
                assert "anthropic_payload_pseudonymize.py" in str(call_args)

    def test_launch_mitmdump_includes_capture_addon(self):
        """launch_mitmdump() includes capture addon."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_process = MagicMock()
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                with patch("time.sleep"):
                    launcher.launch_mitmdump()

                call_args = mock_popen.call_args[0][0]
                assert "anthropic_payload_capture.py" in str(call_args)

    def test_launch_mitmdump_includes_port(self):
        """launch_mitmdump() includes correct port."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_process = MagicMock()
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                with patch("time.sleep"):
                    launcher.launch_mitmdump()

                call_args = mock_popen.call_args[0][0]
                assert "8899" in str(call_args)

    def test_launch_mitmdump_raises_if_pseudonymize_addon_missing(self):
        """launch_mitmdump() raises if pseudonymization addon not found."""
        launcher = ProxyLauncher()
        with patch("pathlib.Path.exists") as mock_exists:
            # First addon missing, second exists
            mock_exists.side_effect = [False, True]

            with pytest.raises(RuntimeError, match="Pseudonymization addon not found"):
                launcher.launch_mitmdump()

    def test_launch_mitmdump_raises_if_capture_addon_missing(self):
        """launch_mitmdump() raises if capture addon not found."""
        launcher = ProxyLauncher()
        with patch("pathlib.Path.exists") as mock_exists:
            # First addon exists, second missing
            mock_exists.side_effect = [True, False]

            with pytest.raises(RuntimeError, match="Capture addon not found"):
                launcher.launch_mitmdump()

    def test_launch_mitmdump_raises_if_mitmdump_not_found(self):
        """launch_mitmdump() raises if mitmdump not in PATH."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_popen.side_effect = FileNotFoundError()

                with pytest.raises(RuntimeError, match="mitmdump not found"):
                    launcher.launch_mitmdump()

    def test_launch_mitmdump_raises_if_process_fails_immediately(self):
        """launch_mitmdump() raises if mitmdump fails to start."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_process = MagicMock()
                mock_process.poll.return_value = 1  # Process exited
                mock_process.communicate.return_value = ("", "Error message")
                mock_popen.return_value = mock_process

                with patch("time.sleep"):
                    with pytest.raises(RuntimeError, match="mitmdump failed to start"):
                        launcher.launch_mitmdump()

    def test_launch_mitmdump_stores_process(self):
        """launch_mitmdump() stores process in self.mitmdump_process."""
        launcher = ProxyLauncher()
        with patch("subprocess.Popen") as mock_popen:
            with patch("pathlib.Path.exists", return_value=True):
                mock_process = MagicMock()
                mock_process.poll.return_value = None
                mock_popen.return_value = mock_process

                with patch("time.sleep"):
                    launcher.launch_mitmdump()

                assert launcher.mitmdump_process is mock_process


class TestShutdown:
    """Test proxy shutdown."""

    def test_shutdown_terminates_process(self):
        """shutdown() calls terminate() on mitmdump process."""
        launcher = ProxyLauncher()
        mock_process = MagicMock()
        launcher.mitmdump_process = mock_process

        launcher.shutdown()
        mock_process.terminate.assert_called_once()

    def test_shutdown_waits_for_process(self):
        """shutdown() waits for process to terminate."""
        launcher = ProxyLauncher()
        mock_process = MagicMock()
        launcher.mitmdump_process = mock_process

        launcher.shutdown()
        mock_process.wait.assert_called()

    def test_shutdown_kills_on_timeout(self):
        """shutdown() kills process if terminate timeout."""
        launcher = ProxyLauncher()
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired("mitmdump", 5)
        launcher.mitmdump_process = mock_process

        launcher.shutdown()
        mock_process.kill.assert_called_once()

    def test_shutdown_no_error_if_no_process(self):
        """shutdown() doesn't error if no process running."""
        launcher = ProxyLauncher()
        launcher.mitmdump_process = None

        # Should not raise
        launcher.shutdown()


class TestHandleSignal:
    """Test signal handling."""

    def test_handle_signal_calls_shutdown(self):
        """handle_signal() calls shutdown()."""
        launcher = ProxyLauncher()
        with patch.object(launcher, "shutdown") as mock_shutdown:
            with patch("sys.exit"):
                launcher.handle_signal(signal.SIGINT, None)
                mock_shutdown.assert_called_once()

    def test_handle_signal_exits(self):
        """handle_signal() exits the program."""
        launcher = ProxyLauncher()
        launcher.mitmdump_process = None

        with pytest.raises(SystemExit):
            launcher.handle_signal(signal.SIGINT, None)


class TestMainFunction:
    """Test main() entry point."""

    def test_main_creates_launcher(self):
        """main() creates a ProxyLauncher instance."""
        with patch.object(ProxyLauncher, "run"):
            from Klaus_proxy_local.launcher import main

            main()
            # If no exception, test passes

    def test_main_calls_run(self):
        """main() calls launcher.run()."""
        with patch.object(ProxyLauncher, "run") as mock_run:
            from Klaus_proxy_local.launcher import main

            main()
            mock_run.assert_called_once()


# --- Manual verification commands for user ---
"""
To manually verify launcher.py works:

1. Check imports:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.launcher import ProxyLauncher, main
   print("✅ Imports successful")
   EOF

2. Check launcher initialization:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.launcher import ProxyLauncher

   launcher = ProxyLauncher()
   print(f"✅ Launcher created")
   print(f"   HOST: {launcher.HOST}")
   print(f"   PORT: {launcher.PORT}")
   EOF

3. Full launch (if mitmproxy installed and addons present):
   python3 src/Klaus_proxy_local/launcher.py
   # Press Ctrl+C to stop
"""
