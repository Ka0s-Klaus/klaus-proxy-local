#!/usr/bin/env python3
"""Tests del seudonimizador bidireccional de payloads Anthropic."""
from __future__ import annotations

import json
import re
import stat

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


def _ip(*parts: int) -> str:
    """Construye una cadena con forma de IPv4 sin escribirla literal."""
    return ".".join(str(p) for p in parts)


@pytest.mark.parametrize(
    "addr",
    [_ip(10, 0, 0, 1), _ip(192, 168, 1, 10), _ip(255, 255, 255, 255), _ip(0, 0, 0, 0)],
)
def test_real_ipv4_still_detected(addr):
    v = ps.Vault()
    for text in (f"host {addr}", f"({addr}:443)", f"ip={addr}.", f"user@{addr}"):
        forward = ps.pseudonymize_text(text, v, _rules())
        assert addr not in forward, text
        assert ps.restore_text(forward, v) == text


@pytest.mark.parametrize(
    "text",
    [
        # Octeto fuera de rango: versión de Claude Code (#57)
        f"cc_version={_ip(2, 1, 312, 625)}; cc_entrypoint=cli",
        f"build {_ip(1, 2, 300, 4)}",
        # Octetos válidos pero en contexto de versión (#57)
        f"x-anthropic-billing-header: cc_version={_ip(2, 1, 3, 4)}; cc_entrypoint=cli",
        f"version: {_ip(1, 2, 3, 4)}".replace(": ", ":"),
        # Secuencias de más de 4 componentes
        f"release {_ip(1, 2, 3, 4, 5)}",
        f"release {_ip(9, 1, 2, 3, 4)}",
        # Pegado a letras o guiones bajos
        f"v{_ip(1, 2, 3, 4)}",
        f"lib_{_ip(1, 2, 3, 4)}",
    ],
)
def test_version_like_strings_not_mistaken_for_ip(text):
    v = ps.Vault()
    assert ps.pseudonymize_text(text, v, _rules()) == text


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
        ("llm.tools.cloud.customer1.es", False),
        ("api.openai.com", False),
    ],
)
def test_is_target_host(host, expected):
    assert ps.is_target_host(host) is expected


# --- is_llm_path (#39) -------------------------------------------------------


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/v1/messages", True),
        ("/v1/messages?beta=true", True),
        ("/v1/messages/", True),
        ("/prefix/v1/messages", True),
        ("/v1/complete", True),
        ("/messages", True),
        ("/v1/count_tokens", False),
        ("/v1/models", False),
        ("/health", False),
        ("", False),
    ],
)
def test_is_llm_path(path, expected):
    assert ps.is_llm_path(path) is expected


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


@pytest.mark.parametrize(
    "url",
    [
        "acme-org/repo.with.dots",  # lo que envía Claude Code (sin host)
        "https://github.com/acme-org/repo.with.dots.git",
        "https://user:tok@github.com/acme-org/repo.with.dots",
        "git@github.com:acme-org/repo.with.dots.git",
        "ssh://git@git.example.com:2222/acme-org/repo.with.dots.git",
        "github.com/acme-org/repo.with.dots",
    ],
)
def test_parse_remote_tokens_keeps_dotted_repo_names(url):
    """Un repo con forma de dominio no se descarta por llevar puntos (#65)."""
    assert ps._parse_remote_tokens(url) == ["acme-org", "repo.with.dots"]


def test_parse_remote_tokens_gitlab_subgroups():
    url = "https://gitlab.example.com/acme-org/team-a/service-x.git"
    assert ps._parse_remote_tokens(url) == ["acme-org", "team-a", "service-x"]


def test_parse_remote_tokens_never_returns_host_or_port():
    for url in (
        "https://git.example.com/acme-org/acme-repo",
        "ssh://git@git.example.com:2222/acme-org/acme-repo.git",
        "git@git.example.com:acme-org/acme-repo.git",
    ):
        toks = ps._parse_remote_tokens(url)
        assert toks == ["acme-org", "acme-repo"], url


