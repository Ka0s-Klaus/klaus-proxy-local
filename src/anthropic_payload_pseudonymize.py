#!/usr/bin/env python3
"""Seudonimizador bidireccional de payloads Anthropic para el proxy de auditoría.

Reescribe EN VUELO el cuerpo de las peticiones (``/v1/messages``) sustituyendo
datos sensibles —identidad, usuario del SO, rutas de ficheros, emails, IPs— por
seudónimos estables, y REVIERTE esos seudónimos en la respuesta para que las
tool calls (Read/Edit/Bash) sigan operando sobre valores REALES en la máquina.

    real  --[forward]-->  seudónimo   → gateway / Anthropic     (request)
    seudónimo  --[restore]-->  real   → CLI                     (response)

Diseño:
  - ``Vault``: mapa bidireccional consistente real<->seudónimo, persistible.
  - Reglas: prefijos de ruta (palanca de rutas), literales (identidad/usuario),
    regex (email / IPv4). Se aplican longest-match-first para evitar solapes.
  - ``pseudonymize_text`` (request): aplica reglas y da de alta valores nuevos.
  - ``restore_text``     (response): aplica el inverso del vault; NUNCA da altas.

El seudónimo se deriva de un hash con sal, por lo que es estable y no revela el
valor original, pero SOLO es reversible con el vault. **El vault contiene los
valores reales**: es el fichero más sensible de la auditoría — vive en el
directorio gitignored ``captures/`` y jamás debe versionarse.

mitmproxy se importa de forma perezosa: el módulo es unit-testable sin el proxy.

Uso (el seudonimizador debe ir ANTES de la captura para que la evidencia refleje
lo que REALMENTE sale del equipo):

    mitmdump -s src/anthropic_payload_pseudonymize.py \\
             -s src/anthropic_payload_capture.py --listen-host 127.0.0.1 -p 8899
"""
from __future__ import annotations

import functools
import getpass
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

# TOOL_ROOT no se usa más; rutas de usuario se encuentran bajo ~/.klaus-proxy/


# --- Coloreado de logs --------------------------------------------------------
# Coloreamos cada línea de log por semántica: verde = acción de auditoría OK
# (se seudonimizó/revirtió algo), amarillo = aviso a revisar, rojo = error. Se
# DESACTIVA si NO_COLOR está presente (convención https://no-color.org) o si la
# salida NO es una terminal (p.ej. `claude-proxy | tee audit.log`), para no
# ensuciar la evidencia con secuencias ANSI. Forzable con ANTHROPIC_LOG_COLOR=1
# (siempre) o =0 (nunca).
_ANSI = {"ok": "\033[32m", "warn": "\033[33m", "error": "\033[31m"}
_ANSI_RESET = "\033[0m"


def color_enabled(stream: Any = None) -> bool:
    """¿Debe colorearse la salida? TTY y sin NO_COLOR; override ANTHROPIC_LOG_COLOR."""
    forced = os.environ.get("ANTHROPIC_LOG_COLOR")
    if forced in ("1", "true", "yes"):
        return True
    if forced in ("0", "false", "no"):
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    stream = stream if stream is not None else sys.stdout
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def colorize(text: str, level: str, *, enabled: bool | None = None) -> str:
    """Envuelve ``text`` en el ANSI de ``level`` (``ok``/``warn``/``error``).

    ``enabled=None`` consulta ``color_enabled()``. Nivel desconocido o coloreado
    desactivado → texto intacto (neutro). Pura → unit-testable sin terminal.
    """
    if enabled is None:
        enabled = color_enabled()
    code = _ANSI.get(level)
    if not enabled or code is None:
        return text
    return f"{code}{text}{_ANSI_RESET}"


def project_root() -> Path:
    """Raíz del proyecto AUDITADO (no la del tooling).

    Es la raíz de la palanca de rutas y el cwd para detectar identidad/remote
    git. Por defecto el directorio de trabajo del proceso mitmdump, que hereda
    el de quien lanzó `claude-proxy` (no hace `cd`); override explícito con
    ANTHROPIC_PSEUDO_PROJECT_ROOT. Para que org/repo no dependan de ese
    directorio, `claude-proxy` los guarda en ``pseudo_word_literals`` de
    config.json (#61).
    """
    override = os.environ.get("ANTHROPIC_PSEUDO_PROJECT_ROOT")
    return Path(override) if override else Path.cwd()


# Hosts sobre los que se reescribe — solo el fallback final si ni env var ni config.json.
_DEFAULT_HOSTS = ("api.anthropic.com",)

# Regex de datos sensibles con forma reconocible.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# IPv4 con 4 octetos delimitados por punto (evita versiones tipo 4.8.0).
# Cada octeto debe estar en 0–255 y la secuencia no puede formar parte de una
# más larga (2.1.312.625, 1.2.3.4.5). Tampoco cuenta como IP lo que va tras
# ``version=``/``version:`` (``cc_version=`` en la cabecera de facturación de
# Claude Code), aunque sus octetos sean válidos (#57).
_IPV4_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_IPV4_RE = re.compile(
    r"(?<![\w.])(?<![Vv]ersion=)(?<![Vv]ersion:)"
    rf"{_IPV4_OCTET}(?:\.{_IPV4_OCTET}){{3}}"
    r"(?![\w]|\.\d)"
)

# --- Secretos (Tier 1): redacción IRREVERSIBLE ------------------------------
# El cuerpo del payload NO se redacta como las cabeceras. Si un fichero leído
# (Read) o la salida de un Bash contiene un secreto, viajaría en claro. Estos
# patrones lo sustituyen por un placeholder fijo `«REDACTED:label»` que NO entra
# al vault: no se revierte (el modelo casi nunca necesita el valor real de un
# secreto, y así el vault no acumula credenciales).
_PLACEHOLDER = "«REDACTED:{label}»"

# Cada entrada: (regex, label). Los que capturan grupo 2 redactan SOLO el valor,
# conservando la clave (`password=…`) como contexto legible para el modelo.
_SECRET_RES: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
            r"[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
        ),
        "private-key",
    ),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-access-key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "github-token"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "google-api-key"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"), "slack-token"),
    (
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "jwt",
    ),
]

# key=value / key: value con nombre sensible. Grupo 1 = clave+separador(+comilla),
# grupo 2 = valor a redactar. El valor excluye backslash y '(' de su cuerpo, y un
# lookahead exige que termine en un delimitador real (comilla/espacio/coma/cierre/
# fin) — así una llamada tipo `os.getenv("X")` NO se confunde con una credencial
# (el valor iría seguido de '(', que no es delimitador válido).
_SECRET_KV_RE = re.compile(
    r"((?:secret|token|password|passwd|api[_-]?key|apikey|client[_-]?secret|"
    r"access[_-]?token|auth[_-]?token)\s*[:=]\s*[\"']?)"
    r"([^\s\"',\\(]{4,})(?=[\s\"',;)\]}]|$)",
    re.IGNORECASE,
)


