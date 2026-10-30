#!/usr/bin/env python3
"""Detección de nombres de negocio para ``klaus-scan`` (#140).

El proxy solo pseudonimiza lo que casa con una regla: un cliente, una razón
social o un dominio corporativo que no esté en ``pseudo_word_literals`` /
``pseudo_literals`` sale en claro. Este detector busca esos valores en una
carpeta para proponerlos como reglas:

- razón social con forma jurídica y titular de copyright;
- dominios de email y de URL no públicos (y el tenant de un SaaS:
  ``cliente-x.atlassian.net``), también los de los autores en ``git log``;
- IDs de proyecto cloud (GCP, cuenta AWS, suscripción Azure);
- identidad de paquete en los manifiestos (npm, composer, Maven, Go, pyproject);
- claves de proyecto de los IDs de incidencia (``PRJ-123``).

Cada valor se devuelve una sola vez, con sus apariciones, y lo ya protegido en
config.json solo se cuenta.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Callable

BUSINESS_CATEGORIES = (
    "business-name",
    "corporate-domain",
    "cloud-project",
    "package-name",
    "issue-key",
)

# --- Dominios públicos ---------------------------------------------------------

PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "outlook.es",
        "hotmail.com",
        "hotmail.es",
        "live.com",
        "msn.com",
        "yahoo.com",
        "yahoo.es",
        "icloud.com",
        "me.com",
        "mac.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "gmx.de",
        "aol.com",
        "zoho.com",
        "yandex.ru",
        "mail.com",
        "users.noreply.github.com",
        "noreply.github.com",
    }
)

PUBLIC_DOMAINS = frozenset(
    {
        "github.com",
        "githubusercontent.com",
        "githubassets.com",
        "gitlab.com",
        "bitbucket.org",
        "google.com",
        "googleapis.com",
        "gstatic.com",
        "goo.gl",
        "youtube.com",
        "youtu.be",
        "microsoft.com",
        "visualstudio.com",
        "azure.com",
        "amazon.com",
        "amazonaws.com",
        "cloudflare.com",
        "docker.com",
        "docker.io",
        "python.org",
        "pypi.org",
        "pythonhosted.org",
        "npmjs.com",
        "npmjs.org",
        "yarnpkg.com",
        "nodejs.org",
        "mozilla.org",
        "w3.org",
        "schema.org",
        "json-schema.org",
        "apache.org",
        "readthedocs.io",
        "readthedocs.org",
        "shields.io",
        "wikipedia.org",
        "stackoverflow.com",
        "anthropic.com",
        "claude.ai",
        "claude.com",
        "openai.com",
        "gnu.org",
        "opensource.org",
        "creativecommons.org",
        "golang.org",
        "go.dev",
        "rust-lang.org",
        "crates.io",
        "mitmproxy.org",
        "jsdelivr.net",
        "unpkg.com",
        "apple.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "facebook.com",
        "medium.com",
        "gradle.org",
        "kubernetes.io",
        "k8s.io",
        "helm.sh",
        "hashicorp.com",
        "terraform.io",
        "ubuntu.com",
        "debian.org",
        "alpinelinux.org",
        "redhat.com",
        "oracle.com",
        "postgresql.org",
        "mongodb.com",
        "redis.io",
        "nginx.org",
        "nginx.com",
        "letsencrypt.org",
        "sentry.io",
        "datadoghq.com",
        "brew.sh",
        "keepachangelog.com",
        "semver.org",
        "codecov.io",
        "circleci.com",
        "snyk.io",
        "discord.com",
        "discord.gg",
        "pre-commit.com",
        "astral.sh",
        "pytest.org",
        "djangoproject.com",
        "palletsprojects.com",
        "reactjs.org",
        "react.dev",
        "vuejs.org",
        "angular.io",
        "typescriptlang.org",
        "eslint.org",
        "prettier.io",
        "jestjs.io",
        "vitejs.dev",
        "spring.io",
        "maven.org",
        "jetbrains.com",
        "atlassian.com",
        "slack.com",
        "notion.so",
        "figma.com",
        "vercel.com",
        "netlify.com",
        "heroku.com",
    }
)

# SaaS multi-tenant: el subdominio es el nombre del cliente
TENANT_SUFFIXES = (
    "atlassian.net",
    "slack.com",
    "sharepoint.com",
    "okta.com",
    "my.salesforce.com",
    "zendesk.com",
    "herokuapp.com",
    "azurewebsites.net",
    "vercel.app",
    "netlify.app",
    "myshopify.com",
    "github.io",
    "gitlab.io",
    "auth0.com",
    "service-now.com",
    "freshdesk.com",
    "visualstudio.com",
    "monday.com",
)

# Segundo nivel de los ccTLD (``cliente.co.uk``)
_SECOND_LEVEL = frozenset(
    {"co", "com", "org", "net", "gob", "gov", "ac", "edu", "nom", "ltd", "plc"}
)

_RESERVED_TLDS = frozenset(
    {"example", "test", "invalid", "localhost", "local", "internal", "corp", "intra"}
)


def registrable_domain(host: str) -> str:
    """``api.eu.cliente-x.co.uk`` → ``cliente-x.co.uk``."""
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _is_public(domain: str, public: frozenset[str]) -> bool:
    labels = domain.split(".")
    if len(labels) < 2 or labels[-1] in _RESERVED_TLDS:
        return True
    if labels[-2] == "example":
        return True
    # Una "extensión" de fichero o código no es un TLD (``config.json``)
    if not labels[-1].isalpha() or len(labels[-1]) > 12:
        return True
    return registrable_domain(domain) in public or domain in public


def domain_value(host: str, public: frozenset[str] = PUBLIC_DOMAINS) -> str | None:
    """Valor a proteger de un host: el tenant de un SaaS o el dominio propio."""
    host = host.lower().strip(".")
    for suffix in TENANT_SUFFIXES:
        if host.endswith("." + suffix):
            tenant = host[: -len(suffix) - 1].split(".")[-1]
            return f"{tenant}.{suffix}" if len(tenant) >= 3 else None
    if re.fullmatch(r"[\d.]+", host) or _is_public(host, public):
        return None
    return registrable_domain(host)


# --- Expresiones ---------------------------------------------------------------

_UPPER = "A-ZÁÉÍÓÚÑÜÇ"
_WORD = rf"[{_UPPER}][\w&'’.-]*"
_LEGAL_SUFFIX = (
    r"S\.\s?L\.(?:\s?U\.)?|S\.\s?A\.(?:\s?U\.)?|S\.\s?L\.\s?L\.|S\.\s?Coop\."
    r"|SLU|SAU|GmbH|AG|Inc\.?|LLC|L\.L\.C\.|Ltd\.?|Limited|S\.A\.S\.|SAS|B\.V\."
    r"|BV|S\.r\.l\.|SRL|S\.p\.A\.|SpA|PLC|plc|Corp\.?|Corporation|Co\.,?\s?Ltd\.?"
)
_LEGAL_NAME_RE = re.compile(
    rf"(?<![\w.])((?:{_WORD})(?:\s+(?:{_WORD}|de|del|y|&|and|of))"
    rf"{{0,4}}),?\s+({_LEGAL_SUFFIX})(?![\w])"
)
_COPYRIGHT_RE = re.compile(
    r"(?:copyright|©)\s*(?:\(c\)|©)?\s*((?:19|20)\d{2})(?:\s*[-–,]\s*(?:19|20)?\d{2,4})*"
    r"\s*,?\s*(?:by\s+)?([^\n]{2,80})",
    re.IGNORECASE,
)
_COPYRIGHT_STOP = re.compile(
    r"\s*(?:all rights reserved|todos los derechos|licen[cs]ed|<|-->|\*/|\(|\[|;|$)",
    re.IGNORECASE,
)
_COPYRIGHT_GENERIC = re.compile(
    r"contributors|the authors|authors|free software foundation|"
    r"python software foundation|the project|original author|\{|\$",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
_URL_HOST_RE = re.compile(
    r"(?:https?|wss?|ftp|git|ssh)://(?:[^@/\s]+@)?([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)"
)
_CLOUD_RES = (
    re.compile(
        r"(?:project_id|projectId|project-id|GOOGLE_CLOUD_PROJECT|GCP_PROJECT|"
        r"GCLOUD_PROJECT)[\"']?\s*[:=]\s*[\"']?([a-z][a-z0-9-]{4,28}[a-z0-9])\b"
    ),
    re.compile(r"--project[= ]([a-z][a-z0-9-]{4,28}[a-z0-9])\b"),
    re.compile(r"\bprojects/([a-z][a-z0-9-]{4,28}[a-z0-9])/"),
    re.compile(r"arn:aws[\w-]*:[\w-]*:[\w-]*:(\d{12}):"),
    re.compile(
        r"(?:aws_account_id|AWS_ACCOUNT_ID|account_id|accountId)[\"']?\s*[:=]\s*"
        r"[\"']?(\d{12})\b"
    ),
    re.compile(r"/subscriptions/([0-9a-fA-F-]{36})\b"),
)
_CLOUD_PLACEHOLDER = re.compile(
    r"example|sample|your|my-|demo|test|project-id|placeholder|xxxx|^0+$|^1234",
    re.IGNORECASE,
)
_ISSUE_KEY_RE = re.compile(r"(?<![\w-])([A-Z][A-Z0-9]{1,9})-(\d{1,6})(?![\w-])")
_ISSUE_KEY_COMMON = frozenset(
    {
        "ISO", "UTF", "SHA", "RFC", "CVE", "CWE", "GPL", "LGPL", "AGPL", "MIT",
        "BSD", "HTTP", "TLS", "SSL", "AES", "RSA", "EC", "PEP", "ES", "ECMA",
        "IEEE", "ANSI", "ASCII", "GHSA", "WCAG", "ISBN", "DIN", "EN", "UNE",
        "NIST", "PCI", "SOC", "CSS", "HTML", "XSS", "OWASP", "API", "GPT", "ID",
        "IP", "PR", "IE", "OS", "CI", "CD", "US", "EU", "UK", "IDE", "JDK",
        "JRE", "VS", "K8S", "IPV", "TC", "SP", "ARM", "AMD", "KB", "MB", "GB",
        "TB", "COVID", "SARS", "MP", "UTC", "GMT", "CET", "CEST", "PST", "EST",
        "TODO", "FIXME", "XXX", "BUG", "FIX", "V", "VER", "REV", "STEP", "PHASE",
        "FASE", "TIER", "ITEM", "TEST", "CASE", "DEV", "PRE", "POST", "AUTO",
    }
)  # fmt: skip
ISSUE_KEY_MIN = 3

_GENERIC_ORGS = frozenset(
    {
        "com", "org", "net", "io", "es", "eu", "de", "fr", "uk", "co",
        "apache", "springframework", "google", "junit", "maven", "fasterxml",
        "slf4j", "netty", "jetbrains", "github", "gitlab", "microsoft",
        "amazon", "amazonaws", "example", "types", "babel", "angular", "vue",
        "react", "nestjs", "aws-sdk", "golang", "x", "gopkg", "mycompany",
    }
)  # fmt: skip


class RawHit:
    """Un valor de negocio encontrado en un fichero (antes de agregar)."""

    __slots__ = ("value", "category", "confidence", "path", "line", "reason")

    def __init__(self, value, category, confidence, path, line, reason):
        self.value = value
        self.category = category
        self.confidence = confidence
        self.path = path
        self.line = line
        self.reason = reason


def _clean_holder(text: str) -> str | None:
    holder = _COPYRIGHT_STOP.split(text, maxsplit=1)[0]
    holder = holder.strip(" \t.,:-–\"'`*#/")
    if len(holder) < 3 or not re.search(rf"[{_UPPER}a-z]", holder):
        return None
    if _COPYRIGHT_GENERIC.search(holder):
        return None
    return holder


def detect_line(line: str) -> list[tuple[str, str, str, str]]:
    """``(valor, categoría, confianza, motivo)`` de una línea de texto."""
    hits: list[tuple[str, str, str, str]] = []
    copyright_holders = set()
    for m in _COPYRIGHT_RE.finditer(line):
        holder = _clean_holder(m.group(2))
        if holder:
            copyright_holders.add(holder)
            hits.append((holder, "business-name", "HIGH", "Titular de copyright"))
    for m in _LEGAL_NAME_RE.finditer(line):
        name = re.sub(r"^(?:The|El|La|Los|Las)\s+", "", m.group(0).strip())
        if not any(name in h for h in copyright_holders):
            hits.append((name, "business-name", "HIGH", "Razón social"))
    for m in _EMAIL_RE.finditer(line):
        domain = m.group(1).lower()
        if domain in PUBLIC_EMAIL_DOMAINS:
            continue
        value = domain_value(domain)
        if value:
            hits.append((value, "corporate-domain", "HIGH", "Dominio de email"))
    for m in _URL_HOST_RE.finditer(line):
        value = domain_value(m.group(1))
        if value:
            hits.append((value, "corporate-domain", "MEDIUM", "Dominio de URL"))
    for regex in _CLOUD_RES:
        for m in regex.finditer(line):
            value = m.group(1)
            if not _CLOUD_PLACEHOLDER.search(value):
                hits.append((value, "cloud-project", "HIGH", "ID de proyecto cloud"))
    for m in _ISSUE_KEY_RE.finditer(line):
        if m.group(1) not in _ISSUE_KEY_COMMON:
            hits.append((m.group(1), "issue-key", "LOW", "Clave de incidencias"))
    return hits


# --- Manifiestos ---------------------------------------------------------------


def _org_tokens(*values: str) -> list[str]:
    return [
        v
        for v in values
        if v and len(v) >= 3 and v.lower() not in _GENERIC_ORGS and "{" not in v
    ]


def _authors(raw) -> list[str]:
    items = raw if isinstance(raw, list) else [raw]
    names = []
    for item in items:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str):
            name = re.sub(r"\s*[<(].*$", "", name).strip()
            if len(name) >= 3:
                names.append(name)
    return names


def detect_manifest(path: Path, content: str) -> list[tuple[str, str]]:
    """``(valor, motivo)`` de identidad de paquete en un manifiesto."""
    name = path.name
    out: list[tuple[str, str]] = []
    try:
        if name == "package.json":
            data = json.loads(content)
            pkg = str(data.get("name") or "")
            scope = pkg[1:].split("/")[0] if pkg.startswith("@") else ""
            out += [(v, "Scope de npm") for v in _org_tokens(scope)]
            out += [(v, "Autor en package.json") for v in _authors(data.get("author"))]
        elif name == "composer.json":
            data = json.loads(content)
            vendor = str(data.get("name") or "").split("/")[0]
            out += [(v, "Vendor de composer") for v in _org_tokens(vendor)]
            out += [
                (v, "Autor en composer.json") for v in _authors(data.get("authors"))
            ]
        elif name == "go.mod":
            m = re.search(r"^module\s+(\S+)", content, re.M)
            if m:
                parts = m.group(1).split("/")
                org = parts[1] if len(parts) >= 3 and "." in parts[0] else ""
                out += [(v, "Módulo Go") for v in _org_tokens(org)]
        elif name == "pom.xml":
            body = re.sub(
                r"<(parent|dependencies|dependencyManagement|build|plugins)>.*?</\1>",
                "",
                content,
                flags=re.S,
            )
            m = re.search(r"<groupId>\s*([\w.-]+)\s*</groupId>", body)
            if m:
                labels = m.group(1).split(".")
                org = labels[1] if len(labels) >= 2 else labels[0]
                out += [(v, "groupId de Maven") for v in _org_tokens(org)]
        elif name == "pyproject.toml":
            for m in re.finditer(r"\{\s*name\s*=\s*\"([^\"]+)\"", content):
                out += [(v, "Autor en pyproject") for v in _authors(m.group(1))]
            for m in re.finditer(r"^authors\s*=\s*\[([^\]]*)\]", content, re.M):
                items = re.sub(r"\{[^}]*\}", "", m.group(1))
                for a in re.findall(r"\"([^\"]+)\"", items):
                    out += [(v, "Autor en pyproject") for v in _authors(a)]
    except (ValueError, AttributeError):
        return []
    seen: set[str] = set()
    return [(v, r) for v, r in out if not (v in seen or seen.add(v))]


MANIFESTS = ("package.json", "composer.json", "go.mod", "pom.xml", "pyproject.toml")


def git_author_domains(repo: Path, limit: int = 2000) -> list[str]:
    """Dominios corporativos de los autores y committers de ``git log``."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"-n{limit}", "--format=%ae%n%ce"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    domains: list[str] = []
    for email in set((out.stdout or "").split()):
        domain = email.rpartition("@")[2].lower()
        if not domain or domain in PUBLIC_EMAIL_DOMAINS:
            continue
        value = domain_value(domain)
        if value and value not in domains:
            domains.append(value)
    return sorted(domains)


