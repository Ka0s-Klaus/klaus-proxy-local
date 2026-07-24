#!/usr/bin/env python3
"""Analizador de payloads /v1/messages capturados por el proxy de auditoría.

Dado uno o varios ficheros JSON generados por ``anthropic_payload_capture.py``,
produce un volcado legible con TODO lo que se envía al modelo:

  - system prompt completo (todos los bloques)
  - definición de herramientas (nombres + descripción)
  - historial de mensajes (texto, tool_use, tool_result)
  - MANIFIESTO de ficheros del repo embebidos: qué rutas aparecen y por qué vía
    (system, tool_use input, tool_result), con el nº de bytes de contenido.

Uso:
    python3 src/anthropic_payload_analyze.py captures/<fichero>.json
    python3 src/anthropic_payload_analyze.py --all        # todos los /v1/messages
    python3 src/anthropic_payload_analyze.py --all --dump  # + volcado .md legible
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parents[1]
# Raíz del proyecto AUDITADO para detectar sus rutas en los payloads
# (cwd del proceso, u override). Independiente de dónde viva el tooling.
PROJECT_ROOT = Path(os.environ.get("ANTHROPIC_PSEUDO_PROJECT_ROOT") or Path.cwd())
CAPTURE_DIR = TOOL_ROOT / "captures"

# Detecta rutas absolutas dentro del repo o rutas relativas típicas del proyecto.
_ABS_PATH_RE = re.compile(re.escape(str(PROJECT_ROOT)) + r"/[^\s\"'`)]+")
# Herramientas cuyo input lleva una ruta de fichero.
_FILE_PATH_KEYS = ("file_path", "notebook_path", "path")


def is_messages_payload(record: dict[str, Any]) -> bool:
    """True si el registro es una llamada /v1/messages (inferencia)."""
    p = record.get("payload")
    return isinstance(p, dict) and "messages" in p and "model" in p


def _iter_text(content: Any):
    """Devuelve texto plano de un content block (str o lista de bloques)."""
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    yield block["text"]
                # tool_result anida su contenido
                if "content" in block:
                    yield from _iter_text(block["content"])


def extract_embedded_files(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Localiza ficheros del repo embebidos en el payload.

    Devuelve {ruta: {"vias": set(...), "bytes_contenido": int}}.
    """
    found: dict[str, dict[str, Any]] = {}

    def note(path: str, via: str, content_len: int = 0):
        path = path.strip()
        if not path:
            return
        entry = found.setdefault(path, {"vias": set(), "bytes_contenido": 0})
        entry["vias"].add(via)
        entry["bytes_contenido"] += content_len

    # 1) system prompt: rutas mencionadas (p.ej. CLAUDE.md embebido)
    system = payload.get("system")
    for txt in _iter_text(system):
        for m in _ABS_PATH_RE.findall(txt):
            note(m, "system")
        # CLAUDE.md se embebe por contenido, no siempre por ruta absoluta
        if "CLAUDE.md" in txt and "project instructions" in txt:
            note(str(PROJECT_ROOT / "CLAUDE.md"), "system(contenido)", len(txt))

    # 2) mensajes: tool_use inputs (rutas) y tool_result (contenido de ficheros)
    for msg in payload.get("messages", []):
        content = msg.get("content")
        if not isinstance(content, list):
            # texto suelto: buscar rutas absolutas
            for txt in _iter_text(content):
                for m in _ABS_PATH_RE.findall(txt):
                    note(m, "mensaje-texto")
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use":
                inp = block.get("input", {})
                for key in _FILE_PATH_KEYS:
                    if isinstance(inp.get(key), str):
                        # contenido embebido en Write/Edit
                        clen = 0
                        for ck in ("content", "new_string", "new_source"):
                            if isinstance(inp.get(ck), str):
                                clen += len(inp[ck])
                        note(inp[key], f"tool_use:{block.get('name','?')}", clen)
                # cualquier ruta absoluta que aparezca en el input
                for m in _ABS_PATH_RE.findall(json.dumps(inp, ensure_ascii=False)):
                    note(m, f"tool_use:{block.get('name','?')}")
            elif btype == "tool_result":
                body = "".join(_iter_text(block.get("content")))
                for m in _ABS_PATH_RE.findall(body):
                    note(m, "tool_result", 0)
                # el contenido devuelto (Read) va asociado al tool_use previo;
                # aquí registramos su tamaño global bajo una clave sintética
                if body:
                    note("<tool_result contenido>", "tool_result", len(body))
            elif btype == "text":
                for m in _ABS_PATH_RE.findall(block.get("text", "")):
                    note(m, "mensaje-texto")

    return found