# --- Configuración por entorno ----------------------------------------------


def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val not in ("0", "false", "False", "no", "")


def enabled() -> bool:
    """Interruptor general del seudonimizador."""
    return _env_flag("ANTHROPIC_PSEUDO_ENABLE", True)


def paths_enabled() -> bool:
    """Palanca específica de seudonimización de rutas de ficheros."""
    return _env_flag("ANTHROPIC_PSEUDO_PATHS", True)


def user_dirs_enabled() -> bool:
    """Palanca del patrón integrado de usuarios en rutas ``/Users|/home/<u>`` (#42)."""
    return _env_flag("ANTHROPIC_PSEUDO_USER_DIRS", True)


def dir_words_enabled() -> bool:
    """Palanca: nombres de carpeta del vault también fuera de una ruta (#93)."""
    return _env_flag("ANTHROPIC_PSEUDO_DIR_WORDS", True)


def regexes_enabled() -> bool:
    """Palanca de detección por regex (email / IPv4)."""
    return _env_flag("ANTHROPIC_PSEUDO_REGEX", True)


def secrets_enabled() -> bool:
    """Palanca de detectores de secretos de alta precisión (PEM/AWS/GitHub/...)."""
    return _env_flag("ANTHROPIC_PSEUDO_SECRETS", True)


def secret_kv_enabled() -> bool:
    """Palanca del matcher genérico ``clave=valor`` (Tier 1).

    Por defecto OFF: sobre código real (``password = get_password()``,
    ``token: fetchToken()``) mis-dispara con frecuencia. Actívalo solo cuando
    audites un fichero de credenciales concreto (``.env``, YAML de secretos).
    """
    return _env_flag("ANTHROPIC_PSEUDO_SECRET_KV", False)


def _configured_hosts() -> tuple[str, ...]:
    # Priority 1: explicit env var
    override = os.environ.get("ANTHROPIC_PSEUDO_HOSTS") or os.environ.get(
        "ANTHROPIC_CAPTURE_HOSTS"
    )
    if override:
        return tuple(h.strip().lower() for h in override.split(",") if h.strip())
    # Priority 2: ~/.klaus-proxy/config.json — single source of truth for hosts
    try:
        import json as _json

        _cfg_path = Path.home() / ".klaus-proxy" / "config.json"
        if _cfg_path.exists():
            _cfg = _json.loads(_cfg_path.read_text(encoding="utf-8"))
            hosts = [h.strip().lower() for h in _cfg.get("hosts", []) if h.strip()]
            if hosts:
                return tuple(hosts)
    except Exception:
        pass
    # Priority 3: hardcoded fallback (only Anthropic — user-specific gateways go in config.json)
    return _DEFAULT_HOSTS


def is_target_host(host: str) -> bool:
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in _configured_hosts())


_LLM_PATH_PATTERNS = (
    "/v1/messages",
    "/v1/complete",
    "/messages",
)


def is_llm_path(path: str) -> bool:
    """True si la ruta parece una llamada a un LLM (defense-in-depth para hosts desconocidos)."""
    p = (path or "").lower().split("?")[0].rstrip("/")
    return any(p == pat or p.endswith(pat) for pat in _LLM_PATH_PATTERNS)


def _salt() -> str:
    """Load pseudonymization salt; must be explicitly configured.

    Raises RuntimeError if ANTHROPIC_PSEUDO_SALT is not set. The default
    salt was removed (it was public in the repo). In v0.1.0, auto-generation
    will handle this transparently.
    """
    salt = os.environ.get("ANTHROPIC_PSEUDO_SALT")
    if not salt:
        raise RuntimeError(
            "⚠️  ANTHROPIC_PSEUDO_SALT environment variable is required.\n"
            "\n"
            "Generate a random salt:\n"
            "  python -c 'import secrets; print(secrets.token_hex(16))'\n"
            "\n"
            "Then set it in your shell:\n"
            "  export ANTHROPIC_PSEUDO_SALT=<your-32-char-hex-salt>\n"
            "\n"
            "(v0.1.0 will auto-generate this on first run)"
        )
    return salt


def vault_path() -> Path:
    override = os.environ.get("ANTHROPIC_PSEUDO_VAULT")
    if override:
        return Path(override)
    return Path.home() / ".klaus-proxy" / "captures" / ".pseudonym_vault.json"


# --- Generación de seudónimos ------------------------------------------------


def _hash(value: str) -> str:
    return hashlib.sha1((_salt() + "::" + value).encode("utf-8")).hexdigest()[:8]


# --- Vault bidireccional -----------------------------------------------------


