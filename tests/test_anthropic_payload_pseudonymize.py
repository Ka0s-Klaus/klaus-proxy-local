#!/usr/bin/env python3
"""Tests del seudonimizador bidireccional de payloads Anthropic."""
from __future__ import annotations

import json

import pytest

import anthropic_payload_pseudonymize as ps

# --- Vault: consistencia y reversibilidad ------------------------------------


def test_vault_map_is_consistent():
    v = ps.Vault()
    a = v.map("localuser", "id")
    b = v.map("localuser", "id")
    assert a == b  # mismo real → mismo seudónimo
    assert a != "localuser"  # se ha ofuscado


def test_vault_is_bidirectional():
    v = ps.Vault()
    pseudo = v.map("secreto", "id")
    assert v.pseudo_to_real[pseudo] == "secreto"


def test_vault_distinct_values_distinct_pseudonyms():
    v = ps.Vault()
    assert v.map("uno", "id") != v.map("dos", "id")


def test_vault_map_path_is_pathlike():
    v = ps.Vault()
    pseudo = v.map_path("/home/localuser/proyectos/customer1-ecosistema1", "proj")
    assert pseudo.startswith("/proj_")
    assert v.pseudo_to_real[pseudo] == "/home/localuser/proyectos/customer1-ecosistema1"


# --- forward / restore round-trip -------------------------------------------


def _rules():
    return ps.Rules(
        path_prefixes=[
            ("/home/localuser/proyectos/customer1-ecosistema1", "proj"),
            ("/home/localuser", "home"),
        ],
        literals=["gituser", "localuser"],
        regexes=[(ps._EMAIL_RE, "email"), (ps._IPV4_RE, "ip")],
    )


def test_round_trip_restores_original():
    v = ps.Vault()
    rules = _rules()
    original = (
        "usuario localuser (git gituser) en "
        "/home/localuser/proyectos/customer1-ecosistema1/CLAUDE.md, "
        "correo dev1@example.com, gateway 203.0.113.10"
    )
    forward = ps.pseudonymize_text(original, v, rules)
    # Nada sensible sobrevive en claro.
    assert "localuser" not in forward
    assert "dev1@example.com" not in forward
    assert "203.0.113.10" not in forward
    # Reversión exacta.
    assert ps.restore_text(forward, v) == original


def test_repo_root_wins_over_home_longest_first():
    v = ps.Vault()
    rules = _rules()
    text = "/home/localuser/proyectos/customer1-ecosistema1/dashboard/app.py"
    forward = ps.pseudonymize_text(text, v, rules)
    # El prefijo de repo (más largo) se aplica antes que el home.
    assert forward.startswith("/proj_")
    assert "/home_" not in forward
    assert ps.restore_text(forward, v) == text


def test_git_identity_wins_over_username_longest_first():
    v = ps.Vault()
    rules = _rules()
    forward = ps.pseudonymize_text("gituser", v, rules)
    # No debe degradarse a "<pseudo-usuario>_orgcode4".
    assert "_orgcode4" not in forward
    assert ps.restore_text(forward, v) == "gituser"


def test_relative_path_structure_preserved():
    v = ps.Vault()
    rules = _rules()
    text = (
        "/home/localuser/proyectos/customer1-ecosistema1/dashboard/backend/app/main.py"
    )
    forward = ps.pseudonymize_text(text, v, rules)
    # La estructura relativa (y la extensión) siguen visibles para el modelo.
    assert forward.endswith("/dashboard/backend/app/main.py")


def test_model_generated_path_reverts_to_real():
    """Una ruta NUEVA que el modelo invente bajo el seudónimo se traduce a real."""
    v = ps.Vault()
    rules = _rules()
    ps.pseudonymize_text("/home/localuser/proyectos/customer1-ecosistema1", v, rules)
    proj_pseudo = v.real_to_pseudo["/home/localuser/proyectos/customer1-ecosistema1"]
    model_output = f"{proj_pseudo}/docs/nuevo.md"
    restored = ps.restore_text(model_output, v)
    assert restored == "/home/localuser/proyectos/customer1-ecosistema1/docs/nuevo.md"


# --- regex -------------------------------------------------------------------


def test_email_and_ip_detected():
    v = ps.Vault()
    rules = _rules()
    forward = ps.pseudonymize_text("mail dev3@example.com ip 10.0.0.1", v, rules)
    assert "dev3@example.com" not in forward
    assert "10.0.0.1" not in forward
    assert ps.restore_text(forward, v) == "mail dev3@example.com ip 10.0.0.1"


