#!/usr/bin/env python3
"""Tests for FASE 1.5: Shell detection + auto-install (setup_shell.py).

Verifies:
- Shell detection (bash, zsh, fish, powershell)
- Config file discovery
- Hook generation (shell-specific)
- User permission asking
- Hook installation
- Idempotence
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import setup_shell


class TestShellDetection:
    """Test shell detection."""

    def test_detect_shell_from_env(self):
        """detect_shell() uses $SHELL environment variable."""
        with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
            result = setup_shell.detect_shell()
            assert result == "bash"

    def test_detect_bash_shell(self):
        """detect_shell() identifies bash."""
        with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
            result = setup_shell.detect_shell()
            assert result == "bash"

    def test_detect_zsh_shell(self):
        """detect_shell() identifies zsh."""
        with patch.dict("os.environ", {"SHELL": "/bin/zsh"}):
            result = setup_shell.detect_shell()
            assert result == "zsh"

    def test_detect_fish_shell(self):
        """detect_shell() identifies fish."""
        with patch.dict("os.environ", {"SHELL": "/usr/bin/fish"}):
            result = setup_shell.detect_shell()
            assert result == "fish"

    def test_detect_sh_shell(self):
        """detect_shell() identifies sh (POSIX shell)."""
        with patch.dict("os.environ", {"SHELL": "/bin/sh"}):
            result = setup_shell.detect_shell()
            assert result == "sh"

    def test_detect_powershell(self):
        """detect_shell() detects PowerShell."""
        with patch.dict("os.environ", {"SHELL": ""}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = setup_shell.detect_shell()
                assert result == "powershell"

    def test_detect_unknown_shell(self):
        """detect_shell() returns 'unknown' if not detected."""
        with patch.dict("os.environ", {"SHELL": ""}):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("platform.system", return_value="Linux"):
                    result = setup_shell.detect_shell()
                    assert result == "unknown"

    def test_detect_shell_returns_string(self):
        """detect_shell() always returns a string."""
        with patch.dict("os.environ", {"SHELL": "/bin/bash"}):
            result = setup_shell.detect_shell()
            assert isinstance(result, str)


class TestShellConfigFile:
    """Test shell config file discovery."""

    def test_bash_config_file_is_bashrc(self):
        """get_shell_config_file() returns ~/.bashrc for bash."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch.object(Path, "exists", return_value=True):
                config_file = setup_shell.get_shell_config_file()
                assert "bashrc" in str(config_file)

    def test_zsh_config_file_is_zshrc(self):
        """get_shell_config_file() returns ~/.zshrc for zsh."""
        with patch.object(setup_shell, "detect_shell", return_value="zsh"):
            config_file = setup_shell.get_shell_config_file()
            assert "zshrc" in str(config_file)

    def test_fish_config_file_path(self):
        """get_shell_config_file() returns ~/.config/fish/config.fish for fish."""
        with patch.object(setup_shell, "detect_shell", return_value="fish"):
            config_file = setup_shell.get_shell_config_file()
            assert "fish" in str(config_file)
            assert "config.fish" in str(config_file)

    def test_powershell_config_file_path(self):
        """get_shell_config_file() returns PowerShell profile path."""
        with patch.object(setup_shell, "detect_shell", return_value="powershell"):
            with patch("platform.system", return_value="Windows"):
                with patch("os.getenv", return_value="C:\\AppData"):
                    config_file = setup_shell.get_shell_config_file()
                    assert config_file is not None
                    assert "profile" in str(config_file).lower()

    def test_cmd_config_file_returns_none(self):
        """get_shell_config_file() returns None for cmd (unsupported)."""
        with patch.object(setup_shell, "detect_shell", return_value="cmd"):
            config_file = setup_shell.get_shell_config_file()
            assert config_file is None

    def test_unknown_shell_returns_none(self):
        """get_shell_config_file() returns None for unknown shell."""
        with patch.object(setup_shell, "detect_shell", return_value="unknown"):
            config_file = setup_shell.get_shell_config_file()
            assert config_file is None