class Vault:
    """Mapa consistente y reversible real<->seudónimo.

    - ``map(real, prefix)``      → seudónimo tipo ``prefix_<hash>`` (identidades).
    - ``map_path(real, label)``  → seudónimo tipo ``/label_<hash>`` (rutas).
    Ambos son idempotentes: el mismo valor real siempre devuelve el mismo
    seudónimo, y se garantiza que dos valores distintos no colisionan.
    """

    def __init__(self) -> None:
        self.real_to_pseudo: dict[str, str] = {}
        self.pseudo_to_real: dict[str, str] = {}

    def _register(self, real: str, pseudo: str) -> str:
        # Resolución de colisión: si el seudónimo ya apunta a otro real, alarga.
        while pseudo in self.pseudo_to_real and self.pseudo_to_real[pseudo] != real:
            pseudo += "z"
        self.real_to_pseudo[real] = pseudo
        self.pseudo_to_real[pseudo] = real
        return pseudo

    def map(self, real: str, prefix: str = "id") -> str:
        if real in self.real_to_pseudo:
            return self.real_to_pseudo[real]
        return self._register(real, f"{prefix}_{_hash(real)}")

    def map_path(self, real: str, label: str = "path") -> str:
        if real in self.real_to_pseudo:
            return self.real_to_pseudo[real]
        # Seudónimo con forma de raíz absoluta para que el modelo lo trate como
        # ruta y conserve la estructura relativa que cuelga de él.
        return self._register(real, f"/{label}_{_hash(real)}")

    def dir_words(self, ignore: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
        """Nombres de carpeta (``dir_…``) que se sustituyen también sueltos (#93).

        Longest-first, como los word-literals.
        """
        return sorted(
            (
                (real, pseudo)
                for real, pseudo in self.real_to_pseudo.items()
                if pseudo.startswith("dir_") and is_dir_word(real, ignore)
            ),
            key=lambda t: len(t[0]),
            reverse=True,
        )

    # -- persistencia --
    def to_dict(self) -> dict[str, str]:
        return dict(self.real_to_pseudo)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Vault":
        v = cls()
        for real, pseudo in data.items():
            v.real_to_pseudo[real] = pseudo
            v.pseudo_to_real[pseudo] = real
        return v

    def save(self, path: Path | None = None) -> Path:
        """Save vault with secure permissions (0o600 = owner read/write only).

        Parent directory is created with 0o700 (owner read/write/execute only).
        This prevents other users on shared systems from accessing the vault.
        """
        path = path or vault_path()
        # Create parent with restrictive permissions
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Ensure vault is readable only by owner
        os.chmod(path, 0o600)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "Vault":
        path = path or vault_path()
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return cls()


# --- Reglas ------------------------------------------------------------------


class Rules:
    """Conjunto de reglas de seudonimización, ordenadas para aplicar sin solapes.

    - ``path_prefixes``: lista de (prefijo_real, etiqueta), longest-first.
    - ``literals``: lista de literales exactos (substring), longest-first.
    - ``word_literals``: literales que SOLO casan con frontera de palabra
      (evita corromper substrings: ``orgcode2`` no debe tocar ``HTTPS``). Reversibles.
    - ``regexes``: lista de (regex, prefijo) para altas dinámicas (reversibles).
    - ``secret_regexes``: (regex, label) de secretos → redacción IRREVERSIBLE.
    - ``patterns``: ``pseudo_patterns`` de config, (regex, prefijo). Si el
      regex tiene grupos solo se seudonimiza el grupo 1 (#42). Reversibles.
    - ``pattern_ignore``: valores que los patrones no seudonimizan
      (``pseudo_pattern_ignore`` de config, #92).
    - ``dir_words``: los nombres de carpeta del vault (``dir_…``) se
      sustituyen también fuera de una ruta, como palabra completa (#93).
    """

    def __init__(
        self,
        path_prefixes: list[tuple[str, str]] | None = None,
        literals: list[str] | None = None,
        regexes: list[tuple[re.Pattern, str]] | None = None,
        word_literals: list[str] | None = None,
        secret_regexes: list[tuple[re.Pattern, str]] | None = None,
        secret_kv: bool = False,
        patterns: list[tuple[re.Pattern, str]] | None = None,
        pattern_ignore: Iterable[str] | None = None,
        dir_words: bool = False,
    ) -> None:
        # Longest-first: una raíz de repo (más larga) se sustituye antes que el
        # home que la contiene; una identidad git antes que el usuario suelto.
        self.path_prefixes = sorted(
            [(p, label) for p, label in (path_prefixes or []) if p],
            key=lambda t: len(t[0]),
            reverse=True,
        )
        self.literals = sorted(
            [lit for lit in (literals or []) if lit], key=len, reverse=True
        )
        self.word_literals = sorted(
            [w for w in (word_literals or []) if w], key=len, reverse=True
        )
        self.regexes = regexes or []
        self.secret_regexes = secret_regexes or []
        # Si se aplica también la regla key=value (captura de secretos por nombre).
        self.secret_kv = secret_kv
        self.patterns = patterns or []
        self.pattern_ignore = frozenset(pattern_ignore or ())
        self.dir_words = dir_words

    def add_word_literals(self, tokens: list[str]) -> list[str]:
        """Añade word-literals en caliente (longest-first); devuelve los nuevos."""
        added = [t for t in dict.fromkeys(tokens) if t and t not in self.word_literals]
        if added:
            self.word_literals = sorted(
                self.word_literals + added, key=len, reverse=True
            )
        return added


def _detect_git_identity() -> list[str]:
    """Lee la identidad git local (user.name / user.email) si está disponible."""
    values: list[str] = []
    try:
        import subprocess

        for key in ("user.name", "user.email"):
            out = subprocess.run(
                ["git", "config", "--get", key],
                cwd=str(project_root()),
                capture_output=True,
                text=True,
                timeout=3,
            )
            val = (out.stdout or "").strip()
            if val:
                values.append(val)
    except Exception:
        # Detección best-effort: si el parseo del remote falla, seguimos sin
        # esos literales — nunca debe romper la seudonimización.
        pass
    return values


_GENERIC_REMOTE_TOKENS = {"github", "gitlab", "bitbucket", "com", "org", "net", "git"}


def _parse_remote_tokens(url: str) -> list[str]:
    """Extrae org y nombre de repo de una URL de remote como word-literals.

    p.ej. ``dev2@example.com:example-org/customer1-ecosistema1.git`` →
    ``["example-org", "customer1-ecosistema1"]``. El host se quita por
    posición (tras el esquema, antes de ``:`` en la forma scp), no por llevar
    punto: un repo puede llamarse como un dominio (``user.github.io``) y
    antes se descartaba en silencio (#65). Acepta también ``org/repo`` sin
    host, que es lo que envía Claude Code. Se descartan tokens de menos de 3
    chars y los genéricos de plataforma (github/gitlab/...). Función pura →
    unit-testable sin git.
    """
    tokens: list[str] = []
    if not url:
        return tokens
    rest = url.strip()
    scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", rest)
    if scheme:
        # esquema://[user[:pass]@]host[:port]/org/repo
        path = rest[scheme.end() :].partition("/")[2]
    elif re.match(r"^[^/:]+:(?!//)", rest):
        # scp-like: [user@]host:org/repo
        path = rest.partition(":")[2]
    else:
        # org/repo sin host; si parece host/org/repo, el host se quita.
        path = rest
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and "." in parts[0]:
            path = "/".join(parts[1:])
    path = re.sub(r"\.git/?$", "", path.strip().strip("/"))
    for tok in path.split("/"):
        tok = tok.strip()
        if (
            len(tok) >= 3
            and tok.lower() not in _GENERIC_REMOTE_TOKENS
            and tok not in tokens
        ):
            tokens.append(tok)
    return tokens


def _detect_git_remote_tokens() -> list[str]:
    """Lee la URL del remote origin y devuelve sus tokens de org/repo."""
    try:
        import subprocess

        out = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(project_root()),
            capture_output=True,
            text=True,
            timeout=3,
        )
        return _parse_remote_tokens((out.stdout or "").strip())
    except Exception:
        return []


# Nombres de repo/org demasiado comunes para usarlos como word-literal: se
# seudonimizaría esa palabra en todo el texto (#63). Solo se aplica a lo que se
# aprende de las peticiones; lo configurado a mano se respeta.
_GENERIC_REPO_TOKENS = frozenset(
    {
        "api",
        "app",
        "apps",
        "backend",
        "blog",
        "client",
        "config",
        "core",
        "data",
        "demo",
        "docs",
        "dotfiles",
        "example",
        "examples",
        "frontend",
        "infra",
        "lib",
        "main",
        "notes",
        "scripts",
        "server",
        "site",
        "src",
        "test",
        "tests",
        "tools",
        "utils",
        "web",
        "website",
    }
)


def is_generic_repo_token(token: str) -> bool:
    return token.lower() in _GENERIC_REPO_TOKENS