def test_version_string_not_mistaken_for_ip():
    v = ps.Vault()
    rules = _rules()
    forward = ps.pseudonymize_text("anthropic-version 2023-06-01 v4.8.0", v, rules)
    assert forward == "anthropic-version 2023-06-01 v4.8.0"


# --- idempotencia ------------------------------------------------------------


def test_pseudonymize_is_idempotent():
    v = ps.Vault()
    rules = _rules()
    text = "localuser en /home/localuser/x y mail dev1@example.com"
    once = ps.pseudonymize_text(text, v, rules)
    twice = ps.pseudonymize_text(once, v, rules)
    assert once == twice


# --- payload JSON completo ---------------------------------------------------


def test_full_json_body_round_trip():
    v = ps.Vault()
    rules = _rules()
    body = json.dumps(
        {
            "model": "claude-opus-4-8",
            "messages": [
                {
                    "role": "user",
                    "content": "lee /home/localuser/proyectos/customer1-ecosistema1/CLAUDE.md",
                },
                {"role": "assistant", "content": "autor gituser"},
            ],
        },
        ensure_ascii=False,
    )
    forward = ps.pseudonymize_text(body, v, rules)
    assert "localuser" not in forward
    # Sigue siendo JSON válido tras la sustitución.
    assert json.loads(forward)["model"] == "claude-opus-4-8"
    assert ps.restore_text(forward, v) == body


# --- persistencia del vault --------------------------------------------------


def test_vault_save_and_load(tmp_path):
    path = tmp_path / "vault.json"
    v = ps.Vault()
    pseudo = v.map("localuser", "id")
    v.save(path)
    loaded = ps.Vault.load(path)
    assert loaded.real_to_pseudo["localuser"] == pseudo
    assert loaded.pseudo_to_real[pseudo] == "localuser"


def test_vault_load_missing_returns_empty(tmp_path):
    loaded = ps.Vault.load(tmp_path / "noexiste.json")
    assert loaded.real_to_pseudo == {}


# --- host targeting ----------------------------------------------------------


@pytest.mark.parametrize(
    "host,expected",
    [
        ("api.anthropic.com", True),
        ("llm.tools.cloud.customer1.es", True),
        ("api.openai.com", False),
    ],
)
def test_is_target_host(host, expected):
    assert ps.is_target_host(host) is expected


# --- palanca de rutas --------------------------------------------------------


def test_paths_lever_disabled_via_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_PATHS", "0")
    rules = ps.build_rules()
    assert rules.path_prefixes == []


# --- Tier 1: secretos (redacción irreversible) -------------------------------


def _secret_rules():
    return ps.Rules(secret_regexes=list(ps._SECRET_RES), secret_kv=True)


# Los "secretos" son fixtures sintéticas ensambladas en runtime a partir de
# fragmentos, para que ningún escáner de credenciales (GitGuardian, etc.) las
# detecte como secretos reales en el código fuente.
_JWT_FIXTURE = ".".join(
    [
        "eyJ" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0",
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
    ]
)


@pytest.mark.parametrize(
    "secret,label",
    [
        ("AKIA" + "IOSFODNN7" + "EXAMPLE", "aws-access-key"),
        ("ghp_" + "a" * 36, "github-token"),
        ("AIza" + "b" * 35, "google-api-key"),
        ("xoxb-" + "123456789012-" + "abcdefghijkl", "slack-token"),
        (_JWT_FIXTURE, "jwt"),
    ],
)
def test_secret_is_redacted(secret, label):
    rules = _secret_rules()
    v = ps.Vault()
    out = ps.pseudonymize_text(f"credencial: {secret} fin", v, rules)
    assert secret not in out
    assert f"«REDACTED:{label}»" in out


def test_private_key_block_redacted():
    rules = _secret_rules()
    v = ps.Vault()
    # Marcadores PEM ensamblados en runtime para no incrustar un bloque de
    # clave privada literal que dispare los escáneres de secretos.
    _kind = "RSA PRIVATE KEY"
    pem = (
        f"-----BEGIN {_kind}-----\n"
        "MIIEowIBAAKCAQEA1234567890abcdef\n"
        f"-----END {_kind}-----"
    )
    out = ps.pseudonymize_text(f"clave:\n{pem}\nlisto", v, rules)
    assert "MIIEowIBAAKCAQEA" not in out
    assert "«REDACTED:private-key»" in out


def test_secret_kv_redacts_value_keeps_key():
    rules = _secret_rules()
    v = ps.Vault()
    # Valor ensamblado en runtime para no incrustar un literal tipo credencial.
    secret_val = "s3cr3t" + "-value-x"
    out = ps.pseudonymize_text(f'password="{secret_val}"', v, rules)
    assert secret_val not in out
    assert out.startswith('password="')  # la clave se conserva
    assert "«REDACTED:secret-kv»" in out


