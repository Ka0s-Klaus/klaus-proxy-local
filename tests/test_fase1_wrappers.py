#!/usr/bin/env python3
"""Tests for FASE 1.4: Wrapper scripts (claude-with-proxy.*).

Verifies:
- Wrapper scripts exist
- Correct permissions (executable)
- Environment variables set correctly
- Arguments passed through to claude
- Each shell variant works
"""
import os
import subprocess
from pathlib import Path

import pytest


class TestWrapperScriptsExist:
    """Test wrapper script files."""

    @pytest.fixture
    def scripts_dir(self):
        """Get scripts directory."""
        return Path(__file__).parent.parent / "scripts"

    def test_bash_wrapper_exists(self, scripts_dir):
        """claude-with-proxy.sh exists."""
        script = scripts_dir / "claude-with-proxy.sh"
        assert script.exists(), f"Missing: {script}"

    def test_fish_wrapper_exists(self, scripts_dir):
        """claude-with-proxy.fish exists."""
        script = scripts_dir / "claude-with-proxy.fish"
        assert script.exists(), f"Missing: {script}"

    def test_ps1_wrapper_exists(self, scripts_dir):
        """claude-with-proxy.ps1 exists."""
        script = scripts_dir / "claude-with-proxy.ps1"
        assert script.exists(), f"Missing: {script}"

    def test_bat_wrapper_exists(self, scripts_dir):
        """claude-with-proxy.bat exists."""
        script = scripts_dir / "claude-with-proxy.bat"
        assert script.exists(), f"Missing: {script}"


class TestBashWrapperContent:
    """Test bash wrapper script content."""

    @pytest.fixture
    def bash_script(self):
        """Get bash wrapper path."""
        return Path(__file__).parent.parent / "scripts" / "claude-with-proxy.sh"

    def test_bash_sets_http_proxy(self, bash_script):
        """Bash script sets HTTP_PROXY."""
        content = bash_script.read_text()
        assert "HTTP_PROXY" in content
        assert "127.0.0.1:8899" in content

    def test_bash_sets_https_proxy(self, bash_script):
        """Bash script sets HTTPS_PROXY."""
        content = bash_script.read_text()
        assert "HTTPS_PROXY" in content

    def test_bash_sets_lowercase_proxies(self, bash_script):
        """Bash script sets lowercase proxy vars for some tools."""
        content = bash_script.read_text()
        assert "http_proxy" in content
        assert "https_proxy" in content

    def test_bash_execs_claude(self, bash_script):
        """Bash script executes claude."""
        content = bash_script.read_text()
        assert "exec claude" in content or "exec claude" in content

    def test_bash_passes_arguments(self, bash_script):
        """Bash script passes arguments to claude."""
        content = bash_script.read_text()
        assert '"$@"' in content

    def test_bash_has_shebang(self, bash_script):
        """Bash script has correct shebang."""
        content = bash_script.read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_bash_executable(self, bash_script):
        """Bash script is executable."""
        stat_info = bash_script.stat()
        is_executable = bool(stat_info.st_mode & 0o111)
        assert is_executable, f"{bash_script} is not executable"


class TestFishWrapperContent:
    """Test fish wrapper script content."""

    @pytest.fixture
    def fish_script(self):
        """Get fish wrapper path."""
        return Path(__file__).parent.parent / "scripts" / "claude-with-proxy.fish"

    def test_fish_sets_http_proxy(self, fish_script):
        """Fish script sets HTTP_PROXY."""
        content = fish_script.read_text()
        assert "HTTP_PROXY" in content
        assert "127.0.0.1:8899" in content

    def test_fish_uses_set_x(self, fish_script):
        """Fish script uses 'set -x' for environment variables."""
        content = fish_script.read_text()
        assert "set -x HTTP_PROXY" in content

    def test_fish_execs_claude(self, fish_script):
        """Fish script executes claude."""
        content = fish_script.read_text()
        assert "exec claude" in content

    def test_fish_passes_arguments(self, fish_script):
        """Fish script passes arguments to claude."""
        content = fish_script.read_text()
        assert "$argv" in content

    def test_fish_has_shebang(self, fish_script):
        """Fish script has correct shebang."""
        content = fish_script.read_text()
        assert content.startswith("#!/usr/bin/env fish")

    def test_fish_executable(self, fish_script):
        """Fish script is executable."""
        stat_info = fish_script.stat()
        is_executable = bool(stat_info.st_mode & 0o111)
        assert is_executable, f"{fish_script} is not executable"