def _iter_remotes(obj: Any):
    """Valores ``remote`` de los dicts ``{host, remote}`` anidados en ``obj``."""
    if isinstance(obj, dict):
        remote = obj.get("remote")
        if isinstance(remote, str) and isinstance(obj.get("host"), str):
            yield remote
        for v in obj.values():
            yield from _iter_remotes(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_remotes(v)


def remote_tokens_from_payload(raw: str) -> list[str]:
    """org/repo de los remotes git que Claude Code envía en la propia petición.

    Claude Code incluye ``{host, remote: "org/repo"}`` en
    ``safeguards[].classifier_context.git_state.visibility`` (y en el
    ``prior_turn_context``). Es un campo interno, así que es best-effort: sin
    JSON, sin ``safeguards`` o con otra forma devuelve ``[]``. Solo se mira
    ``safeguards``: lo que va en los mensajes es contenido, no estructura.
    """
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(payload, dict):
        return []
    tokens: list[str] = []
    for remote in _iter_remotes(payload.get("safeguards")):
        for tok in _parse_remote_tokens(remote):
            if tok not in tokens:
                tokens.append(tok)
    return tokens


def config_path() -> Path:
    return Path.home() / ".klaus-proxy" / "config.json"


def add_word_literals_to_config(
    tokens: list[str], path: Path | None = None
) -> tuple[list[str], list[str]]:
    """Añade ``tokens`` a ``pseudo_word_literals`` de config.json.

    Escritura atómica (tmp + rename, 0600): la usan a la vez ``mitmdump`` al
    aprender tokens y ``claude-proxy`` al arrancar (#63). Devuelve
    ``(añadidos, lista_completa)``. Sin config legible no cambia nada.
    """
    return _add_to_config_list("pseudo_word_literals", tokens, path)


# Un valor de un solo token (``acme-corp``, ``proyecto.x``) se protege con
# frontera de palabra; con espacios o barras, como literal substring.
_WORD_TOKEN_RE = re.compile(r"[\w.@-]+")


def add_protected_values_to_config(
    values: list[str], path: Path | None = None
) -> list[str]:
    """Añade ``values`` a las reglas de config.json para que se seudonimicen (#99).

    El vault solo guarda el seudónimo de un valor que ya casa con una regla:
    un valor que solo está en el vault sale en claro. Los tokens van a
    ``pseudo_word_literals``; el resto, a ``pseudo_literals``. Devuelve los
    añadidos. El proxy los aplica al reiniciarse.
    """
    values = [v.strip() for v in values if v and v.strip()]
    words = [v for v in values if _WORD_TOKEN_RE.fullmatch(v)]
    literals = [v for v in values if v not in words]
    added_words, _ = _add_to_config_list("pseudo_word_literals", words, path)
    added_literals, _ = _add_to_config_list("pseudo_literals", literals, path)
    return added_words + added_literals


def add_pattern_to_config(
    entry: dict[str, str], path: Path | None = None
) -> tuple[bool, list[dict[str, str]]]:
    """Añade un ``pseudo_patterns`` a config.json si no estaba (#42).

    Devuelve ``(añadido, lista_completa)``.
    """
    added, patterns = _add_to_config_list("pseudo_patterns", [entry], path)
    return bool(added), patterns


def _add_to_config_list(key: str, values: list, path: Path | None) -> tuple[list, list]:
    """Añade ``values`` (sin duplicar) a la lista ``key`` de config.json.

    Escritura atómica (tmp + rename, 0600). Sin config legible no cambia nada.
    """
    path = path or config_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return [], []
    current = list(config.get(key) or [])
    added = []
    for value in values:
        if value and value not in current and value not in added:
            added.append(value)
    if added:
        current.extend(added)
        config[key] = current
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), "utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    return added, current


# Nombre de usuario en cualquier ruta ``/Users/<u>`` o ``/home/<u>``, sea o no el
# home de esta máquina: un CLAUDE.md o un log pueden citar rutas de otro equipo
# o de otro usuario (#42). No casa dentro de URLs (``x.com/home/feed``).
_USER_DIR_RE = re.compile(r"(?<![\w./-])(?:/Users|/home)/([^/\s\"'`\\:;,()\[\]<>]+)")

# Seudónimo ya acuñado (``dir_1a2b3c4d``): no se vuelve a seudonimizar.
_PSEUDONYM_RE = re.compile(r"^[A-Za-z]+_[0-9a-f]{8}z*$")

# Valores que un patrón captura pero no pueden ser un dato (#92): marcadores
# con los que se tapa o se generaliza un nombre (``{user}``, ``«X»``, ``$USER``,
# ``%USERNAME%``) y nombres genéricos bajo /Users o /home.
_PLACEHOLDER_VALUE_RE = re.compile(r"[{<«\[(].*[}>»\])]|\$\{?\w+\}?|%\w+%")
_GENERIC_USER_DIRS = frozenset(
    {"shared", "guest", "root", "user", "username", "usuario", "nobody"}
)


# Nombres de carpeta que, fuera de una ruta, son palabras corrientes (#93).
DIR_WORD_MIN_LEN = 5
_GENERIC_DIR_WORDS = frozenset(
    {
        "assets",
        "backup",
        "backups",
        "build",
        "config",
        "configs",
        "examples",
        "github",
        "images",
        "projects",
        "proyectos",
        "public",
        "scripts",
        "shared",
        "static",
        "tests",
        "tools",
        "utils",
        "vendor",
        "workspace",
    }
)


def is_dir_word(value: str, ignore: frozenset[str] = frozenset()) -> bool:
    """True si un nombre de carpeta del vault se sustituye también suelto (#93).

    Con ``DIR_WORD_MIN_LEN`` caracteres o más, que no sea un nombre genérico
    (``scripts``, ``tests``…) ni un valor que los patrones ignoran (#92).
    """
    return (
        len(value) >= DIR_WORD_MIN_LEN
        and value.lower() not in _GENERIC_DIR_WORDS
        and not is_ignorable_pattern_value(value, "dir", ignore)
    )


def is_ignorable_pattern_value(
    value: str, prefix: str, ignore: frozenset[str] = frozenset()
) -> bool:
    """True si ``value``, capturado por un patrón, no debe seudonimizarse (#92).

    Sin ningún carácter alfanumérico (``…``, ``|``), de un solo carácter, un
    marcador de plantilla, un nombre genérico de usuario o uno de
    ``pseudo_pattern_ignore``. Así no entra al vault algo que no es un dato.
    """
    if value in ignore:
        return True
    if len(value) < 2 or not any(c.isalnum() for c in value):
        return True
    if _PLACEHOLDER_VALUE_RE.fullmatch(value):
        return True
    return prefix == "user" and value.lower() in _GENERIC_USER_DIRS


def compile_patterns(entries: Any) -> tuple[list[tuple[re.Pattern, str]], list[str]]:
    """Compila ``pseudo_patterns`` de config.json (#42).

    Cada entrada es ``{"pattern": <regex>, "replacement_prefix": <prefijo>}``.
    Devuelve ``(patrones, errores)``: una entrada inválida se descarta y se
    describe en ``errores``, nunca rompe la seudonimización.
    """
    patterns: list[tuple[re.Pattern, str]] = []
    errors: list[str] = []
    for entry in entries or []:
        try:
            pattern = entry["pattern"]
            prefix = entry.get("replacement_prefix") or "pat"
            if not isinstance(pattern, str) or not re.fullmatch(r"[a-z]+", prefix):
                raise ValueError("pattern debe ser texto y replacement_prefix [a-z]+")
            patterns.append((re.compile(pattern), prefix))
        except (KeyError, TypeError, AttributeError, ValueError, re.error) as exc:
            errors.append(f"{entry!r}: {exc}")
    return patterns, errors