def test_secret_is_irreversible_not_in_vault():
    rules = _secret_rules()
    v = ps.Vault()
    forward = ps.pseudonymize_text("token=ghp_" + "z" * 36, v, rules)
    # No hay entradas de secreto en el vault → restore no lo reconstruye.
    assert v.real_to_pseudo == {}
    assert ps.restore_text(forward, v) == forward


def test_secret_redaction_is_idempotent():
    rules = _secret_rules()
    v = ps.Vault()
    once = ps.pseudonymize_text("api_key=" + "AKIA" + "IOSFODNN7" + "EXAMPLE", v, rules)
    twice = ps.pseudonymize_text(once, v, rules)
    assert once == twice


def test_secrets_disabled_via_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_SECRETS", "0")
    rules = ps.build_rules()
    assert rules.secret_regexes == []


def test_secret_kv_off_by_default():
    rules = ps.build_rules()
    assert rules.secret_kv is False  # ruidoso sobre código → opt-in


def test_secret_kv_on_via_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_SECRET_KV", "1")
    rules = ps.build_rules()
    assert rules.secret_kv is True


def test_secret_kv_does_not_match_getenv_call():
    """`password = os.getenv("X")` es código, no una credencial → no se toca."""
    rules = _secret_rules()
    v = ps.Vault()
    code = 'password = os.getenv("TP_WIN_DEFAULT_PASSWORD")'
    out = ps.pseudonymize_text(code, v, rules)
    assert out == code


# --- Transformación estructural sobre JSON (regresión del bug 400) -----------


def test_json_body_with_code_stays_valid():
    """El fallo real: regex sobre JSON serializado partía un escape `\\\"` y
    rompía el JSON. La transformación estructural debe conservarlo válido."""
    rules = _secret_rules()  # secret_kv activo (el que disparaba el bug)
    v = ps.Vault()
    body = json.dumps(
        {
            "messages": [
                {
                    "role": "user",
                    "content": '43\t        password = os.getenv("TP_WIN_DEFAULT_PASSWORD")\n',
                }
            ]
        },
        ensure_ascii=False,
    )
    out = ps.pseudonymize_body(body, v, rules)
    # No debe lanzar: sigue siendo JSON válido.
    parsed = json.loads(out)
    assert parsed["messages"][0]["role"] == "user"


def test_body_structural_round_trip():
    v = ps.Vault()
    rules = _rules()
    body = json.dumps(
        {
            "model": "claude-opus-4-8",
            "messages": [
                {
                    "role": "user",
                    "content": "lee /home/localuser/proyectos/customer1-ecosistema1/x.py",
                },
                {
                    "role": "assistant",
                    "content": 'ruta con "comillas" y \\backslash y gituser',
                },
            ],
        },
        ensure_ascii=False,
    )
    forward = ps.pseudonymize_body(body, v, rules)
    assert "localuser" not in forward
    assert json.loads(forward)["model"] == "claude-opus-4-8"  # JSON válido
    # restore_body reconstruye el original semánticamente (mismo objeto).
    assert json.loads(ps.restore_body(forward, v)) == json.loads(body)


def test_pseudonymize_body_non_json_falls_back_to_text():
    v = ps.Vault()
    rules = _rules()
    raw = "texto plano con localuser y dev1@example.com"
    out = ps.pseudonymize_body(raw, v, rules)
    assert "localuser" not in out
    assert ps.restore_body(out, v) == raw


# --- Tier 2: word-literals con frontera de palabra ---------------------------


def _word_rules():
    return ps.Rules(word_literals=["example-org", "orgcode4", "orgcode2", "orgcode1"])


def test_word_literal_boundary_does_not_corrupt_substrings():
    """`orgcode2` no debe tocar `HTTPS`; `orgcode1` no debe tocar `COMMIT`."""
    v = ps.Vault()
    rules = _word_rules()
    text = "HTTPS y COMMIT intactos"
    out = ps.pseudonymize_text(text, v, rules)
    assert out == text  # nada casó


def test_word_literal_matches_standalone_token():
    v = ps.Vault()
    rules = _word_rules()
    out = ps.pseudonymize_text("cliente orgcode2 y cliente orgcode1", v, rules)
    assert " orgcode2" not in out.replace("cliente", "")  # el token suelto sí se mapeó
    assert "orgcode2" not in out
    assert "orgcode1" not in out
    assert ps.restore_text(out, v) == "cliente orgcode2 y cliente orgcode1"


