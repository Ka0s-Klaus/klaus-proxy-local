#!/usr/bin/env python3
"""Tests for FASE 1.1: Auto-config generation (setup.py).

Verifies:
- Config auto-generates on first run
- All required keys present
- Salt is cryptographically random
- File/directory permissions are secure (0o600 config, 0o700 dirs)
- Idempotent (safe to call multiple times)
- No external dependencies
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from Klaus_proxy_local import setup


class TestConfigAutoGeneration:
    """Test FASE 1.1: Auto-config generation."""

    def test_config_auto_generates_on_first_run(self):
        """init_config_if_missing() creates config.json on first run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"

            # Mock config_dir() to use temp directory
            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            assert config_file.exists(), "config.json should be created"
            assert isinstance(config, dict), "Should return config dict"

    def test_config_has_all_required_keys(self):
        """Generated config has all required keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            required_keys = {"version", "salt", "hosts", "capture_dir", "vault_path", "log_level"}
            assert required_keys.issubset(config.keys()), f"Missing keys: {required_keys - config.keys()}"

    def test_config_version_correct(self):
        """Config version is 0.1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            assert config["version"] == "0.1.0"

    def test_config_hosts_correct(self):
        """Config has correct hosts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            expected_hosts = [
                "api.anthropic.com",
                "llm.tools.cloud.customer1.es",
            ]
            assert config["hosts"] == expected_hosts

    def test_salt_is_random(self):
        """Two runs generate different salts."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                config_dir1 = Path(tmpdir1)
                config_dir2 = Path(tmpdir2)

                with patch.object(setup, "config_dir", return_value=config_dir1):
                    config1 = setup.init_config_if_missing()

                with patch.object(setup, "config_dir", return_value=config_dir2):
                    config2 = setup.init_config_if_missing()

                salt1 = config1["salt"]
                salt2 = config2["salt"]

                assert salt1 != salt2, "Two runs should generate different salts"
                assert len(salt1) == 32, "Salt should be 32 hex chars (16 bytes)"
                assert len(salt2) == 32, "Salt should be 32 hex chars (16 bytes)"

    def test_salt_is_hex(self):
        """Generated salt is valid hex string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            salt = config["salt"]
            try:
                int(salt, 16)  # Should not raise if valid hex
            except ValueError:
                pytest.fail(f"Salt is not valid hex: {salt}")


class TestConfigPermissions:
    """Test secure file permissions (FASE 0 compliance)."""

    def test_config_file_permissions_0o600(self):
        """config.json has permissions 0o600 (owner read+write only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"

            with patch.object(setup, "config_dir", return_value=config_dir):
                setup.init_config_if_missing()

            stat_info = config_file.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_config_dir_permissions_0o700(self):
        """~/.klaus-proxy/ has permissions 0o700 (owner rwx only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                setup.init_config_if_missing()

            stat_info = config_dir.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_capture_dirs_permissions_0o700(self):
        """captures/ and captures/original/ and captures/sent/ have 0o700."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                with patch.object(setup, "original_dir", return_value=config_dir / "captures" / "original"):
                    with patch.object(setup, "sent_dir", return_value=config_dir / "captures" / "sent"):
                        setup.init_config_if_missing()

            # Check captures/ dir
            captures = config_dir / "captures"
            stat_info = captures.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o700, f"captures/ should be 0o700, got {oct(mode)}"

            # Check captures/original/ dir
            original = captures / "original"
            stat_info = original.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o700, f"captures/original/ should be 0o700, got {oct(mode)}"

            # Check captures/sent/ dir
            sent = captures / "sent"
            stat_info = sent.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o700, f"captures/sent/ should be 0o700, got {oct(mode)}"


class TestDirectoryCreation:
    """Test directory structure creation."""

    def test_config_directory_created(self):
        """~/.klaus-proxy/ is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                setup.init_config_if_missing()

            assert config_dir.exists()
            assert config_dir.is_dir()

    def test_captures_directory_created(self):
        """~/.klaus-proxy/captures/ is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            captures = config_dir / "captures"

            with patch.object(setup, "config_dir", return_value=config_dir):
                with patch.object(setup, "original_dir", return_value=captures / "original"):
                    with patch.object(setup, "sent_dir", return_value=captures / "sent"):
                        setup.init_config_if_missing()

            assert captures.exists()
            assert captures.is_dir()

    def test_original_directory_created(self):
        """~/.klaus-proxy/captures/original/ is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            captures = config_dir / "captures"
            original = captures / "original"

            with patch.object(setup, "config_dir", return_value=config_dir):
                with patch.object(setup, "original_dir", return_value=original):
                    with patch.object(setup, "sent_dir", return_value=captures / "sent"):
                        setup.init_config_if_missing()

            assert original.exists()
            assert original.is_dir()

    def test_sent_directory_created(self):
        """~/.klaus-proxy/captures/sent/ is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            captures = config_dir / "captures"
            sent = captures / "sent"

            with patch.object(setup, "config_dir", return_value=config_dir):
                with patch.object(setup, "original_dir", return_value=captures / "original"):
                    with patch.object(setup, "sent_dir", return_value=sent):
                        setup.init_config_if_missing()

            assert sent.exists()
            assert sent.is_dir()


class TestIdempotence:
    """Test that operations are idempotent (safe to call multiple times)."""

    def test_config_idempotent_same_salt(self):
        """Calling init_config_if_missing() twice returns same salt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config1 = setup.init_config_if_missing()
                config2 = setup.init_config_if_missing()

            assert config1["salt"] == config2["salt"], "Salt should be stable across calls"

    def test_config_idempotent_no_error(self):
        """Calling init_config_if_missing() twice doesn't error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                setup.init_config_if_missing()
                # Should not raise
                setup.init_config_if_missing()

    def test_config_can_be_loaded_multiple_times(self):
        """load_config() can be called multiple times safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config1 = setup.load_config()
                config2 = setup.load_config()
                config3 = setup.load_config()

            assert config1 == config2 == config3


class TestConfigContent:
    """Test the content of generated config."""

    def test_config_keys_are_strings(self):
        """All config keys are strings (valid JSON keys)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            for key in config.keys():
                assert isinstance(key, str)

    def test_config_values_are_json_serializable(self):
        """All config values can be JSON serialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            # Should not raise
            json.dumps(config)

    def test_log_level_default_is_info(self):
        """Default log_level is 'info'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            with patch.object(setup, "config_dir", return_value=config_dir):
                config = setup.init_config_if_missing()

            assert config["log_level"] == "info"


class TestGenerateSalt:
    """Test salt generation utility."""

    def test_generate_salt_returns_string(self):
        """_generate_salt() returns a string."""
        salt = setup._generate_salt()
        assert isinstance(salt, str)

    def test_generate_salt_length(self):
        """_generate_salt() returns 32 characters (16 bytes hex)."""
        salt = setup._generate_salt()
        assert len(salt) == 32

    def test_generate_salt_is_hex(self):
        """_generate_salt() returns valid hex."""
        salt = setup._generate_salt()
        try:
            int(salt, 16)
        except ValueError:
            pytest.fail(f"Salt is not valid hex: {salt}")

    def test_generate_salt_randomness(self):
        """Multiple calls to _generate_salt() produce different values."""
        salts = [setup._generate_salt() for _ in range(10)]
        unique_salts = set(salts)
        # With 10 salts, they should all be different (collision probability negligible)
        assert len(unique_salts) == 10, "All generated salts should be unique"


# --- Manual verification commands for user ---
"""
To manually verify setup.py works:

1. Set test env var:
   export ANTHROPIC_PSEUDO_SALT=test-salt-12345

2. Run Python:
   python3 << 'EOF'
   import sys
   sys.path.insert(0, 'src')
   from Klaus_proxy_local.setup import init_config_if_missing

   config = init_config_if_missing()
   print("✅ Config created:", config)

   import os, json
   cfg_dir = os.path.expanduser("~/.klaus-proxy")
   cfg_file = os.path.join(cfg_dir, "config.json")

   stat = os.stat(cfg_file)
   mode = stat.st_mode & 0o777
   print(f"✅ config.json permissions: {oct(mode)}")

   stat = os.stat(cfg_dir)
   mode = stat.st_mode & 0o777
   print(f"✅ ~/.klaus-proxy permissions: {oct(mode)}")
   EOF

3. Verify files:
   ls -la ~/.klaus-proxy/
   cat ~/.klaus-proxy/config.json
"""
