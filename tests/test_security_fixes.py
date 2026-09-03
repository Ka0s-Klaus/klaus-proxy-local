#!/usr/bin/env python3
"""Tests for FASE 0 security hardening fixes.

Verifies:
1. Salt must be explicitly configured (no default)
2. Vault file permissions are secure (0o600)
3. Response reversal detects unreversed pseudonyms
"""
import os
import tempfile
from pathlib import Path

import pytest

import anthropic_payload_pseudonymize as ps


@pytest.fixture(autouse=True)
def restore_salt_after_test():
    """Ensure ANTHROPIC_PSEUDO_SALT is restored after each test."""
    original_salt = os.environ.get("ANTHROPIC_PSEUDO_SALT")
    yield
    # Restore original state after test
    if original_salt is not None:
        os.environ["ANTHROPIC_PSEUDO_SALT"] = original_salt
    else:
        os.environ.pop("ANTHROPIC_PSEUDO_SALT", None)


# --- FIX #1: Salt Weakness ---


class TestSaltHardening:
    """Security fix #1: Remove default salt, force explicit configuration."""

    def test_missing_salt_raises_runtime_error(self):
        """_salt() must raise RuntimeError if ANTHROPIC_PSEUDO_SALT is not set."""
        # Remove salt from environment
        old_val = os.environ.pop("ANTHROPIC_PSEUDO_SALT", None)
        try:
            with pytest.raises(RuntimeError, match="ANTHROPIC_PSEUDO_SALT"):
                ps._salt()
        finally:
            # Restore original value if it existed
            if old_val is not None:
                os.environ["ANTHROPIC_PSEUDO_SALT"] = old_val

    def test_salt_with_environment_variable(self):
        """_salt() returns configured salt from environment."""
        test_salt = "test-salt-32-character-hex-value0"
        old_val = os.environ.get("ANTHROPIC_PSEUDO_SALT")
        try:
            os.environ["ANTHROPIC_PSEUDO_SALT"] = test_salt
            assert ps._salt() == test_salt
        finally:
            if old_val is not None:
                os.environ["ANTHROPIC_PSEUDO_SALT"] = old_val
            else:
                os.environ.pop("ANTHROPIC_PSEUDO_SALT", None)

    def test_error_message_is_helpful(self):
        """RuntimeError message guides user on how to generate salt."""
        old_val = os.environ.pop("ANTHROPIC_PSEUDO_SALT", None)
        try:
            with pytest.raises(RuntimeError) as exc_info:
                ps._salt()
            error_msg = str(exc_info.value)
            assert "python" in error_msg.lower()
            assert "secrets.token_hex" in error_msg or "token_hex" in error_msg
        finally:
            if old_val is not None:
                os.environ["ANTHROPIC_PSEUDO_SALT"] = old_val


# --- FIX #2: Vault Permissions ---