class TestShellHook:
    """Test shell-specific hook generation."""

    def test_bash_hook_is_string(self):
        """get_shell_hook() returns string for bash."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            hook = setup_shell.get_shell_hook()
            assert isinstance(hook, str)
            assert len(hook) > 0

    def test_bash_hook_contains_claude_proxy(self):
        """Bash hook mentions claude-proxy."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            hook = setup_shell.get_shell_hook()
            assert "claude-proxy" in hook

    def test_zsh_hook_similar_to_bash(self):
        """Zsh hook is similar to bash."""
        with patch.object(setup_shell, "detect_shell", return_value="zsh"):
            hook = setup_shell.get_shell_hook()
            assert "claude-proxy" in hook
            assert "pgrep" in hook

    def test_fish_hook_uses_fish_syntax(self):
        """Fish hook uses fish-specific syntax."""
        with patch.object(setup_shell, "detect_shell", return_value="fish"):
            hook = setup_shell.get_shell_hook()
            assert "claude-proxy" in hook
            assert "set -gx HTTPS_PROXY" in hook

    def test_powershell_hook_is_unsupported(self):
        """Windows shells are not supported (#105)."""
        with patch.object(setup_shell, "detect_shell", return_value="powershell"):
            assert setup_shell.get_shell_hook() == ""

    def test_cmd_hook_returns_empty(self):
        """CMD shell hook returns empty string (unsupported)."""
        with patch.object(setup_shell, "detect_shell", return_value="cmd"):
            hook = setup_shell.get_shell_hook()
            assert hook == ""

    def test_all_hooks_mention_klaus_proxy(self):
        """All hooks mention Klaus Proxy."""
        for shell in ["bash", "zsh", "fish", "powershell"]:
            with patch.object(setup_shell, "detect_shell", return_value=shell):
                hook = setup_shell.get_shell_hook()
                if hook:  # Non-empty hooks
                    assert "Klaus Proxy" in hook


class TestUserPermission:
    """Test user permission prompting."""

    def test_ask_user_permission_returns_bool(self):
        """ask_user_permission() returns boolean."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch("builtins.input", return_value="n"):
                result = setup_shell.ask_user_permission()
                assert isinstance(result, bool)

    def test_ask_user_permission_yes_response(self):
        """ask_user_permission() returns True for 'y' response."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch("builtins.input", return_value="y"):
                result = setup_shell.ask_user_permission()
                assert result is True

    def test_ask_user_permission_no_response(self):
        """ask_user_permission() returns False for 'n' response."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch("builtins.input", return_value="n"):
                result = setup_shell.ask_user_permission()
                assert result is False

    def test_ask_user_permission_empty_response(self):
        """ask_user_permission() returns False for empty response (default N)."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch("builtins.input", return_value=""):
                result = setup_shell.ask_user_permission()
                assert result is False

    def test_ask_user_permission_unsupported_shell(self):
        """ask_user_permission() returns False for unsupported shell."""
        with patch.object(setup_shell, "detect_shell", return_value="cmd"):
            with patch.object(setup_shell, "get_shell_config_file", return_value=None):
                result = setup_shell.ask_user_permission()
                assert result is False


class TestAddHookToConfig:
    """Test adding hook to shell config file."""

    def test_add_hook_creates_file(self):
        """add_hook_to_shell_config() creates file if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config"
            hook_code = "# test hook\n"

            setup_shell.add_hook_to_shell_config(config_file, hook_code)

            assert config_file.exists()
            assert "test hook" in config_file.read_text()

    def test_add_hook_appends_to_existing(self):
        """add_hook_to_shell_config() appends to existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config"
            config_file.write_text("existing content\n")

            hook_code = "# new hook\n"
            setup_shell.add_hook_to_shell_config(config_file, hook_code)

            content = config_file.read_text()
            assert "existing content" in content
            assert "new hook" in content

    def test_add_hook_idempotent(self):
        """add_hook_to_shell_config() is idempotent (doesn't duplicate)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config"
            hook_code = "# Klaus Proxy Local — Auto-startup\ntest\n"

            # Add hook first time
            setup_shell.add_hook_to_shell_config(config_file, hook_code)
            content1 = config_file.read_text()

            # Add same hook second time
            setup_shell.add_hook_to_shell_config(config_file, hook_code)
            content2 = config_file.read_text()

            # Content should be identical (hook not duplicated)
            assert content1 == content2

    def test_add_hook_creates_parent_directory(self):
        """add_hook_to_shell_config() creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "deep" / "nested" / "config"
            hook_code = "# hook\n"

            setup_shell.add_hook_to_shell_config(config_file, hook_code)

            assert config_file.exists()
            assert config_file.parent.exists()

    def test_add_hook_sets_permissions(self):
        """add_hook_to_shell_config() sets secure permissions (0o600)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config"
            hook_code = "# hook\n"

            setup_shell.add_hook_to_shell_config(config_file, hook_code)

            stat_info = config_file.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_add_hook_handles_missing_newline(self):
        """add_hook_to_shell_config() adds newline before hook if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test_config"
            config_file.write_text("existing content")  # No newline

            hook_code = "# hook\n"
            setup_shell.add_hook_to_shell_config(config_file, hook_code)

            content = config_file.read_text()
            # Should have newline between existing and hook
            assert "existing content\n" in content or "existing content\n\n" in content