def projects_root_pattern(projects_root: str) -> dict[str, str]:
    """Patrón que seudonimiza el nombre de cada directorio bajo ``projects_root``.

    ``/Users/u/proyectos/foo/src`` → solo ``foo``. El nombre acaba en ``/``,
    espacio, comillas, backtick, ``\\`` o puntuación de cierre; así un nombre
    truncado (``foo-ba``) también se protege.
    """
    root = projects_root.rstrip("/")
    return {
        "pattern": re.escape(root) + r"/([^/\s\"'`\\:;,()\[\]<>]+)",
        "replacement_prefix": "dir",
    }


def build_rules() -> Rules:
    """Ensambla las reglas por defecto a partir del entorno de la máquina.

    Autodetecta: raíz del repo y home (palanca de rutas), usuario del SO e
    identidad git (literales), org/repo del remote (word-literals). Ampliable:
      - ANTHROPIC_PSEUDO_LITERALS = "valor1,valor2"       (literales substring)
      - ANTHROPIC_PSEUDO_WORD_LITERALS = "orgcode1,orgcode2,proj-id"  (frontera de palabra)
      - ANTHROPIC_PSEUDO_PATHS_EXTRA = "/ruta=label,..."   (prefijos de ruta)
    """
    path_prefixes: list[tuple[str, str]] = []
    literals: list[str] = []
    word_literals: list[str] = []

    home = os.path.expanduser("~")

    if paths_enabled():
        path_prefixes.append((str(project_root()), "proj"))
        if home and home != "~":
            path_prefixes.append((home, "home"))
        extra = os.environ.get("ANTHROPIC_PSEUDO_PATHS_EXTRA", "")
        for item in extra.split(","):
            item = item.strip()
            if "=" in item:
                real, label = item.split("=", 1)
                if real.strip():
                    path_prefixes.append((real.strip(), (label.strip() or "path")))

    try:
        user = getpass.getuser()
    except Exception:
        user = os.path.basename(home) if home else ""
    if user:
        literals.append(user)

    literals.extend(_detect_git_identity())

    extra_lit = os.environ.get("ANTHROPIC_PSEUDO_LITERALS", "")
    literals.extend(v.strip() for v in extra_lit.split(",") if v.strip())

    # Word-literals: org/repo autodetectados + extras de entorno (códigos de
    # cliente orgcode1/orgcode2, IDs de proyecto cloud, dominios corporativos...).
    word_literals.extend(_detect_git_remote_tokens())
    extra_word = os.environ.get("ANTHROPIC_PSEUDO_WORD_LITERALS", "")
    word_literals.extend(v.strip() for v in extra_word.split(",") if v.strip())

    # Persistencia desde config.json — fuente de verdad que sobrevive reinicios.
    # Las env vars tienen prioridad; config.json actúa como fallback/complemento.
    patterns: list[tuple[re.Pattern, str]] = []
    pattern_ignore: list[str] = []
    try:
        import json as _json

        _cfg_path = Path.home() / ".klaus-proxy" / "config.json"
        if _cfg_path.exists():
            _cfg = _json.loads(_cfg_path.read_text(encoding="utf-8"))
            for v in _cfg.get("pseudo_literals", []):
                if v and v not in literals:
                    literals.append(v)
            for v in _cfg.get("pseudo_word_literals", []):
                if v and v not in word_literals:
                    word_literals.append(v)
            patterns, _errors = compile_patterns(_cfg.get("pseudo_patterns"))
            pattern_ignore = [
                v for v in _cfg.get("pseudo_pattern_ignore") or [] if isinstance(v, str)
            ]
    except Exception:
        pass

    # Después de los de config: éstos se escriben con la ruta real completa
    # (``/Users/u/proyectos/…``) y dejarían de casar si el usuario ya se hubiera
    # sustituido.
    if user_dirs_enabled():
        patterns.append((_USER_DIR_RE, "user"))

    regexes: list[tuple[re.Pattern, str]] = []
    if regexes_enabled():
        regexes = [(_EMAIL_RE, "email"), (_IPV4_RE, "ip")]

    secret_regexes: list[tuple[re.Pattern, str]] = []
    if secrets_enabled():
        secret_regexes = list(_SECRET_RES)
    secret_kv = secret_kv_enabled()

    return Rules(
        path_prefixes=path_prefixes,
        literals=literals,
        regexes=regexes,
        word_literals=word_literals,
        secret_regexes=secret_regexes,
        secret_kv=secret_kv,
        patterns=patterns,
        pattern_ignore=pattern_ignore,
        dir_words=dir_words_enabled(),
    )


# --- Núcleo: forward / restore ----------------------------------------------


@functools.lru_cache(maxsize=4096)
def _word_boundary_re(literal: str) -> re.Pattern:
    """Compila un literal con fronteras alfanuméricas (más robusto que \\b para
    tokens con puntos o guiones: ``orgcode3``, ``example.com``)."""
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(literal) + r"(?![A-Za-z0-9_])")


def redact_secrets(text: str, rules: Rules) -> str:
    """Redacta secretos a un placeholder fijo IRREVERSIBLE (no toca el vault).

    Idempotente: el placeholder no vuelve a casar con los patrones de secreto.
    """
    if not text:
        return text
    for regex, label in rules.secret_regexes:
        text = regex.sub(_PLACEHOLDER.format(label=label), text)
    if rules.secret_kv:
        # Redacta solo el valor (grupo 2), conserva la clave (grupo 1).
        text = _SECRET_KV_RE.sub(
            lambda m: m.group(1) + _PLACEHOLDER.format(label="secret-kv"), text
        )
    return text


def _pattern_sub(
    m: "re.Match", prefix: str, vault: Vault, ignore: frozenset[str] = frozenset()
) -> str:
    """Seudonimiza el grupo 1 (o la coincidencia entera si no hay grupos)."""
    group = 1 if m.re.groups else 0
    value = m.group(group)
    if (
        not value
        or _PSEUDONYM_RE.match(value)
        or is_ignorable_pattern_value(value, prefix, ignore)
    ):
        return m.group(0)
    start, end = m.start(group) - m.start(0), m.end(group) - m.start(0)
    whole = m.group(0)
    return whole[:start] + vault.map(value, prefix) + whole[end:]


