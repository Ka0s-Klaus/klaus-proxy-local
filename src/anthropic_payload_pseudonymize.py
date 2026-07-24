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
             -s src/anthropic_payload_capture.py -p 8899
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

TOOL_ROOT = Path(__file__).resolve().parents[1]


def project_root() -> Path:
    """Raíz del proyecto AUDITADO (no la del tooling).

    Es la raíz de la palanca de rutas y el cwd para detectar identidad/remote
    git. Por defecto el directorio de trabajo del proceso mitmdump (el
    `claude-proxy` hace `cd` al repo auditado); override explícito con
    ANTHROPIC_PSEUDO_PROJECT_ROOT.
    """
    override = os.environ.get("ANTHROPIC_PSEUDO_PROJECT_ROOT")
    return Path(override) if override else Path.cwd()


# Hosts sobre los que se reescribe. Mismos que la captura (gateway + Anthropic).
_DEFAULT_HOSTS = (
    "api.anthropic.com",
    "llm.tools.cloud.customer1.es",
)

# Regex de datos sensibles con forma reconocible.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# IPv4 con 4 octetos delimitados por punto (evita versiones tipo 4.8.0).
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

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
    override = os.environ.get("ANTHROPIC_PSEUDO_HOSTS") or os.environ.get(
        "ANTHROPIC_CAPTURE_HOSTS"
    )
    if override:
        return tuple(h.strip().lower() for h in override.split(",") if h.strip())
    return _DEFAULT_HOSTS


def is_target_host(host: str) -> bool:
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in _configured_hosts())


def _salt() -> str:
    return os.environ.get("ANTHROPIC_PSEUDO_SALT", "mo-ecosistema1-audit")


def vault_path() -> Path:
    override = os.environ.get("ANTHROPIC_PSEUDO_VAULT")
    if override:
        return Path(override)
    return TOOL_ROOT / "captures" / ".pseudonym_vault.json"


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
        path = path or vault_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
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
    """

    def __init__(
        self,
        path_prefixes: list[tuple[str, str]] | None = None,
        literals: list[str] | None = None,
        regexes: list[tuple[re.Pattern, str]] | None = None,
        word_literals: list[str] | None = None,
        secret_regexes: list[tuple[re.Pattern, str]] | None = None,
        secret_kv: bool = False,
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
    ``["example-org", "customer1-ecosistema1"]``. Se descartan tokens de
    menos de 3 chars, los que contienen punto (hosts) y los genéricos de
    plataforma (github/gitlab/...). Función pura → unit-testable sin git.
    """
    tokens: list[str] = []
    if not url:
        return tokens
    # Normaliza scp-like y https, quita credenciales embebidas y .git final.
    tail = re.sub(r"^[a-z]+://", "", url.strip())
    tail = tail.split("@")[-1]  # quita user[:pass]@
    tail = re.sub(r"[:/]", " ", tail)  # host:org/repo → host org repo
    tail = re.sub(r"\.git\b", " ", tail)
    for tok in tail.split():
        tok = tok.strip()
        if (
            len(tok) >= 3
            and tok.lower() not in _GENERIC_REMOTE_TOKENS
            and "." not in tok
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
    )


# --- Núcleo: forward / restore ----------------------------------------------


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


def pseudonymize_text(text: str, vault: Vault, rules: Rules) -> str:
    """Sustituye datos sensibles por seudónimos, dando de alta los nuevos.

    Orden: (0) secretos → redacción irreversible; (1) prefijos de ruta;
    (2) literales substring; (3) regex email/IPv4; (4) word-literals con
    frontera. Regex antes que word-literals para que un email que contenga un
    término corporativo (``dev4@example.com``) se mapee entero como email.
    Idempotente: aplicar dos veces da el mismo resultado.
    """
    if not text:
        return text

    text = redact_secrets(text, rules)

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

    return text


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


def restore_body(raw: str, vault: Vault) -> str:
    """Revierte el cuerpo de una response. JSON → estructural; si no, texto plano
    (respuestas SSE en streaming caen aquí; los seudónimos no llevan chars JSON
    especiales, así que la reversión en texto plano es segura)."""
    if not raw:
        return raw
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return restore_text(raw, vault)
    new = _transform_json_strings(obj, lambda s: restore_text(s, vault))
    return json.dumps(new, ensure_ascii=False, separators=(",", ":"))


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

    def _get_vault(self) -> Vault:
        if self._vault is None:
            self._vault = Vault.load()
        return self._vault

    def _get_rules(self) -> Rules:
        if self._rules is None:
            self._rules = build_rules()
        return self._rules

    def _log(self, msg: str) -> None:
        try:
            from mitmproxy import ctx

            ctx.log.info(msg)
        except Exception:
            print(msg)

    def request(self, flow: Any) -> None:  # pragma: no cover - requiere mitmproxy
        if not enabled():
            return
        req = flow.request
        if not is_target_host(req.pretty_host):
            return
        try:
            text = req.get_text(strict=False)
        except Exception:
            return
        if not text:
            return
        vault = self._get_vault()
        rules = self._get_rules()
        before = len(vault.pseudo_to_real)
        # `original`: datos reales con SOLO los secretos Tier-1 redactados (nunca
        # se persiste una credencial). `new`: cuerpo totalmente seudonimizado que
        # sale del equipo. Se deja el original en flow.metadata para que el addon
        # de captura (que corre DESPUÉS) grabe el par original/enviado.
        original = redact_secrets_body(text, rules)
        new = pseudonymize_body(text, vault, rules)
        try:
            flow.metadata["anthropic_original_body"] = original
            flow.metadata["anthropic_pseudonymized"] = bool(new != original)
            # Mapa real→seudónimo YA poblado por el cuerpo, para que la captura
            # seudonimice también url/host/cabeceras del registro `sent` con los
            # MISMOS seudónimos y sin acuñar ninguno nuevo.
            flow.metadata["anthropic_vault_forward"] = dict(vault.real_to_pseudo)
        except Exception:
            # metadata es solo traza para el addon de captura; su ausencia no
            # afecta a la reescritura del cuerpo.
            pass
        if new != text:
            req.set_text(new)
        if len(vault.pseudo_to_real) != before:
            vault.save()
        self._log(
            f"[anthropic-pseudo] request {req.method} {req.path} "
            f"seudónimos={len(vault.pseudo_to_real)}"
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
            return
        if not text:
            return
        new = restore_body(text, self._get_vault())
        if new != text:
            flow.response.set_text(new)
            self._log(f"[anthropic-pseudo] response {req.path} revertida")


# mitmproxy busca una variable de módulo ``addons``.
addons = [AnthropicPseudonymizer()]
