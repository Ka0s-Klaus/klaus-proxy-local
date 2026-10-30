#!/usr/bin/env bash
# Klaus Proxy Local — Bootstrap installer
# Comprueba prerequisitos, instala dependencias y configura el sistema.
#
# Uso:
#   ./install.sh          # Instalación completa
#   ./install.sh --check  # Solo verificar prerequisitos, sin instalar

set -euo pipefail

# ── Constantes ────────────────────────────────────────────────────────────────
# Igual que requires-python de pyproject.toml (CI prueba 3.10–3.13) (#101).
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=10
MIN_VERSION="${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}"
# Versión que se instala con Homebrew en macOS si no hay ninguna válida.
BREW_PYTHON_VERSION="3.13"

VENV_DIR="${HOME}/.local/share/klaus/venv"
BIN_DIR="${HOME}/.local/bin"
ENTRY_POINTS=("claude-proxy" "Klaus-proxy" "klaus-scan" "klaus-setup" "klaus-audit-payloads" "klaus-fix-pseudonymization" "klaus-audit-dashboard" "klaus-prune-captures")

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=true
fi

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

ok()   { echo -e "  ${GREEN}✅${NC}  $*"; }
fail() { echo -e "  ${RED}❌${NC}  $*"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}⚠️${NC}   $*"; WARNINGS=$((WARNINGS + 1)); }
info() { echo -e "  ${BLUE}ℹ️${NC}   $*"; }
step() { echo -e "\n${BOLD}$*${NC}"; }

# ── Utilidades ────────────────────────────────────────────────────────────────

version_ge() {
    # Comprueba que la versión $1 >= $2 (formato major.minor)
    local actual_major actual_minor req_major req_minor
    IFS='.' read -r actual_major actual_minor <<< "$1"
    IFS='.' read -r req_major req_minor <<< "$2"
    [[ "$actual_major" -gt "$req_major" ]] || \
        { [[ "$actual_major" -eq "$req_major" ]] && [[ "$actual_minor" -ge "$req_minor" ]]; }
}

find_python() {
    # Devuelve el path del primer Python que cumpla la versión mínima
    local candidates=("python3.13" "python3.12" "python3.11" "python3.10" "python3" "python")
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" &>/dev/null; then
            local ver
            ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
            if [[ -n "$ver" ]] && version_ge "$ver" "${MIN_VERSION}"; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

install_homebrew() {
    step "📦 Instalando Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Añadir brew al PATH de la sesión actual
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f "/usr/local/bin/brew" ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
}

install_python_macos() {
    step "🐍 Instalando Python ${BREW_PYTHON_VERSION} via Homebrew..."
    brew install "python@${BREW_PYTHON_VERSION}"
    # Hacer disponible en PATH de la sesión actual
    local brew_prefix
    brew_prefix="$(brew --prefix)"
    export PATH="${brew_prefix}/opt/python@${BREW_PYTHON_VERSION}/bin:${PATH}"
}

# ── Comprobaciones de prerequisitos ──────────────────────────────────────────

check_os() {
    step "🖥️  Sistema operativo"
    local os
    os="$(uname -s)"
    case "$os" in
        Darwin)
            ok "macOS detectado ($(sw_vers -productVersion))"
            ;;
        Linux)
            ok "Linux detectado"
            ;;
        *)
            fail "Sistema operativo no soportado: $os"
            ;;
    esac
}

check_brew() {
    step "🍺 Homebrew"
    if command -v brew &>/dev/null; then
        local ver
        ver="$(brew --version | head -1)"
        ok "Homebrew disponible: $ver"
        return 0
    fi

    warn "Homebrew no encontrado"
    if [[ "$CHECK_ONLY" == true ]]; then
        info "Instalar con: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        return 0
    fi

    echo ""
    read -r -p "  ¿Instalar Homebrew ahora? [s/N] " ans
    if [[ "$ans" =~ ^[sS]$ ]]; then
        install_homebrew
        ok "Homebrew instalado"
    else
        fail "Homebrew es necesario para instalar Python en macOS"
    fi
}