def pseudonymize_text(text: str, vault: Vault, rules: Rules) -> str:
    """Sustituye datos sensibles por seudónimos, dando de alta los nuevos.

    Orden: (0) secretos → redacción irreversible; (0b) ``pseudo_patterns``
    sobre el texto real (#42); (1) prefijos de ruta; (2) literales substring;
    (3) regex email/IPv4; (4) word-literals con frontera. Regex antes que word-literals para que un email que contenga un
    término corporativo (``dev4@example.com``) se mapee entero como email.
    Idempotente: aplicar dos veces da el mismo resultado.
    """
    if not text:
        return text

    text = redact_secrets(text, rules)

    # Antes que los prefijos de ruta: los patrones se escriben con rutas reales
    # (``/Users/u/proyectos/([^/]+)``) y dejarían de casar tras sustituir el home.
    for pattern, prefix in rules.patterns:
        text = pattern.sub(
            lambda m, _p=prefix: _pattern_sub(m, _p, vault, rules.pattern_ignore),
            text,
        )

    for real_prefix, label in rules.path_prefixes:
        if real_prefix in text:
            text = text.replace(real_prefix, vault.map_path(real_prefix, label))

    for real in rules.literals:
        if real in text:
            text = text.replace(real, vault.map(real, "id"))

    for regex, prefix in rules.regexes:

        def _sub(m: "re.Match", _prefix: str = prefix) -> str:
            return vault.map(m.group(0), _prefix)

        text = regex.sub(_sub, text)

    for real in rules.word_literals:
        pat = _word_boundary_re(real)
        if pat.search(text):
            text = pat.sub(lambda m, _r=real: vault.map(_r, "org"), text)

    # (5) Nombres de carpeta de proyectos ya conocidos, también fuera de una
    # ruta (#93): un ``<carpeta>.md`` o la raíz de un árbol en un README. Con
    # el mismo seudónimo que en la ruta, así la respuesta se restaura igual.
    if rules.dir_words:
        for real, pseudo in vault.dir_words(rules.pattern_ignore):
            if real in text:
                text = _word_boundary_re(real).sub(lambda m, _p=pseudo: _p, text)

    return text


def prune_vault(vault: Vault, rules: Rules) -> list[str]:
    """Quita del vault los valores de patrones que ya no se seudonimizan (#92).

    Solo toca entradas cuyo seudónimo lleva el prefijo de un patrón activo
    (``user_``, ``dir_``…). Devuelve los valores quitados.
    """
    prefixes = {prefix for _pattern, prefix in rules.patterns}
    removed = []
    for real, pseudo in list(vault.real_to_pseudo.items()):
        prefix = pseudo.lstrip("/").split("_", 1)[0]
        if prefix in prefixes and is_ignorable_pattern_value(
            real, prefix, rules.pattern_ignore
        ):
            del vault.real_to_pseudo[real]
            vault.pseudo_to_real.pop(pseudo, None)
            removed.append(real)
    return removed


def restore_text(text: str, vault: Vault) -> str:
    """Revierte cada seudónimo conocido a su valor real (longest-first)."""
    if not text:
        return text
    for pseudo in sorted(vault.pseudo_to_real, key=len, reverse=True):
        if pseudo in text:
            text = text.replace(pseudo, vault.pseudo_to_real[pseudo])
    return text


# --- Transformación estructural sobre JSON ----------------------------------
# CLAVE: nunca aplicar regex sobre el JSON YA serializado — una sustitución
# puede partir una secuencia de escape (p.ej. comerse el `\` de un `\"`) y
# romper el JSON. En su lugar se parsea, se transforma SOLO el contenido de los
# valores string, y se re-serializa: el encoder re-escapa comillas/backslashes.


def _transform_json_strings(obj: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_transform_json_strings(x, fn) for x in obj]
    if isinstance(obj, dict):
        # Solo valores; las claves son del esquema de la API, no datos del usuario.
        return {k: _transform_json_strings(v, fn) for k, v in obj.items()}
    return obj


def pseudonymize_body(raw: str, vault: Vault, rules: Rules) -> str:
    """Seudonimiza el cuerpo de una request.

    Si es JSON, transforma los valores string y re-serializa (a prueba de
    corrupción de escapes). Si no es JSON, cae a texto plano.
    """
    if not raw:
        return raw
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return pseudonymize_text(raw, vault, rules)
    new = _transform_json_strings(obj, lambda s: pseudonymize_text(s, vault, rules))
    return json.dumps(new, ensure_ascii=False, separators=(",", ":"))


def redact_secrets_body(raw: str, rules: Rules) -> str:
    """Redacta SOLO los secretos Tier-1 del cuerpo, sin seudonimizar el resto.

    Es el cuerpo que se persiste como ``original`` en la auditoría: conserva en
    claro los datos reales que interesa comparar (rutas, identidad, prompts,
    contenido de ficheros) pero JAMÁS deja caer a disco una credencial —clave
    privada, token AWS/GitHub, JWT…— que se sustituye por ``«REDACTED:label»``.

    Si es JSON, transforma los valores string y re-serializa (a prueba de
    corrupción de escapes, igual que ``pseudonymize_body``). Si no, texto plano.
    """
    if not raw:
        return raw
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return redact_secrets(raw, rules)
    new = _transform_json_strings(obj, lambda s: redact_secrets(s, rules))
    return json.dumps(new, ensure_ascii=False, separators=(",", ":"))


# Campo con el fragmento de texto de cada tipo de delta SSE de /v1/messages.
_SSE_DELTA_FIELDS = {
    "text_delta": "text",
    "input_json_delta": "partial_json",
    "thinking_delta": "thinking",
}
_SSE_EVENT_SEP = re.compile(r"(\r?\n\r?\n)")
_SSE_DATA_LINE = re.compile(r"^data: ?(.*)$", re.M)


def _restore_partial_json(full: str, vault: Vault) -> str:
    """Revierte el JSON de un tool_use reconstruido; re-serializa para escapar
    bien valores reales con ``"`` o ``\\``. Si no parsea, texto plano."""
    try:
        obj = json.loads(full)
    except (json.JSONDecodeError, ValueError):
        return restore_text(full, vault)
    new = _transform_json_strings(obj, lambda s: restore_text(s, vault))
    return json.dumps(new, ensure_ascii=False)