def summarize(record: dict[str, Any]) -> dict[str, Any]:
    """Resumen estructurado de un payload /v1/messages."""
    p = record["payload"]
    system = p.get("system")
    sys_chars = sum(len(t) for t in _iter_text(system))
    tools = p.get("tools", [])
    embedded = extract_embedded_files(p)
    return {
        "host": record.get("host"),
        "model": p.get("model"),
        "max_tokens": p.get("max_tokens"),
        "system_bloques": (
            len(system) if isinstance(system, list) else (1 if system else 0)
        ),
        "system_chars": sys_chars,
        "num_tools": len(tools),
        "tools": [t.get("name") for t in tools],
        "num_messages": len(p.get("messages", [])),
        "ficheros_embebidos": embedded,
    }


def render_dump(record: dict[str, Any]) -> str:
    """Volcado Markdown legible con TODO el contenido enviado."""
    p = record["payload"]
    out: list[str] = []
    out.append(f"# Payload /v1/messages → {record.get('host')}\n")
    out.append(
        f"- **model:** `{p.get('model')}`  ·  **max_tokens:** {p.get('max_tokens')}"
    )
    out.append(f"- **capturado:** {record.get('captured_at')}\n")

    out.append("## System prompt\n")
    system = p.get("system")
    if isinstance(system, list):
        for i, block in enumerate(system):
            out.append(f"### Bloque system[{i}]\n")
            out.append("```\n" + block.get("text", "") + "\n```\n")
    elif isinstance(system, str):
        out.append("```\n" + system + "\n```\n")

    out.append("## Herramientas\n")
    for t in p.get("tools", []):
        desc = (t.get("description", "") or "").strip().splitlines()
        first = desc[0] if desc else ""
        out.append(f"- **{t.get('name')}** — {first}")
    out.append("")

    out.append("## Mensajes\n")
    for i, msg in enumerate(p.get("messages", [])):
        out.append(f"### messages[{i}] · role={msg.get('role')}\n")
        content = msg.get("content")
        if isinstance(content, str):
            out.append("```\n" + content + "\n```\n")
        elif isinstance(content, list):
            for block in content:
                bt = block.get("type") if isinstance(block, dict) else "?"
                if bt == "text":
                    out.append("**[text]**\n```\n" + block.get("text", "") + "\n```\n")
                elif bt == "tool_use":
                    out.append(
                        f"**[tool_use: {block.get('name')}]**\n```json\n"
                        + json.dumps(
                            block.get("input", {}), indent=2, ensure_ascii=False
                        )
                        + "\n```\n"
                    )
                elif bt == "tool_result":
                    body = "".join(_iter_text(block.get("content")))
                    out.append(
                        "**[tool_result]**\n```\n"
                        + body[:5000]
                        + ("\n…(truncado)…" if len(body) > 5000 else "")
                        + "\n```\n"
                    )
    return "\n".join(out)


USAGE = (
    "Uso: anthropic_payload_analyze.py <fichero.json> | --all [--dump]\n"
    "\n"
    "Analiza payloads /v1/messages capturados por el proxy de auditoría.\n"
    "\n"
    "Argumentos:\n"
    "  <fichero.json>   Una o más capturas concretas a analizar.\n"
    "  --all            Analiza todas las capturas de inferencia (captures/sent/,\n"
    "                   con fallback al histórico plano de captures/).\n"
    "  --dump           Además, vuelca un .decoded.md legible junto a cada captura.\n"
    "  -h, --help       Muestra esta ayuda y sale.\n"
)


def main(argv: list[str]) -> int:
    args = argv[1:]

    if "-h" in args or "--help" in args:
        print(USAGE)
        return 0

    dump = "--dump" in args
    args = [a for a in args if a != "--dump"]

    if "--all" in args:
        # Tras el split original/sent, las capturas nuevas viven en sent/ (lo que
        # salió). Fallback al histórico plano en la raíz si sent/ está vacío.
        files = sorted(glob.glob(str(CAPTURE_DIR / "sent" / "*.json"))) or sorted(
            glob.glob(str(CAPTURE_DIR / "*.json"))
        )
    else:
        files = args
    if not files:
        print(USAGE)
        return 1

    for f in files:
        with open(f, encoding="utf-8") as fh:
            record = json.load(fh)
        if not is_messages_payload(record):
            continue
        s = summarize(record)
        print("=" * 78)
        print(f"📄 {os.path.basename(f)}  →  {s['host']}")
        print(
            f"   model={s['model']} max_tokens={s['max_tokens']} "
            f"system={s['system_bloques']} bloques/{s['system_chars']} chars "
            f"tools={s['num_tools']} messages={s['num_messages']}"
        )
        print(f"   🧰 tools: {', '.join(s['tools'])}")
        print(f"   📁 ficheros del repo embebidos ({len(s['ficheros_embebidos'])}):")
        for path, meta in sorted(s["ficheros_embebidos"].items()):
            vias = ", ".join(sorted(meta["vias"]))
            b = meta["bytes_contenido"]
            rel = path.replace(str(PROJECT_ROOT) + "/", "")
            print(f"      - {rel}  [{vias}]" + (f"  ~{b}B contenido" if b else ""))
        if dump:
            dump_path = Path(f).with_suffix(".decoded.md")
            dump_path.write_text(render_dump(record), encoding="utf-8")
            print(f"   📝 volcado legible → {dump_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
