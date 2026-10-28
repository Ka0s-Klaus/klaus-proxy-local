# Changelog

All notable changes to Klaus Proxy Local are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Logs del proxy en disco** (#55) — Nuevo addon `src/klaus_file_log.py`, cargado por `claude-proxy`, que guarda en `~/.klaus-proxy/logs/proxy.log` los logs de mitmproxy y de los addons, más una línea por petición (método, host+ruta sin query, status, bytes, duración). Rotación 5 MB × 5, sin ANSI, permisos `0600`. Directorio configurable con `KLAUS_LOG_DIR`. La terminal no cambia.

- **Org/repo aprendidos de cada petición** (#63) — El pseudonimizador lee los remotes de git que Claude Code envía en `safeguards[].classifier_context.git_state`, protege su org/repo antes de reescribir esa misma petición y los guarda en `pseudo_word_literals` (escritura atómica). Cubre proyectos desde los que nunca se arrancó `claude-proxy`. Los nombres genéricos (`docs`, `api`…) no se aprenden y se avisa en el log. Best-effort: el campo es interno y solo está verificado en modo `auto`.

### Fixed
- **Claude Code fallaba con `UNABLE_TO_VERIFY_LEAF_SIGNATURE`** (#51) — `klaus-env.sh` dejaba `NODE_EXTRA_CA_CERTS` comentado y el launcher solo lo ponía en el entorno de `mitmdump`, no en el del cliente. Ahora `klaus-env.sh` lo exporta. Se elimina `NODE_TLS_REJECT_UNAUTHORIZED=0`, que no tenía efecto.
- **Ctrl+C dejaba `claude-proxy` colgado** (#51) — El handler de señales esperaba al hijo mientras el hilo principal ya estaba en `Popen.wait()` con su lock no reentrante (interbloqueo en Python 3.15). Además, un SIGTERM durante el arranque dejaba `mitmdump` huérfano. El apagado se hace ahora fuera del handler y SIGTERM se captura desde el inicio.
- **`klaus-env.sh` rompía HTTPS fuera del proxy** (#53) — `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `REQUESTS_CA_BUNDLE` y `GIT_SSL_CAINFO` apuntaban solo a la CA de mitmproxy y sustituían el almacén de CAs (Python/`httpx`/OpenSSL fallaban con cualquier web que no pasase por el proxy; también curl/git en Linux). Ahora apuntan a `~/.klaus-proxy/ca-bundle.pem` (CAs del sistema + CA del proxy), que se regenera en cada arranque.
- **El detector de IPv4 pseudonimizaba la versión de Claude Code** (#57) — `_IPV4_RE` aceptaba cualquier grupo de 1–3 dígitos, así que `cc_version=2.1.312.625` en la cabecera de facturación del `system` salía como `ip_…`. Ahora cada octeto debe estar en 0–255, la secuencia no puede formar parte de una más larga y se ignora lo que va tras `version=`/`version:`.
- **`anthropic-pair-verify` daba falsos positivos de IPv4/email** (#59) — Aplicaba los regex al JSON serializado (un `\n` antes de un decorador parecía un email) y daba por fuga cualquier aparición del valor en el `sent`, aunque estuviera en un contexto que no es IP (`1.2.3.4.5`, `cc_version=`). Ahora los regex se aplican al texto decodificado y email/IPv4 solo son fuga si vuelven a encajar con el regex en el `sent`. Las entradas `ip_`/`email_` del vault se comprueban con esa misma capa.
- **Los nombres de repo con puntos no se protegían** (#65) — `_parse_remote_tokens()` descartaba cualquier token con `.` para no tomar el host, y con él los repos con forma de dominio (`user.github.io`, `site.example.dev`), que salían en claro. Ahora el host se quita por posición (tras el esquema o antes de `:` en la forma scp) y se aceptan los puntos. Afecta a la detección por cwd, a `remember_repo_tokens()` (#61) y al aprendizaje por petición (#63). De paso, el puerto de `ssh://host:2222/…` ya no se devuelve como token.
- **La protección de org/repo dependía del directorio de arranque** (#61) — El pseudonimizador solo detectaba org/repo con el `git remote` del directorio de trabajo de `mitmdump`, que hereda el de quien lanza `claude-proxy`. Arrancarlo fuera del repo dejaba el nombre del repo en claro (p. ej. en las rutas de memoria codificadas de Claude Code). Ahora `claude-proxy` guarda org/repo en `pseudo_word_literals` de `config.json` y el dashboard muestra la lista protegida o avisa si está vacía.
- Los tests de `ensure_prerequisites()` reescribían el `~/.klaus-proxy/klaus-env.sh` real del usuario (#53).

---

## [0.4.0] — 2026-10-28

### Added
- **Instalador bootstrap `install.sh`** (#31, #33) — Instalación en 3 fases (prerequisitos → venv global en `~/.local/share/klaus/venv` → configuración) con modo `--check`. Enlaza los comandos en `~/.local/bin`.
- **Dashboard HTML de auditoría** (#34, #35) — `klaus-audit-dashboard --open` con 5 planes: seguridad, pseudonimización, actividad, tests y EFDEF.
- **Detección por ruta** (#39, #41) — Cualquier petición a `/v1/messages*` se pseudonimiza aunque el host no esté configurado, con aviso para añadirlo a `config.json`.
- **Flag `pseudo_ran`** (#38, #41) — Distingue "el pseudonimizador no corrió" (exposición real) de "corrió pero no había nada que sustituir". El dashboard mide % de peticiones procesadas, con umbral ≥ 99 %.
- Python 3.10 en la matriz de CI (#45).

### Fixed
- **Seguridad: el proxy escuchaba en todas las interfaces** (#47) — `mitmdump` se lanzaba sin `--listen-host` (`*:8899`), lo que lo convertía en un proxy abierto para la LAN. Ahora solo escucha en `127.0.0.1`.
- **`install.sh` fallaba en equipos limpios** (#43) — `mitmproxy`/`mitmdump` se buscaban en el PATH en lugar de en el venv, y la CA se generaba con la consola interactiva `mitmproxy`, que falla sin TTY. Ahora se resuelven desde el venv y la CA se genera con `mitmdump` sin interfaz.
- **`klaus-audit-dashboard` no se enlazaba** en `~/.local/bin` (#43).
- **`pseudo_literals` se perdían al reiniciar** (#28, #29) — Ahora persisten en `~/.klaus-proxy/config.json`.
- **Placeholder `customer1.es` hardcodeado** (#36, #37) — Los hosts se leen de `config.json` (prioridad: env → config → `api.anthropic.com`).
- **CodeQL #58** (#45) — Comparación de hosts por igualdad / etiquetas DNS en lugar de subcadenas en `klaus-fix-pseudonymization`.
- **CI bloqueado** (#45) — El job Lint fallaba en `main` y `Test` nunca se ejecutaba; deuda de ruff/black saneada.

### Changed
- `requires-python >= 3.10` y sin límite superior de `mitmproxy` (#33). Verificado con mitmproxy 12.3.1.
- Documentación de instalación: el paquete no está en PyPI; se instala con `git clone` + `./install.sh` (#49).

---

## [0.3.3] — 2026-09-20

### Fixed
- **Progress feedback for large directory scans** — Added "Indexing files..." visual feedback during file traversal to prevent appearing frozen when scanning large directories like `/Users/usuario`
- **Documentation version consistency** — Synchronized version references across all modules (README, docstrings, install commands)
- **Test version assertions** — Updated tests to assert correct version (0.3.3)
- **Invalid ruff version constraint** — Changed from non-existent 0.16.5 to valid 0.8.0+
- **Broken shell scripts** — Removed references to non-existent `dashboard_server` module from start.sh and run_all.sh
- **Vault filename documentation** — Corrected vault file name from `.vault.json` to `.pseudonym_vault.json`
- **Outdated docstrings** — Updated module docstrings with current version and removed non-existent CLI flags

### Deprecated
- **Klaus Monitor (claude-proxy-monitor)** — Removed in v0.3.3; use `klaus-audit-payloads` for auditing instead

---

## [0.3.2] — 2026-09-19

### Added
- Klaus Menu v0.3.2 enhancements
- Python3 compatibility improvements
- Improved CLI feedback and user experience

### Fixed
- Python command path issues in Klaus Menu
- Shell expansion handling with `set -u`

---

## [0.3.1] — 2026-09-15

### Added
- `klaus-audit-payloads` CLI for comprehensive payload auditing
- `klaus-fix-pseudonymization` CLI for diagnosing and fixing pseudonymization issues
- Multi-mode audit system (summary, detailed, CSV export)
- SSL/TLS truststore auto-generation (GIT_SSL_CAINFO, CURL_CA_BUNDLE)

### Fixed
- Truststore handshake errors
- Pseudonymization consistency issues

---

## [0.3.0] — 2026-09-04

### Added
- **Three-tier sensitive data detection** (v0.2.0+):
  - Tier 1: Pattern-based detection (20+ regex patterns for common secrets)
  - Tier 2: Contextual detection (variable names, JSON keys, file types)
  - Tier 3: Heuristic detection (entropy analysis, character diversity)
- **Custom pattern support** — Users can add their own detection patterns
- **Vault integration** — Persistent pseudonym mapping with bidirectional reversal
- **Comprehensive testing** — 465 unit and integration tests covering all detection tiers
- **Klaus Menu** — Interactive bash menu for scan, audit, and fix operations
- **Production-ready deployment** — CI/CD validation, security scanning, code quality checks

### Fixed
- SALT generation hardening
- File permission security (vault: 0o600, parent: 0o700)
- Unreversible pseudonym detection
- Zero-configuration setup (certs, config, shell hooks auto-generated)

---

## [0.2.0] — 2026-08-15

### Added
- Multi-tier sensitive data scanner architecture
- Pattern-based secret detection
- Contextual analysis layer
- Heuristic entropy-based detection
- Project-wide secret scanning (`klaus-scan` CLI)

### Fixed
- Detection accuracy across multiple secret types
- False positive reduction through multi-tier validation

---

## [0.1.0] — 2026-07-30

### Added
- Initial release: Klaus Proxy Local
- mitmproxy-based HTTPS interception
- Basic payload capture and pseudonymization
- Zero-config setup (automatic cert and config generation)
- Fail-closed guarantee (proxy must run for requests to leave machine)
- Wrapper scripts for multiple shells (bash, zsh, fish, PowerShell)
- Core addons:
  - `anthropic_payload_capture.py` — Capture original/sent pairs
  - `anthropic_payload_pseudonymize.py` — Rewrite/restore payloads
  - `anthropic_capture_verify.py` — Verify captured data integrity
  - `anthropic_pair_verify.py` — Pair-level diff verification
  - `anthropic_artifacts_cleanup.py` — Clean Claude Code disk artifacts
- Installation helpers for Python, wrapper scripts, and shell integration
- Production-ready launcher with mitmproxy orchestration

---

## Links to Detailed Release Notes

- [v0.3.3 Release Notes](./docs/RELEASE_v0.3.3_NOTES.md) (if available)
- [v0.3.2 Release Notes](./docs/RELEASE_v0.3.2_NOTES.md)
- [v0.3.1 Release Notes](./docs/RELEASE_v0.3.1_NOTES.md)
- [v0.3.0 Release Notes](./docs/RELEASE_v0.3.0_NOTES.md)