class TestPowerShellWrapperContent:
    """Test PowerShell wrapper script content."""

    @pytest.fixture
    def ps1_script(self):
        """Get PowerShell wrapper path."""
        return Path(__file__).parent.parent / "scripts" / "claude-with-proxy.ps1"

    def test_ps1_sets_env_http_proxy(self, ps1_script):
        """PowerShell script sets HTTP_PROXY via env:."""
        content = ps1_script.read_text()
        assert "$env:HTTP_PROXY" in content
        assert "127.0.0.1:8899" in content

    def test_ps1_sets_env_https_proxy(self, ps1_script):
        """PowerShell script sets HTTPS_PROXY."""
        content = ps1_script.read_text()
        assert "$env:HTTPS_PROXY" in content

    def test_ps1_has_param_block(self, ps1_script):
        """PowerShell script has param() block."""
        content = ps1_script.read_text()
        assert "param(" in content

    def test_ps1_captures_arguments(self, ps1_script):
        """PowerShell script captures Arguments."""
        content = ps1_script.read_text()
        assert "[string[]]$Arguments" in content

    def test_ps1_calls_claude(self, ps1_script):
        """PowerShell script calls claude."""
        content = ps1_script.read_text()
        assert "& claude" in content

    def test_ps1_passes_arguments(self, ps1_script):
        """PowerShell script passes arguments to claude."""
        content = ps1_script.read_text()
        assert "@Arguments" in content

    def test_ps1_has_shebang(self, ps1_script):
        """PowerShell script has shebang."""
        content = ps1_script.read_text()
        assert content.startswith("#!/usr/bin/env pwsh")


class TestBatchWrapperContent:
    """Test batch wrapper script content."""

    @pytest.fixture
    def bat_script(self):
        """Get batch wrapper path."""
        return Path(__file__).parent.parent / "scripts" / "claude-with-proxy.bat"

    def test_bat_sets_http_proxy(self, bat_script):
        """Batch script sets HTTP_PROXY."""
        content = bat_script.read_text()
        assert "HTTP_PROXY" in content
        assert "127.0.0.1:8899" in content

    def test_bat_uses_set(self, bat_script):
        """Batch script uses 'set' to set variables."""
        content = bat_script.read_text()
        assert "set HTTP_PROXY" in content

    def test_bat_calls_claude(self, bat_script):
        """Batch script calls claude."""
        content = bat_script.read_text()
        assert "claude" in content

    def test_bat_passes_arguments(self, bat_script):
        """Batch script passes arguments to claude."""
        content = bat_script.read_text()
        assert "%*" in content

    def test_bat_has_echo_off(self, bat_script):
        """Batch script has @echo off."""
        content = bat_script.read_text()
        assert "@echo off" in content