def restore_sse(raw: str, vault: Vault) -> str | None:
    """Revierte una response SSE de /v1/messages a nivel de bloque (#67).

    El texto, los argumentos de tool_use y el thinking viajan troceados en
    ``content_block_delta`` y el cliente los concatena, así que un seudónimo
    puede quedar partido entre dos deltas y un ``replace`` sobre el cuerpo no lo
    ve. Aquí se concatena cada bloque, se restaura completo y se emite entero en
    su primer delta (los demás quedan vacíos): el cliente obtiene el mismo
    resultado al concatenar. El resto de eventos se revierte como JSON.

    Devuelve ``None`` si no parece SSE o algún evento no se puede interpretar,
    para que el llamador use el camino de siempre.
    """
    parts = _SSE_EVENT_SEP.split(raw)
    events: list[dict[str, Any]] = []  # {"text", "obj", "line"}
    groups: dict[tuple[Any, str], list[int]] = {}
    for i in range(0, len(parts), 2):
        text = parts[i]
        lines = _SSE_DATA_LINE.findall(text)
        if not lines:
            events.append({"text": text, "obj": None})
            continue
        if len(lines) > 1:
            return None
        try:
            obj = json.loads(lines[0])
        except (json.JSONDecodeError, ValueError):
            return None
        events.append({"text": text, "obj": obj})
        delta = obj.get("delta") if isinstance(obj, dict) else None
        if obj.get("type") == "content_block_delta" and isinstance(delta, dict):
            field = _SSE_DELTA_FIELDS.get(delta.get("type"))
            if field and isinstance(delta.get(field), str):
                groups.setdefault((obj.get("index"), field), []).append(len(events) - 1)
    if not any(e["obj"] is not None for e in events):
        return None

    in_group = {i for idxs in groups.values() for i in idxs}
    for (_, field), idxs in groups.items():
        full = "".join(events[i]["obj"]["delta"][field] for i in idxs)
        restored = (
            _restore_partial_json(full, vault)
            if field == "partial_json"
            else restore_text(full, vault)
        )
        if restored == full:
            continue
        for n, i in enumerate(idxs):
            events[i]["obj"]["delta"][field] = restored if n == 0 else ""
            events[i]["dirty"] = True
    for i, ev in enumerate(events):
        if ev["obj"] is None or i in in_group:
            continue
        new = _transform_json_strings(ev["obj"], lambda s: restore_text(s, vault))
        if new != ev["obj"]:
            ev["obj"], ev["dirty"] = new, True

    out: list[str] = []
    for n, ev in enumerate(events):
        text = ev["text"]
        if ev.get("dirty"):
            data = json.dumps(ev["obj"], ensure_ascii=False, separators=(",", ":"))
            text = _SSE_DATA_LINE.sub(lambda _m: "data: " + data, text, count=1)
        out.append(text)
        if 2 * n + 1 < len(parts):
            out.append(parts[2 * n + 1])
    return "".join(out)


def sse_block_text(raw: str) -> str:
    """Texto de los deltas de una response SSE ya concatenado por bloque.

    Para buscar seudónimos que siguen partidos entre deltas; ``""`` si no es SSE.
    """
    blocks: dict[tuple[Any, str], list[str]] = {}
    for line in _SSE_DATA_LINE.findall(raw):
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        delta = obj.get("delta") if isinstance(obj, dict) else None
        if obj.get("type") == "content_block_delta" and isinstance(delta, dict):
            field = _SSE_DELTA_FIELDS.get(delta.get("type"))
            if field and isinstance(delta.get(field), str):
                blocks.setdefault((obj.get("index"), field), []).append(delta[field])
    return "\n".join("".join(chunks) for chunks in blocks.values())


def restore_body(raw: str, vault: Vault) -> str:
    """Revierte el cuerpo de una response. JSON → estructural; SSE → por bloque
    (seudónimos partidos entre deltas, #67); si no, texto plano."""
    if not raw:
        return raw
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sse = restore_sse(raw, vault)
        return sse if sse is not None else restore_text(raw, vault)
    new = _transform_json_strings(obj, lambda s: restore_text(s, vault))
    return json.dumps(new, ensure_ascii=False, separators=(",", ":"))


def _find_unreversed_pseudonyms(text: str, vault: Vault) -> list[str]:
    """Find pseudonyms in text that weren't reverted (sanity check).

    Pseudonym pattern: prefix_<8hex>[z*] (e.g., /proj_a1b2c3d4, id_x9y8z7w6).
    Used to detect vault corruption or reversal failures.

    Returns list of unreversed pseudonyms found.
    """
    if not text or not vault.pseudo_to_real:
        return []

    # Pattern: word chars, underscore, 8 hex digits, optional z's for collision resolution
    pseudo_pattern = re.compile(r"\b[a-z]+_[0-9a-f]{8}z*\b")
    found = pseudo_pattern.findall(text)

    # Filter out false positives: only report if pseudonym is actually in vault.
    # Path pseudonyms are stored with their leading slash (/proj_…, #67).
    unreversed = [
        p
        for p in set(found)
        if p in vault.pseudo_to_real or "/" + p in vault.pseudo_to_real
    ]
    return sorted(unreversed)


# --- Fail-closed --------------------------------------------------------------


def fail_closed_body(exc: Exception) -> bytes:
    """Cuerpo de la respuesta de bloqueo que ve el cliente cuando el proxy corta
    una request por no poder garantizar su seudonimización (fail-closed).

    Función pura → unit-testable sin mitmproxy.
    """
    return (
        "klaus-proxy (auditoría): request BLOQUEADA en modo fail-closed.\n"
        "No se pudo garantizar la seudonimización del cuerpo, de modo que NO se "
        "ha enviado a Anthropic para evitar una posible fuga de datos.\n"
        f"Motivo: {type(exc).__name__}: {exc}\n"
    ).encode("utf-8")


# --- Hooks de mitmproxy ------------------------------------------------------