class TestRunSetup:
    """Test complete setup flow."""

    def test_run_setup_calls_all_steps(self):
        """run_setup() orchestrates detection, asking, and installation."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch.object(setup_shell, "ask_user_permission", return_value=False):
                # Should not error, just return
                setup_shell.run_setup()

    def test_run_setup_exits_on_unknown_shell(self):
        """run_setup() exits if shell is unknown."""
        with patch.object(setup_shell, "detect_shell", return_value="unknown"):
            with pytest.raises(SystemExit):
                setup_shell.run_setup()

    def test_run_setup_exits_if_user_declines(self):
        """run_setup() exits gracefully if user says no."""
        with patch.object(setup_shell, "detect_shell", return_value="bash"):
            with patch.object(setup_shell, "ask_user_permission", return_value=False):
                # Doesn't raise, just exits
                setup_shell.run_setup()


class TestMainFunction:
    """Test main() entry point."""

    def test_main_calls_run_setup(self):
        """main() calls run_setup()."""
        with patch.object(setup_shell, "run_setup") as mock_setup:
            with patch("sys.exit"):
                setup_shell.main()
                mock_setup.assert_called_once()

    def test_main_exits_zero_on_success(self):
        """main() exits with code 0 on success."""
        with patch.object(setup_shell, "run_setup"):
            with patch("sys.exit") as mock_exit:
                setup_shell.main()
                mock_exit.assert_called_with(0)

    def test_main_handles_keyboard_interrupt(self):
        """main() handles Ctrl+C gracefully."""
        with patch.object(setup_shell, "run_setup") as mock_setup:
            mock_setup.side_effect = KeyboardInterrupt()
            with patch("sys.exit") as mock_exit:
                setup_shell.main()
                mock_exit.assert_called_with(0)

    def test_main_exits_one_on_exception(self):
        """main() exits with code 1 on exception."""
        with patch.object(setup_shell, "run_setup") as mock_setup:
            mock_setup.side_effect = RuntimeError("Test error")
            with patch("sys.exit") as mock_exit:
                setup_shell.main()
                mock_exit.assert_called_with(1)


class TestIntegration:
    """Integration tests across components."""

    def test_full_setup_flow_bash(self):
        """Full setup flow works for bash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "bashrc"

            with patch.object(setup_shell, "detect_shell", return_value="bash"):
                with patch.object(
                    setup_shell, "get_shell_config_file", return_value=config_file
                ):
                    with patch.object(
                        setup_shell, "ask_user_permission", return_value=True
                    ):
                        with patch(
                            "Klaus_proxy_local.install_wrappers.install_wrappers"
                        ):
                            # Should not raise
                            setup_shell.run_setup()

            # Config file should have been created with hook
            assert config_file.exists()
            content = config_file.read_text()
            assert "Klaus Proxy" in content

    def test_full_setup_flow_fish(self):
        """Full setup flow works for fish."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.fish"

            with patch.object(setup_shell, "detect_shell", return_value="fish"):
                with patch.object(
                    setup_shell, "get_shell_config_file", return_value=config_file
                ):
                    with patch.object(
                        setup_shell, "ask_user_permission", return_value=True
                    ):
                        with patch(
                            "Klaus_proxy_local.install_wrappers.install_wrappers"
                        ):
                            setup_shell.run_setup()

            assert config_file.exists()
            content = config_file.read_text()
            assert "Klaus Proxy" in content


# --- Manual verification commands for user ---
"""
To manually verify setup_shell.py works:

1. Test shell detection:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.setup_shell import detect_shell
   print(f"Detected shell: {detect_shell()}")
   EOF

2. Test config file discovery:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.setup_shell import detect_shell, get_shell_config_file
   shell = detect_shell()
   config = get_shell_config_file()
   print(f"Shell: {shell}")
   print(f"Config: {config}")
   EOF

