#!/usr/bin/env bash
# 🔐 Claude Code a través de Klaus Proxy Local (bash/zsh)
#
# Uso:
#   claude-with-proxy [argumentos de claude…]
#
# Carga la confianza en la CA del proxy, comprueba que claude-proxy escucha y
# lanza claude con HTTPS_PROXY. Fail-closed: si el proxy no está en marcha, no
# ejecuta claude (#105). install.sh lo enlaza en ~/.local/bin.

set -euo pipefail

PROXY_HOST="127.0.0.1"
PROXY_PORT="8899"
ENV_FILE="${HOME}/.klaus-proxy/klaus-env.sh"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ Falta $ENV_FILE: arranca claude-proxy una vez (o ejecuta ./install.sh)." >&2
    exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

if ! (exec 3<>"/dev/tcp/${PROXY_HOST}/${PROXY_PORT}") 2>/dev/null; then
    echo "❌ Klaus Proxy no está escuchando en ${PROXY_HOST}:${PROXY_PORT}." >&2
    echo "   Arráncalo en otra terminal, desde dentro de tu repo:  claude-proxy" >&2
    exit 1
fi

export HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
export NO_PROXY="localhost,${PROXY_HOST},::1"
exec claude "$@"
