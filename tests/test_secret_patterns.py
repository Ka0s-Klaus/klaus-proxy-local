"""Credenciales que el proxy redacta y endpoints de autenticación (#148).

Los valores se construyen en tiempo de ejecución: no son claves reales y así
no los marca el escáner de secretos del repositorio.
"""

import pytest

import anthropic_payload_pseudonymize as ps
from Klaus_proxy_local.sensitive_data_scanner import SensitiveDataScanner

# La configuración por defecto: el matcher genérico clave=valor, apagado
R = ps.Rules(secret_regexes=list(ps._SECRET_RES), secret_kv=False)
TAIL = "Ab3" + "x9" * 12  # 27 caracteres alfanuméricos con dígitos
PW = "Contr4" + "sen" + "ya9"

SAMPLES = {
    "anthropic-api-key": "sk-" + "ant-api03-" + TAIL,
    "openai-api-key": "sk-" + "proj-" + TAIL,
    "stripe-api-key": "sk" + "_live_" + TAIL,
}


def _redact(text):
    return ps.redact_secrets(text, R)


@pytest.mark.parametrize("label,value", list(SAMPLES.items()))
def test_api_keys_redacted_with_their_label(label, value):
    out = _redact(f"clave = {value} fin")
    assert value not in out
    assert f"«REDACTED:{label}»" in out


@pytest.mark.parametrize(
    "url,kept",
    [
        (f"postgres://app:{PW}@db.cliente.example:5432/ventas", "postgres://app:"),
        (f"mongodb+srv://svc:{PW}@cluster0.cliente.example/db", "mongodb+srv://svc:"),
        (f"https://deploy:{PW}@git.cliente.example/repo.git", "https://deploy:"),
    ],
)
def test_url_password_only(url, kept):
    out = _redact(f'DATABASE_URL="{url}"')
    assert PW not in out
    assert kept + "«REDACTED:url-password»@" in out
    assert url.split("@", 1)[1] in out  # host y base de datos intactos


def test_aws_secret_key_and_bearer_keep_context():
    secret = "wJalr" + "XUtnF" * 7
    out = _redact(f"aws_secret_access_key = {secret}")
    assert secret not in out
    assert out.startswith("aws_secret_access_key = «REDACTED:aws-secret-key»")
    token = "eyZ" + TAIL
    out = _redact(f"curl -H 'Authorization: Bearer {token}'")
    assert token not in out and "Bearer «REDACTED:bearer-token»" in out


@pytest.mark.parametrize(
    "text",
    [
        "task-runner-for-the-nightly-build",
        "usa sk-some-long-identifier-name aquí",
        "git@github.com:org/repo.git",
        "https://docs.example.com/guia?x=1",
        "ssh://git@host.example:22/repo",
        "bearer corto",
        "pk_live_",
        "# esquema://[user[:pass]@]host[:port]/org/repo",
        "postgres://${DB_USER}:${DB_PASS}@${DB_HOST}/app",
    ],
)
def test_no_false_positives(text):
    assert _redact(text) == text


@pytest.mark.parametrize("key", ["refresh_token", "AWS_SESSION_TOKEN"])
def test_tokens_redacted_without_generic_kv(key):
    value = "1//" + TAIL + "-Zq"
    out = _redact(f'{key} = "{value}"')
    assert value not in out and f'{key} = "«REDACTED:token»"' == out


def test_token_name_in_code_untouched():
    code = "refresh_token = get_refresh_token_from_store()"
    assert _redact(code) == code


def test_redaction_is_idempotent():
    once = _redact(f"x {SAMPLES['anthropic-api-key']} postgres://a:{PW}@h/db")
    assert _redact(once) == once


@pytest.mark.parametrize(
    "path,auth",
    [
        ("/v1/oauth/token", True),
        ("/oauth/authorize?x=1", True),
        ("/api/oauth/token", True),
        ("/api/oauth/claude_cli/create_api_key", True),
        ("/api/auth/login", True),
        ("/api/oauth/organizations/x/skills/list-skills", False),
        ("/api/oauth/profile", False),
        ("/v1/messages", False),
        ("/api/event_logging/v2/batch", False),
    ],
)
def test_auth_paths(path, auth):
    assert ps.is_auth_path(path) is auth


def test_scanner_credentials_are_redacted_by_proxy(tmp_path):
    """Lo que klaus-scan marca como credencial, el proxy lo redacta (#148)."""
    lines = [
        *SAMPLES.values(),
        f"postgres://app:{PW}@db.cliente.example/ventas",
        f"mongodb://svc:{PW}@mongo.cliente.example/db",
        "aws_secret_access_key = " + "wJalr" + "XUtnF" * 7,
        "Authorization: Bearer " + "eyZ" + TAIL,
        "refresh_token = " + "1//" + TAIL,
        "aws_session_token = " + "FwoG" + TAIL * 4,
    ]
    f = tmp_path / "creds.txt"
    f.write_text("\n".join(lines) + "\n")
    findings = SensitiveDataScanner().scan_file(f)
    assert findings
    for finding in findings:
        if finding.category in ("aws-arn", "ipv4", "internal-hostname"):
            continue  # no son credenciales
        assert _redact(finding.value) != finding.value, finding.category


# --- klaus-scan: conexiones con contraseña de marcador (#152) ----------------------


@pytest.mark.parametrize(
    "line",
    [
        "postgres://user:${DB_PASS}@db.cliente.example:5432/app",
        "postgres://${DB_USER}:${DB_PASS}@${DB_HOST}/app",
        "mongodb+srv://app:{pw}@cluster0.cliente.example/db",
        "postgres://app:«REDACTED:url-password»@db/ventas",
        "mysql://root:password@localhost/app",
        "postgresql://app:changeme@db/app",
        "postgres://app:xxxx@db/app",
        "postgres://app:<password>@db/app",
        "mongodb://app@mongo.cliente.example/db",
    ],
)
def test_scanner_ignores_placeholder_connections(tmp_path, line):
    f = tmp_path / "conf.txt"
    f.write_text(line + "\n")
    cats = {"db-connection", "mongodb-connection", "url-with-credentials"}
    found = [x for x in SensitiveDataScanner().scan_file(f) if x.category in cats]
    assert found == []


def test_scanner_keeps_real_connection_password(tmp_path):
    f = tmp_path / "conf.txt"
    f.write_text(f"postgres://app:{PW}@db.cliente.example/ventas\n")
    found = [
        x for x in SensitiveDataScanner().scan_file(f) if x.category == "db-connection"
    ]
    assert len(found) == 1