def test_word_literal_longest_first():
    """`example-org` se mapea entero, no como `<pseudo>-global-delivery`."""
    v = ps.Vault()
    rules = _word_rules()
    out = ps.pseudonymize_text("org example-org aquí", v, rules)
    assert "-global-delivery" not in out
    assert ps.restore_text(out, v) == "org example-org aquí"


def test_word_literals_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PSEUDO_WORD_LITERALS", "orgcode1,orgcode2,orgcode3")
    rules = ps.build_rules()
    assert "orgcode1" in rules.word_literals
    assert "orgcode2" in rules.word_literals
    assert "orgcode3" in rules.word_literals


def test_git_remote_tokens_parsing():
    toks = ps._parse_remote_tokens(
        "dev2@example.com:example-org/customer1-ecosistema1.git"
    )
    assert "example-org" in toks
    assert "customer1-ecosistema1" in toks
    assert "github" not in toks  # genérico descartado


# --- redact_secrets_body: original con secretos Tier-1 redactados ------------


def test_redact_secrets_body_redacts_tier1_keeps_reversible():
    """El cuerpo `original`: redacta credenciales Tier-1 REALES pero deja
    intactos los datos reversibles (identidad, rutas) — esos van aparte."""
    rules = ps.Rules(
        literals=["localuser"],
        path_prefixes=[("/home/localuser/proyectos/customer1-ecosistema1", "proj")],
        secret_regexes=list(ps._SECRET_RES),
    )
    aws_key = "AKIA" + "IOSFODNN7" + "EXAMPLE"  # contiguo solo en runtime
    body = json.dumps(
        {
            "m": f"user localuser en /home/localuser/proyectos/customer1-ecosistema1/x.py key {aws_key}"
        }
    )
    out = ps.redact_secrets_body(body, rules)
    # El secreto real desaparece; queda el placeholder irreversible.
    assert aws_key not in out
    assert "REDACTED:aws-access-key" in out
    # Reversibles NO tocados aquí (los seudonimiza pseudonymize_body).
    assert "localuser" in out
    assert "/home/localuser/proyectos/customer1-ecosistema1/x.py" in out
    json.loads(out)  # sigue siendo JSON válido


def test_redact_secrets_body_non_json_falls_back_to_text():
    rules = ps.Rules(secret_regexes=list(ps._SECRET_RES))
    out = ps.redact_secrets_body(
        "plain " + "AKIA" + "IOSFODNN7" + "EXAMPLE tail", rules
    )
    assert out == "plain «REDACTED:aws-access-key» tail"


def test_redact_secrets_body_empty():
    assert ps.redact_secrets_body("", ps.Rules()) == ""


# --- Coloreado de logs --------------------------------------------------------


class _FakeStream:
    """Stream con isatty() controlable — evita depender de la terminal real."""

    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_colorize_wraps_by_level_when_enabled():
    assert ps.colorize("x", "ok", enabled=True) == "\033[32mx\033[0m"
    assert ps.colorize("x", "warn", enabled=True) == "\033[33mx\033[0m"
    assert ps.colorize("x", "error", enabled=True) == "\033[31mx\033[0m"


def test_colorize_noop_when_disabled_or_unknown_level():
    assert ps.colorize("x", "ok", enabled=False) == "x"
    assert ps.colorize("x", "desconocido", enabled=True) == "x"


def test_color_enabled_force_flag_beats_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("ANTHROPIC_LOG_COLOR", "1")  # force=1 manda sobre NO_COLOR
    assert ps.color_enabled(_FakeStream(False)) is True
    monkeypatch.setenv("ANTHROPIC_LOG_COLOR", "0")  # force=0 desactiva aun con TTY
    assert ps.color_enabled(_FakeStream(True)) is False


def test_color_enabled_no_color_present_disables(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_LOG_COLOR", raising=False)
    monkeypatch.setenv("NO_COLOR", "")  # su mera presencia (aun vacío) desactiva
    assert ps.color_enabled(_FakeStream(True)) is False


def test_color_enabled_falls_back_to_tty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_LOG_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert ps.color_enabled(_FakeStream(True)) is True
    assert ps.color_enabled(_FakeStream(False)) is False


# --- Fail-closed --------------------------------------------------------------


def test_fail_closed_body_is_bytes_and_explains_reason():
    body = ps.fail_closed_body(ValueError("cuerpo ilegible"))
    assert isinstance(body, bytes)
    text = body.decode("utf-8")
    assert "fail-closed" in text
    assert "NO se ha" in text  # deja claro que la request no salió
    # Incluye el tipo y el mensaje de la excepción para diagnóstico.
    assert "ValueError" in text
    assert "cuerpo ilegible" in text