3. Test hook generation:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.setup_shell import detect_shell, get_shell_hook
   from unittest.mock import patch

   for shell_name in ['bash', 'zsh', 'fish']:
       with patch('Klaus_proxy_local.setup_shell.detect_shell', return_value=shell_name):
           hook = get_shell_hook()
           print(f"{shell_name}:")
           print(f"  Length: {len(hook)} bytes")
           print(f"  Has claude-proxy: {'claude-proxy' in hook}")
   EOF

4. Run interactive setup (will ask for confirmation):
   python3 -m Klaus_proxy_local.setup_shell
   # Or:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.setup_shell import run_setup
   # Answer 'n' when prompted
   run_setup()
   EOF
"""


# --- #105: el hook arranca el proxy y exporta HTTPS_PROXY -----------------


def _hook(shell):
    with patch.object(setup_shell, "detect_shell", return_value=shell):
        return setup_shell.get_shell_hook()


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_hook_exports_https_proxy_and_starts_proxy(shell):
    from Klaus_proxy_local.launcher import ProxyLauncher

    hook = _hook(shell)
    url = f"http://{ProxyLauncher.HOST}:{ProxyLauncher.PORT}"
    assert hook.startswith("\n" + setup_shell.HOOK_BEGIN)
    assert hook.rstrip().endswith(setup_shell.HOOK_END)
    assert url in hook and "HTTPS_PROXY" in hook and "NO_PROXY" in hook
    assert "nohup claude-proxy" in hook and "logs/autostart.log" in hook
    assert "klaus-env.sh" in hook and "klaus-off" in hook and "klaus-on" in hook


def test_bash_hook_runs(tmp_path):
    """Ejecutado en bash: arranca claude-proxy si no corre y exporta las variables."""
    home = tmp_path / "home"
    (home / ".klaus-proxy").mkdir(parents=True)
    (home / ".klaus-proxy" / "klaus-env.sh").write_text("export KLAUS_ENV_LOADED=1\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in {
        "claude-proxy": 'touch "$HOME/started"',
        "pgrep": "exit 1",  # no hay proxy en marcha
    }.items():
        (bindir / name).write_text(f"#!/bin/sh\n{body}\n")
        (bindir / name).chmod(0o755)
    script = tmp_path / "rc.sh"
    script.write_text(
        _hook("bash")
        + 'sleep 1; echo "$KLAUS_ENV_LOADED $HTTPS_PROXY"; '
        + 'klaus-off >/dev/null; echo "off=${HTTPS_PROXY:-}"\n'
    )
    r = subprocess.run(
        ["bash", str(script)],
        env={"HOME": str(home), "PATH": f"{bindir}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    lines = r.stdout.split()
    assert lines[0] == "1" and lines[1].endswith(":8899") and lines[2] == "off="
    assert (home / "started").exists()
    assert (home / ".klaus-proxy" / "logs").is_dir()


def test_add_hook_replaces_legacy_and_is_idempotent(tmp_path):
    rc = tmp_path / ".zshrc"
    legacy = (
        "\n# 🔐 Klaus Proxy Local — Auto-startup (FASE 1.5)\n"
        "# Load SSL/TLS variables for git, curl, etc.\n"
        "[ -f ~/.klaus-proxy/klaus-env.sh ] && source ~/.klaus-proxy/klaus-env.sh\n"
        "# Start proxy if not running\n"
        "if ! pgrep -f 'claude-proxy|mitmdump' > /dev/null 2>&1; then\n"
        "  (claude-proxy > ~/.klaus-proxy/proxy.log 2>&1 &)\n"
        "fi\n"
    )
    rc.write_text("alias ll='ls -l'\n" + legacy + "export EDITOR=vim\n")
    hook = _hook("zsh")
    setup_shell.add_hook_to_shell_config(rc, hook)
    text = rc.read_text()
    assert "FASE 1.5" not in text and "proxy.log" not in text
    assert "alias ll='ls -l'" in text and "export EDITOR=vim" in text
    assert text.count(setup_shell.HOOK_BEGIN) == 1
    setup_shell.add_hook_to_shell_config(rc, hook)
    assert rc.read_text() == text
    # Un bloque distinto (p. ej. de una versión anterior) se sustituye
    rc.write_text(text.replace("klaus-off", "klaus-viejo"))
    setup_shell.add_hook_to_shell_config(rc, hook)
    assert rc.read_text().count(setup_shell.HOOK_BEGIN) == 1
    assert "klaus-viejo" not in rc.read_text()