FOUND_PYTHON=""   # Resultado de check_python, para evitar subshell

check_python() {
    step "🐍 Python ≥${MIN_VERSION}"
    local python_bin
    if python_bin=$(find_python 2>/dev/null); then
        local ver
        ver=$("$python_bin" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
        ok "Python ${ver} encontrado en: $(command -v "$python_bin")"
        FOUND_PYTHON="$python_bin"
        return 0
    fi

    warn "Python ≥${MIN_VERSION} no encontrado"
    if [[ "$CHECK_ONLY" == true ]]; then
        if [[ "$(uname -s)" == "Darwin" ]]; then
            info "Instalar con: brew install python@${BREW_PYTHON_VERSION}"
        else
            info "Instalar con el gestor de paquetes (p. ej. sudo apt install python3 python3-venv)"
        fi
        fail "Python ≥${MIN_VERSION} requerido"
        return 1
    fi

    local os
    os="$(uname -s)"
    if [[ "$os" == "Darwin" ]]; then
        if ! command -v brew &>/dev/null; then
            fail "Homebrew no disponible — instálalo primero"
            return 1
        fi
        echo ""
        read -r -p "  ¿Instalar Python ${BREW_PYTHON_VERSION} via Homebrew? [s/N] " ans
        if [[ "$ans" =~ ^[sS]$ ]]; then
            install_python_macos
            python_bin=$(find_python) || { fail "Python no encontrado tras instalación"; return 1; }
            local ver
            ver=$("$python_bin" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
            ok "Python ${ver} instalado"
            FOUND_PYTHON="$python_bin"
            return 0
        fi
    fi

    if [[ "$os" == "Linux" ]]; then
        info "Debian/Ubuntu: sudo apt install python3 python3-venv · Fedora/RHEL: sudo dnf install python3"
    fi
    fail "Python ≥${MIN_VERSION} requerido. Instálalo manualmente."
    return 1
}

check_git() {
    step "🔧 Git"
    if command -v git &>/dev/null; then
        ok "git $(git --version | awk '{print $3}')"
    else
        warn "git no encontrado (recomendado pero no obligatorio)"
    fi
}

check_curl() {
    step "🌐 curl"
    if command -v curl &>/dev/null; then
        ok "curl disponible"
    else
        fail "curl no encontrado — necesario para descargar dependencias"
    fi
}

# ── Instalación ───────────────────────────────────────────────────────────────

create_venv() {
    local python_bin="$1"
    step "🏗️  Entorno virtual: ${VENV_DIR}"

    if [[ -d "${VENV_DIR}" ]]; then
        # Verificar que el venv existente tiene la versión correcta
        local venv_python="${VENV_DIR}/bin/python"
        if [[ -x "$venv_python" ]]; then
            local venv_ver
            venv_ver=$("$venv_python" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            if version_ge "$venv_ver" "${MIN_VERSION}"; then
                ok "Venv existente con Python ${venv_ver} — reutilizando"
                return 0
            else
                warn "Venv existente tiene Python ${venv_ver} < ${MIN_VERSION}, recreando..."
                rm -rf "${VENV_DIR}"
            fi
        fi
    fi

    mkdir -p "$(dirname "${VENV_DIR}")"
    if ! "$python_bin" -m venv "${VENV_DIR}" >/dev/null 2>&1; then
        rm -rf "${VENV_DIR}"
        local pyver
        pyver=$("$python_bin" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        fail "No se pudo crear el venv con ${python_bin} (falta el módulo venv/ensurepip)"
        info "Debian/Ubuntu: sudo apt install python${pyver}-venv   (o python3-venv)"
        exit 1
    fi
    ok "Venv creado en ${VENV_DIR}"
}

install_package() {
    local project_dir="$1"
    step "📦 Instalando Klaus Proxy Local"

    local pip="${VENV_DIR}/bin/pip"

    # Actualizar pip silenciosamente
    "$pip" install --upgrade pip --quiet

    "$pip" install -e "${project_dir}" --quiet
    ok "Klaus Proxy Local instalado (editable)"

    # Verificar que los entry points están disponibles
    local missing=()
    for ep in "${ENTRY_POINTS[@]}"; do
        if [[ ! -x "${VENV_DIR}/bin/${ep}" ]]; then
            missing+=("$ep")
        fi
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        ok "Entry points disponibles: ${ENTRY_POINTS[*]}"
    else
        fail "Entry points no encontrados: ${missing[*]}"
    fi
}

check_mitmproxy() {
    step "🔀 mitmproxy"
    local mitmdump="${VENV_DIR}/bin/mitmdump"
    if [[ -x "$mitmdump" ]]; then
        local ver
        ver=$("$mitmdump" --version 2>&1 | head -1 | awk '{print $2}' || echo "desconocida")
        ok "mitmdump ${ver} disponible en el venv"
    else
        fail "mitmdump no encontrado en el venv — verifica la instalación del paquete"
    fi
}

link_entry_points() {
    step "🔗 Registrando comandos en ${BIN_DIR}"
    mkdir -p "${BIN_DIR}"

    for ep in "${ENTRY_POINTS[@]}"; do
        local src="${VENV_DIR}/bin/${ep}"
        local dst="${BIN_DIR}/${ep}"
        if [[ -x "$src" ]]; then
            ln -sf "$src" "$dst"
            ok "Enlazado: ${ep} → ${dst}"
        else
            warn "Entry point no encontrado, omitiendo: ${ep}"
        fi
    done
}

link_wrapper() {
    # claude-with-proxy: claude por el proxy, fail-closed (#105)
    local src="$1/scripts/claude-with-proxy.sh"
    if [[ -x "$src" ]]; then
        ln -sf "$src" "${BIN_DIR}/claude-with-proxy"
        ok "Enlazado: claude-with-proxy → ${BIN_DIR}/claude-with-proxy"
    else
        warn "No se encontró ${src}"
    fi
}

check_path() {
    step "🛣️  PATH"
    if [[ ":${PATH}:" == *":${BIN_DIR}:"* ]]; then
        ok "${BIN_DIR} está en PATH"
    else
        warn "${BIN_DIR} NO está en PATH"
        info "Añade esta línea a tu ~/.zshrc o ~/.bashrc:"
        info "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    fi
}

run_first_setup() {
    step "⚙️  Configuración inicial (config + certificados)"
    local python="${VENV_DIR}/bin/python"

    # Ejecutar setup de config (genera ~/.klaus-proxy/config.json si no existe)
    "$python" -c "
from Klaus_proxy_local.setup import init_config_if_missing
init_config_if_missing()
" 2>&1 | sed 's/^/    /'

    # Generar certificados mitmproxy si no existen
    "$python" -c "
from Klaus_proxy_local.certs import ensure_mitmproxy_certs, generate_env_vars_file
cert = ensure_mitmproxy_certs()
generate_env_vars_file(cert)
" 2>&1 | sed 's/^/    /'

    ok "Config y certificados listos"
}

verify_installation() {
    step "🧪 Verificación final"
    local python="${VENV_DIR}/bin/python"
    local bin_proxy="${BIN_DIR}/claude-proxy"

    # Verificar importación del paquete
    if "$python" -c "import Klaus_proxy_local; print(Klaus_proxy_local.__version__)" &>/dev/null; then
        local ver
        ver=$("$python" -c "import Klaus_proxy_local; print(Klaus_proxy_local.__version__)")
        ok "Klaus Proxy Local v${ver} importa correctamente"
    else
        fail "El paquete no importa correctamente"
    fi

    # Verificar entry point principal
    if [[ -x "$bin_proxy" ]]; then
        local version_out
        version_out=$("$bin_proxy" --version 2>&1 || true)
        ok "claude-proxy responde: ${version_out}"
    else
        fail "claude-proxy no encontrado en ${BIN_DIR}"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    local project_dir
    project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║     🔐 Klaus Proxy Local — Instalador                ║${NC}"
    if [[ "$CHECK_ONLY" == true ]]; then
    echo -e "${BOLD}║     Modo: solo verificación                          ║${NC}"
    fi
    echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ── Fase 1: Prerequisitos ─────────────────────────────────────────────────
    echo -e "${BOLD}── FASE 1: Prerequisitos ────────────────────────────────${NC}"
    check_os
    check_curl

    local os
    os="$(uname -s)"
    if [[ "$os" == "Darwin" ]]; then
        check_brew
    fi

    check_python || {
        echo ""
        echo -e "${RED}❌ No se puede continuar sin Python ≥${MIN_VERSION}${NC}"
        exit 1
    }
    check_git

    if [[ "$CHECK_ONLY" == true ]]; then
        echo ""
        echo -e "${BOLD}── RESULTADO DE VERIFICACIÓN ────────────────────────────${NC}"
        if [[ $ERRORS -eq 0 ]]; then
            echo -e "  ${GREEN}✅ Todos los prerequisitos satisfechos${NC}"
            echo -e "  Ejecuta ${BOLD}./install.sh${NC} para instalar."
        else
            echo -e "  ${RED}❌ ${ERRORS} problema(s) encontrado(s)${NC}"
            echo -e "  Corrige los errores antes de instalar."
        fi
        if [[ $WARNINGS -gt 0 ]]; then
            echo -e "  ${YELLOW}⚠️  ${WARNINGS} aviso(s)${NC}"
        fi
        echo ""
        exit $((ERRORS > 0 ? 1 : 0))
    fi

    if [[ $ERRORS -gt 0 ]]; then
        echo ""
        echo -e "${RED}❌ ${ERRORS} prerequisito(s) no satisfecho(s). Corrígelos antes de instalar.${NC}"
        exit 1
    fi

    # ── Fase 2: Instalación ───────────────────────────────────────────────────
    echo -e "\n${BOLD}── FASE 2: Instalación ──────────────────────────────────${NC}"
    create_venv "$FOUND_PYTHON"
    install_package "$project_dir"
    check_mitmproxy
    link_entry_points
    link_wrapper "$project_dir"

    # ── Fase 3: Configuración ─────────────────────────────────────────────────
    echo -e "\n${BOLD}── FASE 3: Configuración ────────────────────────────────${NC}"
    run_first_setup
    check_path

    # ── Verificación final ────────────────────────────────────────────────────
    echo -e "\n${BOLD}── VERIFICACIÓN FINAL ───────────────────────────────────${NC}"
    verify_installation

    # ── Resumen ───────────────────────────────────────────────────────────────
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
    if [[ $ERRORS -eq 0 ]]; then
    echo -e "${BOLD}║  ${GREEN}✅ Instalación completada${NC}${BOLD}                          ║${NC}"
    else
    echo -e "${BOLD}║  ${RED}❌ Instalación con ${ERRORS} error(es)${NC}${BOLD}                  ║${NC}"
    fi
    echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Entorno:${NC}  ${VENV_DIR}"
    echo -e "  ${BOLD}Comandos:${NC} ${BIN_DIR}/claude-proxy"
    echo ""
    echo -e "  ${BOLD}Próximos pasos:${NC}"

    if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
    echo -e "  1. Añade ~/.local/bin a tu PATH:"
    echo -e "       echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
    echo ""
    fi

    echo -e "  2. En una terminal, arranca el proxy:"
    echo -e "       ${BOLD}claude-proxy${NC}"
    echo ""
    echo -e "  3. En otra terminal, usa Claude con el proxy:"
    echo -e "       source ~/.klaus-proxy/klaus-env.sh"
    echo -e "       export HTTPS_PROXY=http://127.0.0.1:8899"
    echo -e "       claude 'tu pregunta'"
    echo ""

    exit $((ERRORS > 0 ? 1 : 0))
}

main "$@"