# --- Agregación ----------------------------------------------------------------


def aggregate(
    hits: list[RawHit], is_protected: Callable[[str], bool]
) -> tuple[list[RawHit], Counter, int]:
    """Una entrada por (valor, categoría): la primera aparición y el total.

    Las claves de incidencias necesitan ``ISSUE_KEY_MIN`` apariciones. Lo ya
    protegido en config.json no se devuelve: solo se cuenta.
    """
    first: dict[tuple[str, str], RawHit] = {}
    counts: Counter = Counter()
    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    for h in hits:
        key = (h.value, h.category)
        counts[key] += 1
        prev = first.get(key)
        if prev is None or rank[h.confidence] < rank[prev.confidence]:
            first[key] = h if prev is None else _upgrade(prev, h)
    kept: list[RawHit] = []
    protected = 0
    for key, h in first.items():
        if h.category == "issue-key" and counts[key] < ISSUE_KEY_MIN:
            continue
        if is_protected(h.value):
            protected += 1
            continue
        kept.append(h)
    return kept, counts, protected


def _upgrade(prev: RawHit, better: RawHit) -> RawHit:
    """Conserva la primera ubicación con la confianza más alta."""
    return RawHit(
        prev.value,
        prev.category,
        better.confidence,
        prev.path,
        prev.line,
        better.reason,
    )
