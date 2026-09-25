#!/bin/sh
# Instala los hooks de git sin tocar nada fuera de la carpeta del proyecto:
#   1. gitleaks fijado en .tools/, con el sha256 del release comprobado.
#   2. pre-commit con su caché en .cache/pre-commit.
# Requiere el entorno de .venv (uv sync). Sale con error si algún paso falla.
set -eu

GITLEAKS_VERSION=8.30.1
# gitleaks_8.30.1_checksums.txt del release v8.30.1 en GitHub
GITLEAKS_SHA256_DARWIN_ARM64=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5

root=$(git rev-parse --show-toplevel)
cd "$root"

if [ "$(uname -s)_$(uname -m)" != "Darwin_arm64" ]; then
    echo "error: solo hay binario de gitleaks fijado para macOS arm64, no para $(uname -s) $(uname -m)" >&2
    exit 1
fi

if [ ! -x .venv/bin/pre-commit ]; then
    echo "error: falta .venv/bin/pre-commit. Ejecuta antes: uv sync --locked" >&2
    exit 1
fi

if [ "$(.tools/gitleaks version 2>/dev/null || true)" != "$GITLEAKS_VERSION" ]; then
    tarball="gitleaks_${GITLEAKS_VERSION}_darwin_arm64.tar.gz"
    mkdir -p .tools
    curl -fsSL -o ".tools/$tarball" \
        "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/$tarball"
    echo "$GITLEAKS_SHA256_DARWIN_ARM64  .tools/$tarball" | shasum -a 256 -c -
    tar -xzf ".tools/$tarball" -C .tools gitleaks
    rm ".tools/$tarball"
fi
echo "gitleaks $(.tools/gitleaks version) en .tools/gitleaks"

PRE_COMMIT_HOME="$root/.cache/pre-commit"
export PRE_COMMIT_HOME
.venv/bin/pre-commit install

# pre-commit no guarda PRE_COMMIT_HOME en el hook que genera: se añade tras el shebang
# para que cada commit use la caché del proyecto y no ~/.cache/pre-commit.
hook=.git/hooks/pre-commit
{
    head -n 1 "$hook"
    echo "export PRE_COMMIT_HOME='$PRE_COMMIT_HOME'"
    tail -n +2 "$hook"
} > "$hook.tmp"
mv "$hook.tmp" "$hook"
chmod +x "$hook"
echo "PRE_COMMIT_HOME=$PRE_COMMIT_HOME fijado en $hook"