class TestProxyHostPort:
    """Test proxy host:port configuration across all scripts."""

    @pytest.fixture
    def scripts(self):
        """Get all wrapper script paths."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        return {
            "bash": scripts_dir / "claude-with-proxy.sh",
            "fish": scripts_dir / "claude-with-proxy.fish",
            "ps1": scripts_dir / "claude-with-proxy.ps1",
            "bat": scripts_dir / "claude-with-proxy.bat",
        }

    def test_all_scripts_use_localhost(self, scripts):
        """All scripts route through 127.0.0.1."""
        for name, script in scripts.items():
            content = script.read_text()
            assert "127.0.0.1" in content, f"{name} doesn't use 127.0.0.1"

    def test_all_scripts_use_port_8899(self, scripts):
        """All scripts use port 8899."""
        for name, script in scripts.items():
            content = script.read_text()
            assert "8899" in content, f"{name} doesn't use port 8899"

    def test_all_scripts_set_both_proxy_protocols(self, scripts):
        """All scripts set both HTTP and HTTPS proxy."""
        for name, script in scripts.items():
            content = script.read_text()
            assert "HTTP_PROXY" in content, f"{name} doesn't set HTTP_PROXY"
            assert "HTTPS_PROXY" in content, f"{name} doesn't set HTTPS_PROXY"


class TestWrapperDocumentation:
    """Test wrapper script documentation."""

    @pytest.fixture
    def scripts(self):
        """Get all wrapper script paths."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        return {
            "bash": scripts_dir / "claude-with-proxy.sh",
            "fish": scripts_dir / "claude-with-proxy.fish",
            "ps1": scripts_dir / "claude-with-proxy.ps1",
            "bat": scripts_dir / "claude-with-proxy.bat",
        }

    def test_all_scripts_have_usage_comment(self, scripts):
        """All scripts document usage."""
        for name, script in scripts.items():
            content = script.read_text()
            assert "Usage:" in content or "usage" in content.lower(), \
                f"{name} has no usage documentation"

    def test_all_scripts_explain_proxy(self, scripts):
        """All scripts explain proxy routing."""
        for name, script in scripts.items():
            content = script.read_text()
            has_proxy_doc = ("Klaus Proxy" in content or
                            "proxy" in content.lower())
            assert has_proxy_doc, f"{name} doesn't document proxy"

    def test_all_scripts_have_startup_instruction(self, scripts):
        """All scripts remind user to start proxy first."""
        for name, script in scripts.items():
            content = script.read_text()
            has_instruction = ("claude-proxy" in content or
                              "start the proxy" in content.lower())
            assert has_instruction, f"{name} doesn't mention starting proxy"


class TestWrapperIntegration:
    """Test wrapper integration aspects."""

    @pytest.fixture
    def bash_script(self):
        """Get bash wrapper path."""
        return Path(__file__).parent.parent / "scripts" / "claude-with-proxy.sh"

    def test_bash_wrapper_syntax_valid(self, bash_script):
        """Bash wrapper has valid syntax."""
        result = subprocess.run(
            ["bash", "-n", str(bash_script)],
            capture_output=True,
        )
        assert result.returncode == 0, \
            f"Bash syntax error: {result.stderr.decode()}"

    def test_fish_wrapper_syntax_valid(self):
        """Fish wrapper has valid syntax."""
        fish_script = Path(__file__).parent.parent / "scripts" / "claude-with-proxy.fish"
        result = subprocess.run(
            ["fish", "-n", str(fish_script)],
            capture_output=True,
        )
        # Fish might not be installed, so skip if not found
        if result.returncode != 127:
            assert result.returncode == 0, \
                f"Fish syntax error: {result.stderr.decode()}"

    def test_ps1_has_correct_encoding(self):
        """PowerShell wrapper should be UTF-8."""
        ps1_script = Path(__file__).parent.parent / "scripts" / "claude-with-proxy.ps1"
        # PowerShell can handle multiple encodings, but UTF-8 is preferred
        content = ps1_script.read_text(encoding="utf-8")
        assert len(content) > 0


# --- Manual verification commands for user ---
"""
To manually verify wrappers work:

1. Verify all scripts exist:
   ls -la scripts/claude-with-proxy.*

2. Check bash wrapper:
   bash -n scripts/claude-with-proxy.sh

3. Check fish wrapper (if fish installed):
   fish -n scripts/claude-with-proxy.fish

4. Test bash wrapper (dry run):
   bash scripts/claude-with-proxy.sh --version 2>&1 | head -1

5. Show proxy variables (don't run, just verify):
   grep -E 'HTTP_PROXY|HTTPS_PROXY' scripts/claude-with-proxy.sh
   grep -E 'HTTP_PROXY|HTTPS_PROXY' scripts/claude-with-proxy.fish
   grep -E 'HTTP_PROXY|HTTPS_PROXY' scripts/claude-with-proxy.ps1
   grep -E 'HTTP_PROXY|HTTPS_PROXY' scripts/claude-with-proxy.bat
"""
