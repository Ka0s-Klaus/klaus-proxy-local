# 🚀 Inicio rápido — Klaus Proxy Local

> Instalar, arrancar el proxy y usar Claude Code a través de él.

**Versión:** v0.8.0 · **Relacionado:** [Guía de uso](./USER_GUIDE.md) · [Runbook técnico](./anthropic-audit-proxy.md) · [Troubleshooting](./TROUBLESHOOTING.md)

---

## 🤔 Qué hace

Klaus Proxy Local se pone entre Claude Code y la API de Anthropic, en tu máquina:

- 🔐 **Pseudonimiza** lo sensible antes de que salga: rutas, usuario, org/repo, nombres de carpetas de proyectos, emails, IPs y los valores que añadas. Los secretos reconocibles se redactan de forma irreversible.
- 🔁 **Restaura** los valores reales en la respuesta, así que Claude Code trabaja con tus rutas de verdad.
- 📋 **Guarda evidencia local** de cada petición: lo que había (`original/`) y lo que salió (`sent/`).
- 🚧 **Fail-closed:** si el pseudonimizador no ha procesado una petición, el guardián la bloquea con un 502 en lugar de dejarla salir.

```
Tu prompt:        "Lee /Users/ana/proyectos/cliente-x/main.py"
Sale a Anthropic: "Lee /Users/user_1a2b3c4d/proyectos/dir_5e6f7a8b/main.py"
Claude Code ve:   "Lee /Users/ana/proyectos/cliente-x/main.py"
```

---

## 📋 Requisitos

- **macOS o Linux.** Windows no está soportado.
- **Python ≥ 3.10.** En macOS, `install.sh` instala Python 3.13 con Homebrew si no hay ninguno válido. En Debian/Ubuntu hace falta `python3-venv`.
- **git.**

El paquete **no está publicado en PyPI**: se instala desde el repositorio.

---

## 1️⃣ Instalar

```bash
git clone https://github.com/Ka0s-Klaus/klaus-proxy-local.git
cd klaus-proxy-local
./install.sh --check   # opcional: solo comprueba los requisitos
./install.sh
```

Crea un venv en `~/.local/share/klaus/venv`, instala mitmproxy, genera `~/.klaus-proxy/config.json` con una SALT aleatoria y el certificado CA del proxy, y enlaza los comandos en `~/.local/bin` (añádelo al `PATH` si el instalador lo avisa).

> ⚠️ La instalación es *editable*: el venv apunta al clon. No borres ni muevas la carpeta. Para actualizar: `git pull && ./install.sh`.

---

## 2️⃣ Arrancar el proxy (terminal 1)

**Desde dentro de un repo:**

```bash
cd ~/proyectos/mi-repo
claude-proxy
```

Escucha solo en `127.0.0.1:8899`. Al arrancar dentro de un repo registra su org/repo y la carpeta de proyectos que lo contiene, para protegerlos. Muestra un resumen de lo protegido y deja el log en `~/.klaus-proxy/logs/proxy.log`. Se para con Ctrl+C.

---

## 3️⃣ Usar Claude Code (terminal 2)

```bash
source ~/.klaus-proxy/klaus-env.sh          # confianza en la CA del proxy
export HTTPS_PROXY=http://127.0.0.1:8899
claude
```

`klaus-env.sh` hace que Claude Code (`NODE_EXTRA_CA_CERTS`) y git/curl/Python confíen en el certificado del proxy sin romper el resto de HTTPS. `HTTPS_PROXY` es lo que envía el tráfico al proxy: solo afecta a esa terminal.

**Atajos:**

- **`claude-with-proxy`** (instalado por `install.sh`): hace el `source` y el `export` por ti, y se niega a lanzar `claude` si el proxy no está escuchando.
- **`klaus-setup`**: añade a tu shell un bloque que, en cada terminal nueva, carga `klaus-env.sh`, arranca `claude-proxy` en segundo plano si no está en marcha y exporta `HTTPS_PROXY`. Así basta con `claude`. **Todo** el HTTPS de la terminal pasa por el proxy (pip, git…) y queda registrado, pero solo se descifra la API del LLM: el resto va en túnel con su certificado real, sin errores de certificado. `klaus-off` / `klaus-on` quitan o restauran el proxy en una terminal. Detalle en el [README](../README.md#setup-options).

---

## 4️⃣ Comprobar qué ha salido

```bash
# Desde el clon del repositorio
python3 src/anthropic_pair_verify.py      # ¿algún valor real en lo enviado?
klaus-audit-dashboard --open              # dashboard con 5 planes de auditoría
```

- `anthropic_pair_verify.py` compara cada `original` con su `sent` y marca lo que haya salido en claro.
- El [audit dashboard](./reports/web/README.md) guarda cada informe en `informes/` y muestra los cambios respecto al anterior.

---

## 📍 Dónde está cada cosa

```
~/.klaus-proxy/
├── config.json              # SALT y reglas (pseudo_literals, pseudo_word_literals, pseudo_patterns…)
├── klaus-env.sh             # variables de confianza en la CA (se regenera al arrancar)
├── ca-bundle.pem            # CAs del sistema + CA del proxy
├── addons/<hash>/           # copia inmutable de los addons que ejecuta el proxy
├── logs/proxy.log           # log rotado (5 MB × 5)
└── captures/
    ├── original/            # lo que había en la petición (datos reales)
    ├── sent/                # lo que salió de tu máquina
    └── .pseudonym_vault.json  # tabla real ↔ seudónimo (0600)
~/.mitmproxy/                # certificado CA del proxy
```

Nada de esto se versiona ni se sincroniza. **No compartas `original/` ni el vault:** contienen tus datos reales.

---

## ❓ Preguntas frecuentes

**¿Y si el proxy se para?** Claude Code no puede conectar (la terminal 2 apunta a un proxy que no responde): no sale nada sin pasar por él. Vuelve a arrancar `claude-proxy`.

**¿Y si cambio el código del repo con el proxy en marcha?** No le afecta: ejecuta una copia inmutable de los addons. Los cambios se aplican al reiniciarlo.

**¿Puedo proteger un valor concreto (un cliente, un proyecto)?** Sí: añádelo a `pseudo_literals` o `pseudo_word_literals` de `config.json`, o usa `python3 scripts/add_to_vault.py`, y reinicia `claude-proxy`. Ver [Añadir valores a proteger](./ADD_TO_VAULT_AUTOMATIC.md).

**¿Varios proyectos?** Sí. El vault es por máquina: un mismo valor tiene siempre el mismo seudónimo.

**¿Funciona en Linux?** Sí: probado en Debian 13 (Python 3.13) y Ubuntu 24.04 (Python 3.12).

**¿He encontrado un fallo de seguridad?** Sigue [SECURITY.md](../SECURITY.md) y no lo publiques hasta que esté corregido.