class TestVaultPermissions:
    """Security fix #2: Vault file must be readable only by owner (0o600)."""

    def test_vault_save_creates_file_with_0o600_permissions(self):
        """Vault.save() creates file with mode 0o600 (owner read+write only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault.json"
            vault = ps.Vault()
            vault.map("secret-user", "id")
            vault.save(vault_path)

            # Verify file exists
            assert vault_path.exists(), f"Vault file not created at {vault_path}"

            # Verify permissions
            stat_info = vault_path.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_vault_parent_dir_has_0o700_permissions(self):
        """Vault parent directory is created with mode 0o700 (owner rwx only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_dir = Path(tmpdir) / "nested" / "deep" / "captures"
            vault_path = vault_dir / "vault.json"

            vault = ps.Vault()
            vault.save(vault_path)

            # Verify directory exists
            assert vault_dir.exists(), f"Directory not created at {vault_dir}"

            # Verify directory permissions
            stat_info = vault_dir.stat()
            mode = stat_info.st_mode & 0o777
            assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_vault_roundtrip_with_secure_permissions(self):
        """Vault can be loaded back even with secure permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault.json"
            salt = "test-salt-value-for-roundtrip"
            os.environ["ANTHROPIC_PSEUDO_SALT"] = salt

            try:
                # Create and save
                vault1 = ps.Vault()
                vault1.map("user1", "id")
                vault1.map("email@example.com", "email")
                vault1.save(vault_path)

                # Load back
                vault2 = ps.Vault.load(vault_path)

                # Verify mappings are preserved
                assert vault2.real_to_pseudo["user1"] == vault1.real_to_pseudo["user1"]
                assert (
                    vault2.real_to_pseudo["email@example.com"]
                    == vault1.real_to_pseudo["email@example.com"]
                )
            finally:
                os.environ.pop("ANTHROPIC_PSEUDO_SALT", None)


# --- FIX #3: Response Validation ---


class TestResponseValidation:
    """Security fix #3: Detect unreversed pseudonyms in response."""

    def test_find_unreversed_pseudonyms_empty_on_valid_reversal(self):
        """_find_unreversed_pseudonyms returns [] when all pseudonyms are reverted."""
        vault = ps.Vault()
        vault.map("/home/dev/project", "proj")
        vault.map("user@example.com", "email")

        # Response with all pseudonyms reverted
        text = "Read /home/dev/project/file.txt and send to user@example.com"
        unreversed = ps._find_unreversed_pseudonyms(text, vault)

        assert unreversed == []

    def test_find_unreversed_pseudonyms_detects_leaked_pseudonym(self):
        """_find_unreversed_pseudonyms finds pseudonyms that weren't reverted."""
        vault = ps.Vault()
        proj_pseudo = vault.map("/home/dev/project", "proj")
        email_pseudo = vault.map("user@example.com", "email")

        # Response with unreversed pseudonyms (leak)
        # Using actual pseudonyms generated by vault.map()
        text = f"Read /{proj_pseudo}/file.txt and email {email_pseudo}"
        unreversed = ps._find_unreversed_pseudonyms(text, vault)

        # Should detect both unreversed pseudonyms
        assert len(unreversed) > 0
        assert any("proj_" in p for p in unreversed)

    def test_find_unreversed_pseudonyms_with_collision_suffixes(self):
        """_find_unreversed_pseudonyms detects pseudonyms with 'z' collision resolution."""
        vault = ps.Vault()
        # Simulate a collision-resolved pseudonym
        vault.real_to_pseudo["value"] = "id_a1b2c3d4z"
        vault.pseudo_to_real["id_a1b2c3d4z"] = "value"

        text = "The value is id_a1b2c3d4z but should be real"
        unreversed = ps._find_unreversed_pseudonyms(text, vault)

        assert len(unreversed) > 0
        assert "id_a1b2c3d4z" in unreversed

    def test_find_unreversed_pseudonyms_avoids_false_positives(self):
        """_find_unreversed_pseudonyms doesn't flag non-pseudonym patterns."""
        vault = ps.Vault()

        # Text with patterns that look like pseudonyms but aren't in vault
        text = (
            "Version 1_a1b2c3d4 is different from id_a1b2c3d4. "
            "Use flag_xyz and token_abcdefgh for auth."
        )
        unreversed = ps._find_unreversed_pseudonyms(text, vault)

        # No unreversed pseudonyms because nothing is in the vault
        assert unreversed == []

    def test_restore_text_idempotent_after_pseudonymize(self):
        """Pseudonymize followed by restore returns original text."""
        vault = ps.Vault()
        rules = ps.Rules(
            path_prefixes=[("/home/dev/project", "proj")],
            literals=["devuser"],
        )

        original = "User devuser at /home/dev/project needs read access"
        pseudonymized = ps.pseudonymize_text(original, vault, rules)
        restored = ps.restore_text(pseudonymized, vault)

        assert restored == original
        # Verify no unreversed pseudonyms in restored text
        unreversed = ps._find_unreversed_pseudonyms(restored, vault)
        assert unreversed == []


# --- Integration: Vault → Pseudonymize → Restore ---


class TestSecurityFixesIntegration:
    """Integration tests combining all three security fixes."""

    def test_full_cycle_with_secure_salt_and_permissions(self):
        """Full cycle: secure salt + secure vault perms + response validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            salt = "integration-test-salt-value"
            vault_path = Path(tmpdir) / "vault.json"

            os.environ["ANTHROPIC_PSEUDO_SALT"] = salt
            try:
                # Create vault with secure permissions
                vault = ps.Vault()
                rules = ps.Rules(
                    path_prefixes=[("/home/dev", "home")],
                    literals=["testuser"],
                )

                # Pseudonymize request
                original = "User testuser with path /home/dev/secret"
                request_pseudo = ps.pseudonymize_text(original, vault, rules)
                assert "testuser" not in request_pseudo
                assert "/home/dev" not in request_pseudo

                # Save vault with secure permissions
                vault.save(vault_path)
                stat_info = vault_path.stat()
                assert (stat_info.st_mode & 0o777) == 0o600

                # Load vault and restore response
                vault_loaded = ps.Vault.load(vault_path)
                response_restored = ps.restore_text(request_pseudo, vault_loaded)

                # Verify restoration
                assert response_restored == original

                # Verify no unreversed pseudonyms
                unreversed = ps._find_unreversed_pseudonyms(
                    response_restored, vault_loaded
                )
                assert unreversed == []

            finally:
                os.environ.pop("ANTHROPIC_PSEUDO_SALT", None)