class AnthropicPseudonymizer:
    """Addon de mitmproxy: seudonimiza la request y revierte la response.

    Nota de streaming: en esta versión el cuerpo de la respuesta se procesa
    COMPLETO (mitmproxy bufferiza por defecto). Es correcto para tool calls,
    pero retrasa el render token-a-token. La variante en streaming (reemplazo
    con buffer de arrastre sobre SSE) queda como mejora posterior.
    """

    def __init__(self, vault: Vault | None = None, rules: Rules | None = None) -> None:
        self._vault = vault
        self._rules = rules
        self._generic_warned: set[str] = set()

    def _get_vault(self) -> Vault:
        if self._vault is None:
            self._vault = Vault.load()
        return self._vault

    def _get_rules(self) -> Rules:
        if self._rules is None:
            self._rules = build_rules()
        return self._rules

    def _log(self, msg: str, level: str | None = None) -> None:
        out = colorize(msg, level) if level else msg
        try:
            from mitmproxy import ctx

            ctx.log.info(out)
        except Exception:
            print(out)

    def request(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        # Prueba de vida para klaus_pseudo_guard: si este addon no está cargado
        # (p. ej. falló una recarga), el guardián bloquea la request (#71).
        flow.metadata["klaus_pseudo_seen"] = True
        if not enabled():
            return
        req = flow.request
        is_configured = is_target_host(req.pretty_host)
        is_llm = is_llm_path(req.path)
        if not is_configured:
            if is_llm:
                # Defense-in-depth: host desconocido pero ruta LLM → pseudonimizar
                # igualmente y advertir para que el usuario añada el host a config.json.
                self._log(
                    f"[anthropic-pseudo] WARN host desconocido con ruta LLM: "
                    f"{req.pretty_host}{req.path} — pseudonimizando igualmente. "
                    f"Añade este host a ~/.Klaus-proxy/config.json",
                    level="warn",
                )
                flow.metadata["anthropic_unknown_host"] = req.pretty_host
            else:
                return
        # Fail-closed: si CUALQUIER paso de la seudonimización falla (no se puede
        # leer el cuerpo, reescribirlo, etc.), NO dejamos salir la request — la
        # abortamos localmente. Un cuerpo que no hemos podido seudonimizar nunca
        # llega a Anthropic. Sin esta red, una excepción en un hook de mitmproxy se
        # loguea pero el flujo continúa con el cuerpo ORIGINAL (fail-open).
        try:
            self._pseudonymize_request(flow, req)
        except Exception as exc:  # noqa: BLE001 - red de seguridad deliberada
            self._fail_closed(flow, req, exc)

    def learn_repo_tokens(self, text: str, rules: Rules) -> list[str]:
        """Protege el org/repo que trae la propia petición ANTES de reescribirla.

        Así un repo desde el que nunca se arrancó ``claude-proxy`` no sale en
        claro (#63). Best-effort: un fallo aquí solo se avisa, la seudonimización
        sigue con las reglas que ya hay. Devuelve los tokens nuevos.
        """
        try:
            tokens = remote_tokens_from_payload(text)
            for tok in tokens:
                if is_generic_repo_token(tok) and tok not in self._generic_warned:
                    self._generic_warned.add(tok)
                    self._log(
                        f"[anthropic-pseudo] WARN org/repo genérico no protegido: "
                        f"{tok} (añádelo a pseudo_word_literals si es privado)",
                        level="warn",
                    )
            added = rules.add_word_literals(
                [t for t in tokens if not is_generic_repo_token(t)]
            )
            if added:
                self._log(
                    f"[anthropic-pseudo] 🛡️ org/repo nuevo protegido: "
                    f"{', '.join(added)}",
                    level="ok",
                )
                try:
                    add_word_literals_to_config(added)
                except Exception as exc:  # noqa: BLE001
                    self._log(
                        f"[anthropic-pseudo] WARN no pude guardar org/repo en "
                        f"config.json: {type(exc).__name__}: {exc} (protegido "
                        f"solo hasta reiniciar)",
                        level="warn",
                    )
            return added
        except Exception as exc:  # noqa: BLE001
            self._log(
                f"[anthropic-pseudo] WARN no pude leer org/repo de la petición: "
                f"{type(exc).__name__}: {exc}",
                level="warn",
            )
            return []

    def _pseudonymize_request(self, flow: Any, req: Any) -> None:  # pragma: no cover
        """Reescribe el cuerpo de la request. Cualquier excepción sube a
        ``request`` y dispara ``_fail_closed`` (no debe tragarse errores)."""
        text = req.get_text(strict=False)
        if not text:
            return
        vault = self._get_vault()
        rules = self._get_rules()
        self.learn_repo_tokens(text, rules)
        before = len(vault.pseudo_to_real)
        # `original`: datos reales con SOLO los secretos Tier-1 redactados (nunca
        # se persiste una credencial). `new`: cuerpo totalmente seudonimizado que
        # sale del equipo. Se deja el original en flow.metadata para que el addon
        # de captura (que corre DESPUÉS) grabe el par original/enviado.
        original = redact_secrets_body(text, rules)
        new = pseudonymize_body(text, vault, rules)
        flow.metadata["anthropic_original_body"] = original
        flow.metadata["anthropic_pseudonymized"] = bool(new != original)
        flow.metadata["anthropic_pseudo_ran"] = (
            True  # #38: corrió aunque no modificó nada
        )
        # Mapa real→seudónimo YA poblado por el cuerpo, para que la captura
        # seudonimice también url/host/cabeceras del registro `sent` con los
        # MISMOS seudónimos y sin acuñar ninguno nuevo.
        flow.metadata["anthropic_vault_forward"] = dict(vault.real_to_pseudo)
        # Reescribimos el cuerpo ANTES de persistir el vault: aunque el guardado
        # del vault falle, lo que sale ya va seudonimizado.
        if new != text:
            req.set_text(new)
        if len(vault.pseudo_to_real) != before:
            try:
                vault.save()
            except Exception as exc:  # noqa: BLE001
                # La request YA va seudonimizada; solo se degradó la persistencia
                # del vault → aviso (amarillo), sin bloquear ni fallar.
                self._log(
                    f"[anthropic-pseudo] WARN no pude persistir el vault: "
                    f"{type(exc).__name__}: {exc} (la request va seudonimizada)",
                    level="warn",
                )
        # Verde si reescribimos el cuerpo (algo sensible neutralizado); neutro si
        # no hubo nada que seudonimizar en esta request (p.ej. telemetría).
        self._log(
            f"[anthropic-pseudo] request {req.method} {req.path} "
            f"seudónimos={len(vault.pseudo_to_real)}",
            level="ok" if new != text else None,
        )

    def _fail_closed(
        self, flow: Any, req: Any, exc: Exception
    ) -> None:  # pragma: no cover
        """Corta la request localmente para que NO salga sin seudonimizar.

        Fija ``flow.response`` (mitmproxy responde sin contactar con el servidor) y
        marca ``anthropic_blocked`` para que la captura no registre el cuerpo como
        'enviado'. Si ni siquiera podemos construir la respuesta, matamos el flujo.
        """
        try:
            flow.metadata["anthropic_blocked"] = True
        except Exception:
            pass
        try:
            from mitmproxy import http

            flow.response = http.Response.make(
                502,
                fail_closed_body(exc),
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        except Exception:
            # Sin respuesta de bloqueo disponible, matamos el flujo: preferible a
            # dejar salir el cuerpo original.
            try:
                flow.kill()
            except Exception:
                pass
        self._log(
            f"[anthropic-pseudo] BLOQUEADA (fail-closed) {req.method} {req.path}: "
            f"{type(exc).__name__}: {exc} — la request NO salió",
            level="error",
        )

    def response(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        if not enabled():
            return
        req = flow.request
        if not is_target_host(req.pretty_host):
            return
        try:
            text = flow.response.get_text(strict=False)
        except Exception:
            # No poder revertir la response NO es una fuga (va hacia el CLI, no
            # hacia Anthropic): avisamos en amarillo y dejamos pasar. Bloquearla
            # solo rompería la sesión del usuario.
            self._log(
                f"[anthropic-pseudo] WARN no pude leer la response de {req.path} — "
                f"no se revierte (el CLI puede ver seudónimos)",
                level="warn",
            )
            return
        if not text:
            return

        vault = self._get_vault()
        new = restore_body(text, vault)

        # Sanity check: detect unreversed pseudonyms (vault corruption, reversal bug)
        unreversed = _find_unreversed_pseudonyms(
            new + "\n" + sse_block_text(new), vault
        )
        if unreversed:
            self._log(
                f"[anthropic-pseudo] WARN unreversed pseudonyms in response {req.path}: {unreversed}",
                level="warn",
            )

        if new != text:
            flow.response.set_text(new)
            self._log(f"[anthropic-pseudo] response {req.path} revertida", level="ok")


# mitmproxy busca una variable de módulo ``addons``.
addons = [AnthropicPseudonymizer()]