def test_dotted_repo_learned_from_request_is_not_leaked(tmp_path, monkeypatch):
    """Extremo a extremo: petición con remote de repo con puntos (#65)."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"salt": "x"}), encoding="utf-8")
    monkeypatch.setattr(ps, "config_path", lambda: cfg)
    rules = ps.Rules()
    addon = _Recorder(rules)
    body = _claude_code_body(
        "acme-org/site.acme.dev", text="despliega site.acme.dev desde site.acme.dev"
    )
    assert addon.learn_repo_tokens(body, rules) == ["acme-org", "site.acme.dev"]
    out = ps.pseudonymize_body(body, addon._get_vault(), rules)
    assert "site.acme.dev" not in out


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


# --- aprendizaje de org/repo desde la petición (#63) ---------------------------


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """config.json temporal: estos tests nunca tocan el del usuario."""
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"salt": "x", "pseudo_word_literals": ["keep-me"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ps, "config_path", lambda: cfg)
    return cfg


def _visibility(remote):
    origin = {"host": "github.com", "remote": remote, "visibility": "private"}
    return {"origin": origin, "push_remote": "origin", "remotes": [dict(origin)]}


def _claude_code_body(remote="acme-org/acme-repo", prior_remote=None, text=""):
    """Petición con la forma que envía Claude Code (capturas reales, anonimizada)."""
    prior = prior_remote or remote
    return json.dumps(
        {
            "model": "claude-x",
            "system": [
                {
                    "type": "text",
                    "text": "memory at /tmp/claude-501--Users-u-dev-"
                    + remote.split("/")[-1]
                    + "-dea5d022-scratchpad/memory/",
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text or "hola"},
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "x",
                            "input": {
                                "host": "h",
                                "remote": "content-org/content-repo",
                            },
                        },
                    ],
                }
            ],
            "safeguards": [
                {
                    "type": "dangerous_tool_use",
                    "classifier_context": {
                        "permission_mode": "auto",
                        "git_state": {
                            "branch": "main",
                            "visibility": _visibility(remote),
                        },
                        "prior_turn_context": [
                            {
                                "context": {
                                    "git_state": {"visibility": _visibility(prior)}
                                }
                            }
                        ],
                    },
                }
            ],
        }
    )


class _Recorder(ps.AnthropicPseudonymizer):
    def __init__(self, rules):
        super().__init__(vault=ps.Vault(), rules=rules)
        self.logs = []

    def _log(self, msg, level=None):
        self.logs.append((level, msg))


def test_remote_tokens_from_payload_reads_safeguards():
    body = _claude_code_body("acme-org/acme-repo", prior_remote="other-org/other-repo")
    assert ps.remote_tokens_from_payload(body) == [
        "acme-org",
        "acme-repo",
        "other-org",
        "other-repo",
    ]


def test_remote_tokens_from_payload_ignores_message_content():
    tokens = ps.remote_tokens_from_payload(_claude_code_body())
    assert "content-org" not in tokens and "content-repo" not in tokens


@pytest.mark.parametrize(
    "raw",
    [
        "no es json",
        "[]",
        json.dumps({"messages": []}),
        json.dumps({"safeguards": "x"}),
        json.dumps({"safeguards": [{"git_state": {"host": "h", "remote": 3}}]}),
        json.dumps({"safeguards": [{"remote": "acme-org/acme-repo"}]}),  # sin host
    ],
)
def test_remote_tokens_from_payload_is_best_effort(raw):
    assert ps.remote_tokens_from_payload(raw) == []


def test_rules_add_word_literals_returns_only_new_longest_first():
    rules = ps.Rules(word_literals=["abc"])
    assert rules.add_word_literals(["abc", "longer-one", "longer-one", "xyz"]) == [
        "longer-one",
        "xyz",
    ]
    assert rules.word_literals == ["longer-one", "abc", "xyz"]


def test_add_word_literals_to_config_is_atomic_and_idempotent(tmp_config):
    added, protected = ps.add_word_literals_to_config(["acme-repo", "keep-me"])
    assert added == ["acme-repo"]
    assert protected == ["keep-me", "acme-repo"]
    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved == {"salt": "x", "pseudo_word_literals": ["keep-me", "acme-repo"]}
    assert stat.S_IMODE(tmp_config.stat().st_mode) == 0o600
    assert [p.name for p in tmp_config.parent.iterdir()] == ["config.json"]
    assert ps.add_word_literals_to_config(["acme-repo"]) == ([], protected)


def test_add_word_literals_to_config_without_config(tmp_path):
    missing = tmp_path / "missing.json"
    assert ps.add_word_literals_to_config(["acme-repo"], missing) == ([], [])
    assert not missing.exists()


def test_unknown_repo_is_learned_before_rewriting(tmp_config):
    """Repo nunca visto: sale sin org/repo en claro en esa MISMA petición."""
    rules = ps.Rules()  # sin word-literals: proxy arrancado fuera de cualquier repo
    addon = _Recorder(rules)
    body = _claude_code_body(text="trabajando en acme-repo de acme-org")

    added = addon.learn_repo_tokens(body, rules)
    out = ps.pseudonymize_body(body, addon._get_vault(), rules)

    assert added == ["acme-org", "acme-repo"]
    assert "acme-repo" not in out and "acme-org" not in out
    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved["pseudo_word_literals"] == ["keep-me", "acme-org", "acme-repo"]
    assert (
        "ok",
        "[anthropic-pseudo] 🛡️ org/repo nuevo protegido: acme-org, acme-repo",
    ) in addon.logs


def test_known_repo_is_not_logged_again(tmp_config):
    rules = ps.Rules()
    addon = _Recorder(rules)
    addon.learn_repo_tokens(_claude_code_body(), rules)
    addon.logs.clear()
    assert addon.learn_repo_tokens(_claude_code_body(), rules) == []
    assert addon.logs == []


def test_generic_repo_names_are_not_learned_and_warn_once(tmp_config):
    rules = ps.Rules()
    addon = _Recorder(rules)
    body = _claude_code_body("acme-org/docs")
    assert addon.learn_repo_tokens(body, rules) == ["acme-org"]
    addon.learn_repo_tokens(body, rules)
    assert "docs" not in rules.word_literals
    warns = [m for lvl, m in addon.logs if lvl == "warn"]
    assert len(warns) == 1 and "docs" in warns[0]


def test_learning_failure_never_breaks_the_request(tmp_config, monkeypatch):
    def boom(_raw):
        raise RuntimeError("forma nueva")

    monkeypatch.setattr(ps, "remote_tokens_from_payload", boom)
    rules = ps.Rules()
    addon = _Recorder(rules)
    assert addon.learn_repo_tokens(_claude_code_body(), rules) == []
    assert addon.logs[-1][0] == "warn"


def test_config_write_failure_still_protects_in_memory(tmp_config, monkeypatch):
    def boom(_tokens, _path=None):
        raise OSError("disco lleno")

    monkeypatch.setattr(ps, "add_word_literals_to_config", boom)
    rules = ps.Rules()
    addon = _Recorder(rules)
    assert addon.learn_repo_tokens(_claude_code_body(), rules) == [
        "acme-org",
        "acme-repo",
    ]
    assert "acme-repo" in rules.word_literals
    assert "solo hasta reiniciar" in addon.logs[-1][1]


# --- restauración de responses SSE con seudónimos partidos (#67) ----------------


def _sse_event(kind, data):
    return f"event: {kind}\ndata: {json.dumps(data)}\n\n"


def _sse_response(blocks):
    """SSE con la forma de /v1/messages: ``blocks`` = [(delta_type, field, chunks)]."""
    out = _sse_event(
        "message_start",
        {"type": "message_start", "message": {"id": "msg_1", "content": []}},
    )
    for index, (delta_type, field, chunks) in enumerate(blocks):
        out += _sse_event(
            "content_block_start",
            {"type": "content_block_start", "index": index, "content_block": {}},
        )
        for chunk in chunks:
            out += _sse_event(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": delta_type, field: chunk},
                },
            )
        out += _sse_event(
            "content_block_stop", {"type": "content_block_stop", "index": index}
        )
    out += _sse_event("message_stop", {"type": "message_stop"})
    return out


def _client_view(raw):
    """Lo que reconstruye el cliente: {(index, field): texto concatenado}."""
    view = {}
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        obj = json.loads(line[6:])
        if obj.get("type") != "content_block_delta":
            continue
        delta = obj["delta"]
        field = ps._SSE_DELTA_FIELDS[delta["type"]]
        view[(obj["index"], field)] = view.get((obj["index"], field), "") + delta[field]
    return view


def _split(text, *cuts):
    pieces, prev = [], 0
    for cut in cuts:
        pieces.append(text[prev:cut])
        prev = cut
    return pieces + [text[prev:]]


@pytest.fixture
def path_vault():
    v = ps.Vault()
    real = "/Users/alice/dev/acme"
    return v, real, v.map_path(real, "proj")


@pytest.mark.parametrize(
    "delta_type,field",
    [
        ("text_delta", "text"),
        ("thinking_delta", "thinking"),
    ],
)
def test_restore_sse_joins_pseudonym_split_across_deltas(path_vault, delta_type, field):
    v, real, pseudo = path_vault
    text = f"La ruta es {pseudo}/src."
    start = text.index(pseudo)
    raw = _sse_response([(delta_type, field, _split(text, start + 3, start + 9))])
    out = ps.restore_body(raw, v)
    assert _client_view(out) == {(0, field): f"La ruta es {real}/src."}
    assert out.count("event: ") == raw.count("event: ")


def test_restore_sse_tool_use_input_split_and_escaped(path_vault):
    v, _real, pseudo = path_vault
    real_quote = 'C:\\Users\\a "b"'
    pseudo_quote = v.map(real_quote, "id")
    args = json.dumps({"command": f"cd {pseudo} && echo {pseudo_quote}"})
    cut = args.index(pseudo) + 4
    raw = _sse_response([("input_json_delta", "partial_json", _split(args, cut))])
    view = _client_view(ps.restore_body(raw, v))
    assert json.loads(view[(0, "partial_json")]) == {
        "command": f"cd {_real} && echo {real_quote}"
    }


def test_restore_sse_keeps_blocks_separate(path_vault):
    v, real, pseudo = path_vault
    raw = _sse_response(
        [
            ("text_delta", "text", ["uno ", pseudo[:5]]),
            ("text_delta", "text", [pseudo[5:], " dos"]),
        ]
    )
    # Un seudónimo no cruza bloques: cada bloque se restaura por separado.
    assert _client_view(ps.restore_body(raw, v)) == {
        (0, "text"): "uno " + pseudo[:5],
        (1, "text"): pseudo[5:] + " dos",
    }


def test_restore_sse_untouched_when_nothing_to_restore(path_vault):
    v, _real, _pseudo = path_vault
    raw = _sse_response([("text_delta", "text", ["hola ", "mundo"])])
    assert ps.restore_body(raw, v) == raw


def test_restore_sse_falls_back_on_unparseable_event(path_vault):
    v, real, pseudo = path_vault
    raw = f"event: x\ndata: {{roto\n\nruta {pseudo}\n\n"
    assert ps.restore_body(raw, v) == f"event: x\ndata: {{roto\n\nruta {real}\n\n"


def test_restore_sse_restores_other_events_as_json(path_vault):
    v, real, pseudo = path_vault
    raw = _sse_event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "type": "tool_use",
                "name": "Bash",
                "input": {"cwd": pseudo},
            },
        },
    )
    out = ps.restore_body(raw, v)
    data = json.loads(out.split("data: ", 1)[1])
    assert data["content_block"]["input"]["cwd"] == real


def test_sse_block_text_finds_split_unreversed_pseudonym(path_vault):
    v, _real, pseudo = path_vault
    raw = _sse_response([("text_delta", "text", [pseudo[:4], pseudo[4:]])])
    assert ps._find_unreversed_pseudonyms(raw, v) == []
    assert ps._find_unreversed_pseudonyms(ps.sse_block_text(raw), v) == [
        pseudo.lstrip("/")
    ]


# --- pseudo_patterns (#42) -------------------------------------------------------


@pytest.fixture
def projects_rules():
    patterns, errors = ps.compile_patterns(
        [ps.projects_root_pattern("/Users/u/proyectos")]
    )
    assert errors == []
    return ps.Rules(
        path_prefixes=[("/Users/u/proyectos/repo-a", "proj"), ("/Users/u", "home")],
        word_literals=["repo-a"],
        patterns=patterns,
    )


@pytest.mark.parametrize(
    "text,hidden",
    [
        ("cd /Users/u/proyectos/otro-cliente/src", "otro-cliente"),
        ("ver /Users/u/proyectos/acme.site.dev/index.html", "acme.site.dev"),
        ('log: /Users/u/proyectos/klaus-pro" (cortado)', "klaus-pro"),
        ("error en /Users/u/proyectos/sin-git:12", "sin-git"),
        ("`/Users/u/proyectos/cliente-x`", "cliente-x"),
    ],
)
def test_projects_root_pattern_hides_dir_names(projects_rules, text, hidden):
    v = ps.Vault()
    out = ps.pseudonymize_text(text, v, projects_rules)
    assert hidden not in out
    assert "/proyectos/dir_" in out
    assert ps.restore_text(out, v) == text
    assert ps.pseudonymize_text(out, v, projects_rules) == out


def test_patterns_run_before_path_prefixes(projects_rules):
    """La ruta del repo activo también se protege por el patrón y se restaura."""
    v = ps.Vault()
    text = "cat /Users/u/proyectos/repo-a/README.md"
    out = ps.pseudonymize_text(text, v, projects_rules)
    assert "repo-a" not in out and "/Users/u" not in out
    assert ps.restore_text(out, v) == text


def test_paths_outside_projects_root_are_untouched_by_pattern(projects_rules):
    out = ps.pseudonymize_text(
        "/Users/u/Documents/notas.md", ps.Vault(), projects_rules
    )
    assert "Documents/notas.md" in out and "dir_" not in out


def test_pattern_without_groups_replaces_whole_match():
    patterns, _ = ps.compile_patterns(
        [{"pattern": r"CLIENTE-\d{4}", "replacement_prefix": "cli"}]
    )
    rules = ps.Rules(patterns=patterns)
    v = ps.Vault()
    out = ps.pseudonymize_text("pedido CLIENTE-0042 y CLIENTE-0042", v, rules)
    assert out.count("cli_") == 2 and "CLIENTE" not in out
    assert len(set(re.findall(r"cli_[0-9a-f]{8}", out))) == 1  # determinista


def test_pattern_on_domains():
    patterns, _ = ps.compile_patterns(
        [{"pattern": r"([a-z0-9-]+)\.interno\.acme\.dev", "replacement_prefix": "host"}]
    )
    out = ps.pseudonymize_text(
        "https://facturas.interno.acme.dev/x", ps.Vault(), ps.Rules(patterns=patterns)
    )
    assert "facturas" not in out and ".interno.acme.dev/x" in out


def test_compile_patterns_skips_invalid_entries():
    patterns, errors = ps.compile_patterns(
        [
            {"pattern": "("},
            {"replacement_prefix": "x"},
            {"pattern": "ok", "replacement_prefix": "Mal_Prefijo"},
            "no-es-un-dict",
            {"pattern": "bien"},
        ]
    )
    assert [p.pattern for p, _ in patterns] == ["bien"]
    assert patterns[0][1] == "pat"
    assert len(errors) == 4


def test_build_rules_reads_pseudo_patterns_from_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".klaus-proxy").mkdir(parents=True)
    (home / ".klaus-proxy" / "config.json").write_text(
        json.dumps(
            {"pseudo_patterns": [ps.projects_root_pattern("/srv/p"), {"pattern": "("}]}
        )
    )
    monkeypatch.setattr(ps.Path, "home", lambda: home)
    monkeypatch.setenv("ANTHROPIC_PSEUDO_USER_DIRS", "0")
    rules = ps.build_rules()
    assert len(rules.patterns) == 1
    assert rules.patterns[0][1] == "dir"


def test_add_pattern_to_config_is_idempotent(tmp_config):
    entry = ps.projects_root_pattern("/Users/u/proyectos")
    assert ps.add_pattern_to_config(entry, tmp_config) == (True, [entry])
    assert ps.add_pattern_to_config(entry, tmp_config) == (False, [entry])
    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved["pseudo_word_literals"] == ["keep-me"]
    assert stat.S_IMODE(tmp_config.stat().st_mode) == 0o600


def _with_user_dirs(rules):
    rules.patterns = list(rules.patterns) + [(ps._USER_DIR_RE, "user")]
    return rules


@pytest.mark.parametrize(
    "text,hidden",
    [
        ("@/Users/otrapersona/proyectos/docs/x.md", "otrapersona"),
        ("ssh: /home/deploy-bob/.ssh/config", "deploy-bob"),
        ('"/Users/ana.lopez/Desktop"', "ana.lopez"),
    ],
)
def test_user_dirs_pattern_hides_any_username(text, hidden):
    rules = _with_user_dirs(ps.Rules())
    v = ps.Vault()
    out = ps.pseudonymize_text(text, v, rules)
    assert hidden not in out and "user_" in out
    assert ps.restore_text(out, v) == text
    assert ps.pseudonymize_text(out, v, rules) == out


def test_user_dirs_pattern_ignores_urls():
    rules = _with_user_dirs(ps.Rules())
    text = "https://example.com/home/feed y https://x.dev/Users/list"
    assert ps.pseudonymize_text(text, ps.Vault(), rules) == text


def test_projects_pattern_still_applies_before_user_dirs(projects_rules):
    rules = _with_user_dirs(projects_rules)
    v = ps.Vault()
    text = "cd /Users/u/proyectos/cliente-x && ls /Users/otro/proyectos/z"
    out = ps.pseudonymize_text(text, v, rules)
    assert "cliente-x" not in out and "otro" not in out
    assert ps.restore_text(out, v) == text


def test_build_rules_includes_user_dirs_last_and_can_disable(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".klaus-proxy").mkdir(parents=True)
    (home / ".klaus-proxy" / "config.json").write_text(
        json.dumps({"pseudo_patterns": [ps.projects_root_pattern("/srv/p")]})
    )
    monkeypatch.setattr(ps.Path, "home", lambda: home)
    rules = ps.build_rules()
    assert [prefix for _p, prefix in rules.patterns] == ["dir", "user"]
    monkeypatch.setenv("ANTHROPIC_PSEUDO_USER_DIRS", "0")
    assert [prefix for _p, prefix in ps.build_rules().patterns] == ["dir"]


# --- #92: valores que los patrones no deben seudonimizar ---------------------


@pytest.mark.parametrize(
    "value,prefix",
    [
        ("…", "user"),
        ("...", "user"),
        ("|", "user"),
        ("u", "user"),
        ("«X»", "user"),
        ("{l}", "user"),
        ("<u>", "user"),
        ("$USER", "user"),
        ("${USER}", "user"),
        ("%USERNAME%", "user"),
        ("Shared", "user"),
        ("root", "user"),
        ("…", "dir"),
    ],
)
def test_ignorable_pattern_values(value, prefix):
    assert ps.is_ignorable_pattern_value(value, prefix)


@pytest.mark.parametrize(
    "value,prefix",
    [
        ("ana.lopez", "user"),
        ("deploy-bob", "user"),
        ("user2", "user"),
        ("jd", "user"),
        ("Shared", "dir"),  # genérico solo como usuario, no como proyecto
        ("cliente-x", "dir"),
    ],
)
def test_real_looking_values_are_not_ignorable(value, prefix):
    assert not ps.is_ignorable_pattern_value(value, prefix)


def test_user_dirs_pattern_leaves_placeholders_and_vault_clean():
    rules = _with_user_dirs(ps.Rules())
    v = ps.Vault()
    text = "Rutas: /Users/…/x, /Users/|/y, /home/u/z, /Users/Shared/t y /Users/{l}/w"
    assert ps.pseudonymize_text(text, v, rules) == text
    assert v.to_dict() == {}


def test_pattern_ignore_list_from_config(tmp_path, monkeypatch):
    # No usar el usuario de la máquina (en GitHub Actions es "runner"):
    # build_rules() protege siempre el home real como prefijo de ruta.
    home = tmp_path / "home"
    (home / ".klaus-proxy").mkdir(parents=True)
    (home / ".klaus-proxy" / "config.json").write_text(
        json.dumps({"pseudo_pattern_ignore": ["ejemplo-ci", 7]})
    )
    monkeypatch.setattr(ps.Path, "home", lambda: home)
    rules = ps.build_rules()
    assert rules.pattern_ignore == frozenset({"ejemplo-ci"})
    v = ps.Vault()
    out = ps.pseudonymize_text("/home/ejemplo-ci/work y /home/ana.lopez/x", v, rules)
    assert "/home/ejemplo-ci/work" in out and "ana.lopez" not in out
    assert "ejemplo-ci" not in v.to_dict()


def test_prune_vault_removes_only_ignorable_pattern_entries():
    rules = _with_user_dirs(ps.Rules(pattern_ignore=["run" + "ner"]))
    v = ps.Vault.from_dict(
        {
            "\u2026": "user_00000001",
            "|": "user_00000002",
            "run" + "ner": "user_00000003",
            "ana.lopez": "user_00000004",
            "x": "org_00000005",  # no viene de un patrón activo: se queda
        }
    )
    removed = ps.prune_vault(v, rules)
    assert sorted(removed) == sorted(["\u2026", "|", "run" + "ner"])
    assert set(v.to_dict()) == {"ana.lopez", "x"}
    assert "user_00000001" not in v.pseudo_to_real
