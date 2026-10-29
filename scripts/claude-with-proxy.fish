#!/usr/bin/env fish
# 🔐 Claude Code a través de Klaus Proxy Local (fish)
#
# Uso:
#   claude-with-proxy [argumentos de claude…]
#
# Carga la confianza en la CA del proxy, comprueba que claude-proxy escucha y
# lanza claude con HTTPS_PROXY. Fail-closed (#105).

set -l proxy_host "127.0.0.1"
set -l proxy_port "8899"
set -l env_file ~/.klaus-proxy/klaus-env.sh

if not test -f $env_file
    echo "❌ Falta $env_file: arranca claude-proxy una vez (o ejecuta ./install.sh)." >&2
    exit 1
end
source $env_file

if not bash -c "exec 3<>/dev/tcp/$proxy_host/$proxy_port" 2>/dev/null
    echo "❌ Klaus Proxy no está escuchando en $proxy_host:$proxy_port." >&2
    echo "   Arráncalo en otra terminal, desde dentro de tu repo:  claude-proxy" >&2
    exit 1
end

set -x HTTPS_PROXY "http://$proxy_host:$proxy_port"
set -x NO_PROXY "localhost,$proxy_host,::1"
exec claude $argv
