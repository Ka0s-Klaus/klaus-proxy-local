# Changelog

All notable changes to Klaus Proxy Local are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **`klaus-scan` detecta nombres de negocio** (#140) — Busca razones sociales con forma jurídica, titulares de copyright, dominios corporativos de email, URL y `git log` (también el *tenant* de un SaaS), IDs de proyecto cloud, la identidad de paquete en los manifiestos y las claves de incidencias. Cada valor aparece una vez, con sus apariciones. Lo ya protegido en `config.json` solo se cuenta. Activado por defecto (`--no-business`) y umbral por defecto HIGH. Opción nueva `--counts` para obtener solo recuentos.

### Security
- **Un valor protegido tras una secuencia de escape salía en claro** (#142) — En `re.compile(r"\bcliente-x")`, `\ncliente-x` o `\tcliente-x`, la letra del escape iba pegada al valor y la frontera de palabra de `pseudo_word_literals` no casaba. Ahora un escape (`\` + letra) cuenta como frontera por la izquierda, también en los nombres de carpeta sueltos (#93) y en el verificador por pares. En la instalación del autor, un nombre de organización protegido había salido así en 107 peticiones.
- **La salida de `klaus-scan` ya no revela los valores** (#140) — Antes mostraba 8 caracteres de cada valor y el contexto en claro, y la revisión, `--json` y «copiar» sin `pbcopy` mostraban el valor completo. Si lo lanzaba Claude Code, todo entraba en el contexto del modelo. Ahora cada valor es un identificador `⟨categoría·hash·longitud⟩`, sin contexto y con rutas relativas enmascaradas; `--reveal` lo muestra en claro. Sin TTY ya no falla con `EOFError`: se salta la revisión.

### Fixed
- **`anthropic-pair-verify` contaba como fuga un seudónimo** (#143) — Claude Code solo ve rutas seudonimizadas (`/Users/user_1a2b3c4d/…`). Al citarlas, vuelven en el historial y el patrón de usuarios en rutas las tomaba por un usuario real. Ahora el verificador ignora los valores con forma de seudónimo, con el mismo criterio que el pseudonimizador. En la instalación del autor eran 356 de los 623 pares marcados con fugas.

---

## [0.7.0] — 2026-10-30

### Added
- **Retención de capturas: 30 días por defecto** (#132) — ⚠️ **Al primer arranque tras actualizar se borran los pares `original/` + `sent/` de más de 30 días.** `capture_retention_days` en `config.json` cambia el plazo (`0` = sin límite). No se tocan el vault ni `captures/archive/`. La retención se aplica al arrancar `claude-proxy` o con `klaus-prune-captures [--dry-run] [--days N]`. El dashboard de auditoría muestra la retención activa, la captura más antigua y el último borrado. Motivo: `original/` guarda datos reales en claro y las capturas crecen sin límite (~1,5 MB por petición).
- **Tarjeta «🛡️ Proyectos protegidos» en el dashboard de auditoría** (#136) — Un repo por fila de la carpeta de proyectos, con su estado (protegido, nombre genérico, falta proteger), el seudónimo que ve Anthropic y la última petición en la que apareció. Muestra nombres reales: el informe es local.
- **Protección al arrancar del org/repo de toda la carpeta de proyectos** (#134) — `claude-proxy` recorre `projects_dirs` (por defecto la carpeta padre del repo actual y las de `pseudo_patterns`; hasta 3 niveles) y añade a `pseudo_word_literals` el org/repo de todos los remotes de cada repo git, y a `pseudo_literals` la identidad git propia de un repo. Antes, un repo recién clonado que se listaba desde otro salía en claro. Comando `klaus-scan-repos [--dry-run]` para aplicarlo tras clonar. Solo se muestran recuentos.
- **`capture_originals: false`** (#132) — Solo se guarda `sent/`: sin datos reales en claro en disco (salvo el vault) y la mitad de espacio, a cambio de no poder verificar por pares. El dashboard calcula los planes con `sent/` y `anthropic-pair-verify` explica por qué no hay pares.

### Changed
- **El dashboard de arranque cuenta los org/repo protegidos en vez de listarlos** (#134): los nombres son justo lo que se protege, y esa salida puede acabar en el contexto del modelo.
- **Notas de v0.6.1:** la sección «Hosts no capturados» cubre el `proxy.log` actual más hasta 5 rotaciones de 5 MB, no «5 MB × 5 ficheros» (#138).
- **Documentación de v0.6.0/v0.6.1 completada** (#129) — El README menciona los cinco addons (faltaba `klaus_tls_passthrough`). La guía del dashboard explica las tablas «Hosts capturados» y «Hosts no capturados». El troubleshooting cubre el aviso `config.json ilegible`, la prioridad de `ANTHROPIC_CAPTURE_HOSTS` sobre `hosts` y cómo auditar los conectores MCP con `capture_only_hosts`. El runbook, `AUDIT_ALL_PAYLOADS.md`, `FIX_PSEUDONYMIZATION.md` y la guía de uso explican que las capturas `capture_only` no cuentan como fugas.

---

## [0.6.1] — 2026-10-29

### Added
- **`capture_only_hosts`: auditar sin pseudonimizar** (#125) — Hosts de `config.json` que se descifran y se capturan pero cuya petición sale tal cual, para tráfico que dejaría de funcionar con seudónimos, como los conectores MCP de claude.ai (`mcp-proxy.anthropic.com`). En disco se guardan con los secretos Tier-1 redactados y `"capture_only": true`. `anthropic-pair-verify`, `klaus-audit-payloads` y `klaus-fix-pseudonymization` no los cuentan como fugas ni como «no pseudonimizados», y el dashboard los da por esperados. Si un host está también en `hosts`, se pseudonimiza; una ruta de LLM se pseudonimiza siempre.
- **Sección «Hosts no capturados» en el dashboard** (#123) — En el plan de Seguridad, una tabla con los hosts que pasaron por el proxy sin pseudonimizar ni capturar, según `proxy.log` y sus rotaciones. Muestra, por host, las conexiones en túnel (sin descifrar) y las descifradas que salieron tal cual, con la última vez de cada modo. Así se ve qué tráfico conviene añadir a `hosts`, por ejemplo subdominios de `anthropic.com` o `claude.ai`, que se descifran pero no se pseudonimizan.

### Changed
- **Solo se descifra lo que se audita** (#125) — `klaus_tls_passthrough` descifraba todos los subdominios de `anthropic.com` y `claude.ai`, y algunos (`mcp-proxy.anthropic.com`, `downloads.claude.ai`, `platform.claude.com`) salían descifrados sin pseudonimizar ni capturar. Ahora descifra `api.anthropic.com`, `hosts`, `capture_only_hosts` y el host de `ANTHROPIC_BASE_URL`; el resto, incluida la renovación del token OAuth, va en túnel.

### Fixed
- **La tabla de hosts del dashboard marcaba como inesperados los hosts de `config.json`** (#123) — La tabla «Hosts capturados» del plan de Seguridad tenía fijado `api.anthropic.com` como único host esperado, mientras que el estado del plan usa `hosts` de `config.json`, así que el informe se contradecía (estado correcto y host «Inesperado»). Ahora la tabla marca como inesperados los mismos hosts que el estado.
- **Un `config.json` ilegible desactivaba en silencio las reglas del usuario** (#121) — Si `~/.klaus-proxy/config.json` no se podía leer o no era JSON válido, el pseudonimizador descartaba `pseudo_literals`, `pseudo_word_literals` y `pseudo_patterns` sin dejar rastro. Ahora lo avisa en el log (`config.json ilegible`). El dashboard de auditoría también avisa al leer los hosts esperados. Cierra las alertas de CodeQL `py/empty-except` #62 y #63.
- **La captura ignoraba `hosts` de `config.json`** (#119) — Solo leía `ANTHROPIC_CAPTURE_HOSTS` o una lista fija, así que un host añadido a `hosts` (un gateway LLM, o la telemetría de Claude Code para auditarla) se descifraba y pseudonimizaba pero no dejaba pares `original/` + `sent/`. Ahora usa las mismas fuentes que el pseudonimizador: `ANTHROPIC_CAPTURE_HOSTS` / `ANTHROPIC_PSEUDO_HOSTS`, `hosts` de `config.json` y `api.anthropic.com`. La lista fija ya no incluye el gateway de ejemplo.

---

## [0.6.0] — 2026-10-29

### Added
- **`klaus-setup` envía cada terminal nueva por el proxy** (#105) — El bloque que añade al shell (bash, zsh, fish) carga `klaus-env.sh`, arranca `claude-proxy` en segundo plano con `nohup` si no está en marcha (log en `~/.klaus-proxy/logs/autostart.log`) y ahora **exporta `HTTPS_PROXY`** (y `NO_PROXY` para loopback). Antes no lo exportaba y `claude` no pasaba por el proxy. Funciones `klaus-off`/`klaus-on` para quitarlo o restaurarlo en una terminal. Volver a ejecutar `klaus-setup` sustituye el bloque y el hook antiguo. PowerShell deja de estar soportado (Windows no lo está).
- **Solo se descifra la API del LLM** (#116) — Nuevo addon `klaus_tls_passthrough`: descifra `anthropic.com`, `claude.ai`, los `hosts` de `config.json` y el host de `ANTHROPIC_BASE_URL`; el resto del HTTPS pasa en túnel con su certificado real (sin errores de certificado en pip, git, brew…) y queda registrado como `TÚNEL host:puerto` en `proxy.log`. `"intercept_all": true` en `config.json` o `KLAUS_INTERCEPT_ALL=1` descifran todo, como antes.
- **`claude-with-proxy` funciona tras `install.sh`** (#105) — `install.sh` lo enlaza en `~/.local/bin`. Carga `klaus-env.sh` (antes faltaba `NODE_EXTRA_CA_CERTS` y Claude Code rechazaba el certificado) y se niega a ejecutar `claude` si el proxy no escucha.

### Changed
- **Arquitectura, runbook, guía de uso y descripción del producto documentan el hook y el passthrough TLS** (#115): el addon `klaus_tls_passthrough`, las claves `hosts` e `intercept_all` y la variable `KLAUS_INTERCEPT_ALL`.
- **Documentación revisada contra la funcionalidad real** (#98) — Reescritos el inicio rápido, la guía de uso, el entorno de desarrollo, el troubleshooting, la arquitectura y el diagnóstico de pseudonimización; corregidos el runbook, el README, `PRODUCT_DESCRIPTION.md`, `product.json`, `CONTRIBUTING.md`, `SECURITY.md` y las guías de auditoría y del vault. Fuera: instalación desde PyPI, opciones de `add_to_vault.py` y claves de `config.json` que no existen, la ruta `~/.klaus-proxy/../captures`, el formato antiguo del vault, `~/.klaus-proxy/.salt`, el monitor TUI y las funciones de shell no incluidas. Once documentos que describían versiones pasadas pasan a `docs/archive/`. Se sustituyen dos SALT de ejemplo con forma real.

### Fixed
- **`klaus-fix-pseudonymization` daba diagnósticos falsos** (#110) — Leía claves de `config.json` que el proxy no usa (`patterns`, `pseudonymization_enabled`), por lo que siempre avisaba de que no había patrones, y recomendaba `python -m Klaus_proxy_local.setup`, que no hace nada. Contaba como «no pseudonimizada» cualquier petición que el pseudonimizador procesó sin cambiar nada, y las GET sin cuerpo. Ahora usa `pseudo_ran`, separa las peticiones sin cuerpo, comprueba la SALT, `hosts`, las reglas reales y `ANTHROPIC_PSEUDO_ENABLE`, y solo recomienda comandos que existen.
- **`klaus-fix-pseudonymization --show-config` imprimía la SALT en claro** (#106) — Si lo ejecutaba un agente, la SALT viajaba a la API sin pseudonimizar en el resultado de la herramienta. Ahora se muestra enmascarada. `audit_captures.py --find-leaks` y `generate_audit_report.py` recomendaban `add_to_vault.py --manual`, que no existe; ahora indican cómo añadir los valores a `config.json`.
- **Los valores añadidos solo al vault no se pseudonimizaban** (#99) — `scripts/add_to_vault.py`, `klaus-scan --approve-all` y `auto_add_detected_leaks.py` escribían el valor solo en el vault, pero el proxy solo sustituye lo que casa con una regla: el valor seguía saliendo en claro. Ahora también lo añaden a `config.json` (`pseudo_word_literals` si es un único token, `pseudo_literals` si no) e indican que hay que reiniciar `claude-proxy`. Los tests ya no pueden escribir en el `config.json` real.
- **`install.sh` exigía Python 3.13** (#101) — El paquete declara `requires-python >=3.10` y CI prueba 3.10–3.13, pero el instalador se detenía en Ubuntu 24.04 LTS (3.12), Debian 12 (3.11) o RHEL 9. Ahora acepta ≥ 3.10 y busca primero la versión más nueva; en macOS sigue instalando 3.13 con Homebrew si no hay ninguna. Si falta el módulo `venv` (Debian/Ubuntu sin `python3-venv`), indica el paquete que hay que instalar en vez de fallar a medias. Probado de principio a fin en Ubuntu 24.04.
- **El menú `klaus` fallaba con «No module named Klaus_proxy_local»** (#103) — Usaba el `python3` del sistema, pero `install.sh` instala el paquete en `~/.local/share/klaus/venv`. Ahora usa el Python de ese venv si existe.

### Removed
- **`claude-proxy --monitor`** (#103) — El monitor TUI se eliminó en v0.3.3; la opción solo imprimía un aviso de que faltaba el módulo.

---

## [0.5.2] — 2026-10-29

### Added
- **Nombres de carpeta de proyectos protegidos también fuera de una ruta** (#93) — `pseudo_patterns` solo los sustituía dentro de `/Users/<u>/proyectos/<carpeta>`, así que un `<carpeta>.md` o la raíz de un árbol en un README salían en claro aunque el vault los conociera (detectado vigilando una sesión en otro repo). Ahora los nombres `dir_…` del vault se sustituyen también como palabra completa, con el mismo seudónimo, si tienen 5 caracteres o más y no son genéricos ni están en `pseudo_pattern_ignore`. Cubre también las rutas codificadas con guiones (`-Users-u-proyectos-<carpeta>-…`) de carpetas ya conocidas. `anthropic-pair-verify` los marca como fuga (`[dir]`) si reaparecen como palabra. Se desactiva con `ANTHROPIC_PSEUDO_DIR_WORDS=0`.

### Fixed
- **El patrón de usuarios `/Users/<u>` registraba marcadores y puntuación en el vault** (#92) — Una ruta con el usuario tapado (`…`, `|`, `«X»`, `{user}`) o genérica (`/Users/Shared`) entraba al vault como si fuera un usuario real, se sustituía por un seudónimo y el verificador la tomaba por fuga. Los patrones ignoran ahora los valores sin letras ni números, de un carácter, los marcadores de plantilla y, como usuario, los nombres genéricos; `pseudo_pattern_ignore` en `config.json` excluye valores concretos. `scripts/prune_vault.py` quita del vault los que ya habían entrado (con el proxy parado; copia de seguridad).

---

## [0.5.1] — 2026-10-29

### Changed
- **Avisos de prompt injection detallados y accionables en el audit dashboard** (#86, #88) — Antes solo se mostraba la hora de la captura. Ahora cada aviso indica patrones, origen (mensaje del usuario, resultado de una herramienta con su nombre o `count_tokens`), la fuente del texto (fichero, URL o comando), un fragmento con la coincidencia resaltada, endpoint, fichero de la captura e id. Un mismo texto reenviado en el historial cuenta una vez, con el número de peticiones en que aparece. Debajo, las indicaciones a seguir según sea falso positivo o sospechoso.

### Added
- **`klaus-audit-dashboard --mark-reviewed ID… --note "…"`** (#88) — Guarda los avisos revisados en `audit_injection_reviewed` de `config.json` (escritura atómica, 0600). Dejan de contar para el estado del plan y se muestran plegados con su nota.

### Fixed
- **El repo disparaba su propio detector de injection** (#86) — El código, los tests y la documentación del detector contenían las frases literales, y cada lectura con Claude Code generaba un aviso nuevo. Los patrones usan ahora `\s+` entre palabras y los tests construyen las frases por partes; un test lo comprueba.
- **La fuente de un aviso se cortaba en rutas largas** (#88) — Se conserva el final de la ruta (el fichero); en comandos y URLs, el principio. Encontrado en una prueba controlada con un README con una instrucción oculta.
- **El JSON incrustado en el dashboard escapa `<`** (#86) — Un fragmento con `</script>` cerraba el bloque `<script>` y rompía la página.

---

## [0.5.0] — 2026-10-29

### Added
- **Histórico de informes en el audit dashboard** (#77) — Cada ejecución de `klaus-audit-dashboard` guarda su informe en `informes/` (`audit-<fecha>.json` + `.html`, sin sobrescribir) y regenera `index.js` y `audit-dashboard.html` (el último). En la cabecera, un selector abre cualquier informe anterior, y un panel muestra los cambios respecto al informe previo: estados, métricas ▲/▼, checks EFDEF y hosts inesperados. Funciona con `file://`. El dashboard con datos reales deja de versionarse en `docs/reports/web/`.
- **`pseudo_patterns`: patrones regex en `config.json`** (#42) — Lista de `{pattern, replacement_prefix}` aplicada antes que el resto de reglas, sobre el texto real y de forma reversible; si el regex tiene grupos, solo se pseudonimiza el grupo 1. `claude-proxy` registra al arrancar la carpeta que contiene el repo (p. ej. `~/proyectos`), de modo que los nombres de todos los proyectos se protegen en rutas aunque no tengan remote o vayan truncados. Patrón integrado para el usuario de cualquier ruta `/Users/<u>` o `/home/<u>` (`ANTHROPIC_PSEUDO_USER_DIRS`). `anthropic-pair-verify` añade la capa `[pattern]`, con contexto y en caché.
- **Logs del proxy en disco** (#55) — Nuevo addon `src/klaus_file_log.py`, cargado por `claude-proxy`, que guarda en `~/.klaus-proxy/logs/proxy.log` los logs de mitmproxy y de los addons, más una línea por petición (método, host+ruta sin query, status, bytes, duración). Rotación 5 MB × 5, sin ANSI, permisos `0600`. Directorio configurable con `KLAUS_LOG_DIR`. La terminal no cambia.

- **Org/repo aprendidos de cada petición** (#63) — El pseudonimizador lee los remotes de git que Claude Code envía en `safeguards[].classifier_context.git_state`, protege su org/repo antes de reescribir esa misma petición y los guarda en `pseudo_word_literals` (escritura atómica). Cubre proyectos desde los que nunca se arrancó `claude-proxy`. Los nombres genéricos (`docs`, `api`…) no se aprenden y se avisa en el log. Best-effort: el campo es interno y solo está verificado en modo `auto`.

### Docs
- **Modos de permisos y aprendizaje de org/repo** (#68) — El README documenta en qué modos de permisos envía Claude Code los remotes (`auto` sí; `plan` desde la 2ª petición; `manual`, `acceptEdits` y `dontAsk` no), la limitación de la primera petición y cómo proteger un repo en cualquier modo.

### Performance
- **`anthropic-pair-verify` 7 veces más rápido** (#73) — Con ~920 pares pasa de 71 s a ~9 s con una salida idéntica. Las capas email/IPv4 de #59 aplicaban los regex a cada cadena por separado, cuatro veces por par, y las sesiones largas reenvían el historial: solo el ~2 % de las cadenas son distintas. Ahora hay un prefiltro (`@` para email, `.` para IPv4), una caché por cadena, un solo recorrido por registro y el payload del `sent` se serializa una vez.

### Fixed
- **Audit dashboard: el plan de tests fallaba con «No module named pytest»** (#82) — El venv instalado no trae pytest; ahora se busca un intérprete con pytest (actual, `.venv` del repo o `uv`) y, si no hay, el plan sale ⬜ Sin datos con instrucciones en vez de ⚠️. El timeout sube a 300 s.
- **Claude Code fallaba con `UNABLE_TO_VERIFY_LEAF_SIGNATURE`** (#51) — `klaus-env.sh` dejaba `NODE_EXTRA_CA_CERTS` comentado y el launcher solo lo ponía en el entorno de `mitmdump`, no en el del cliente. Ahora `klaus-env.sh` lo exporta. Se elimina `NODE_TLS_REJECT_UNAUTHORIZED=0`, que no tenía efecto.
- **Ctrl+C dejaba `claude-proxy` colgado** (#51) — El handler de señales esperaba al hijo mientras el hilo principal ya estaba en `Popen.wait()` con su lock no reentrante (interbloqueo en Python 3.15). Además, un SIGTERM durante el arranque dejaba `mitmdump` huérfano. El apagado se hace ahora fuera del handler y SIGTERM se captura desde el inicio.
- **`klaus-env.sh` rompía HTTPS fuera del proxy** (#53) — `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `REQUESTS_CA_BUNDLE` y `GIT_SSL_CAINFO` apuntaban solo a la CA de mitmproxy y sustituían el almacén de CAs (Python/`httpx`/OpenSSL fallaban con cualquier web que no pasase por el proxy; también curl/git en Linux). Ahora apuntan a `~/.klaus-proxy/ca-bundle.pem` (CAs del sistema + CA del proxy), que se regenera en cada arranque.
- **El detector de IPv4 pseudonimizaba la versión de Claude Code** (#57) — `_IPV4_RE` aceptaba cualquier grupo de 1–3 dígitos, así que `cc_version=2.1.312.625` en la cabecera de facturación del `system` salía como `ip_…`. Ahora cada octeto debe estar en 0–255, la secuencia no puede formar parte de una más larga y se ignora lo que va tras `version=`/`version:`.
- **`anthropic-pair-verify` daba falsos positivos de IPv4/email** (#59) — Aplicaba los regex al JSON serializado (un `\n` antes de un decorador parecía un email) y daba por fuga cualquier aparición del valor en el `sent`, aunque estuviera en un contexto que no es IP (`1.2.3.4.5`, `cc_version=`). Ahora los regex se aplican al texto decodificado y email/IPv4 solo son fuga si vuelven a encajar con el regex en el `sent`. Las entradas `ip_`/`email_` del vault se comprueban con esa misma capa.
- **El proxy recargaba en caliente los addons del clon y podía quedarse sin pseudonimizador** (#71) — mitmproxy recarga los scripts `-s` al cambiar en disco y los cargaba desde el clon de trabajo: cada `checkout`/`stash` cambiaba el pseudonimizador en uso y, si la recarga fallaba, el proxy seguía sin él y las peticiones salían en claro (verificado). Ahora `claude-proxy` ejecuta `mitmdump` desde un snapshot inmutable en `~/.klaus-proxy/addons/<hash>/`, y el nuevo addon `klaus_pseudo_guard.py` bloquea (502) cualquier petición que el pseudonimizador no haya procesado. Se muestra el commit de los addons cargados.
- **Los seudónimos partidos entre deltas SSE no se restauraban** (#67) — Las respuestas de `/v1/messages` llegan troceadas en `content_block_delta` y `restore_body()` hacía un `replace` sobre el cuerpo SSE, así que un seudónimo partido entre dos deltas llegaba intacto a Claude Code, que operaba con rutas e IPs inexistentes (`cd /proj_…`, `ENOTFOUND`). Ahora `restore_sse()` concatena cada bloque (`text`, `input_json_delta`, `thinking`), lo restaura completo y lo emite en su primer delta. `_find_unreversed_pseudonyms()` revisa el texto reconstruido y ya detecta seudónimos de ruta (`/proj_…`), que antes nunca reportaba.
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

- [v0.3.2 Release Notes](./docs/RELEASE_v0.3.2_NOTES.md)
- [v0.3.1 Release Notes](./docs/RELEASE_v0.3.1_NOTES.md)
- [v0.3.0 Release Notes](./docs/RELEASE_v0.3.0_NOTES.md)
