#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  printf '%s\n' 'Usage: ./scripts/setup-local-macos.sh [--dev]' \
    'Creates backend/.venv and installs Python and Node.js dependencies on macOS, Linux or WSL.' \
    'Set PYTHON_BIN to select a Python interpreter. --dev also installs backend test tools.'
  exit 0
fi
source "$(dirname -- "${BASH_SOURCE[0]}")/local-env.sh"

if [[ $# -gt 1 || ("${1:-}" != "" && "$1" != "--dev") ]]; then
  fail "Usage: ./scripts/setup-local-macos.sh [--dev]"
fi

need_node
if [[ -d "$VENV" ]]; then
  [[ -x "$VENV_PYTHON" ]] || fail "$VENV exists but its Python is missing. Move the old environment aside first."
  python="$VENV_PYTHON"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
  python="$PYTHON_BIN"
else
  python=python3
  for version in python3.11 python3.12 python3.13; do
    if command -v "$version" >/dev/null 2>&1; then
      python="$version"
      break
    fi
  done
fi

need "$python"
"$python" -c 'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] < (3, 14)))' ||
  fail "Python 3.11 through 3.13 is required. Use PYTHON_BIN to select it, or move an incompatible backend/.venv aside."
if [[ ! -d "$VENV" ]]; then
  "$python" -m venv "$VENV" || fail "Could not create $VENV. On Debian or Ubuntu install the matching python3-venv package."
fi

if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
  "$VENV_PYTHON" -m ensurepip --upgrade ||
    fail "Could not install pip into $VENV. Install Python with venv and ensurepip support."
fi
requirements=requirements.txt
if [[ "${1:-}" == "--dev" ]]; then requirements=requirements-dev.txt; fi
[[ -r "$BACKEND_DIR/$requirements" ]] || fail "$requirements is missing. Update the project checkout."
"$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/$requirements"
"$VENV_PYTHON" -m pip install --no-deps -e "$BACKEND_DIR"

if [[ ! -e "$REPO_ROOT/.env" && ! -L "$REPO_ROOT/.env" ]]; then
  (umask 077; set -o noclobber; cat "$REPO_ROOT/.env.example" > "$REPO_ROOT/.env")
  printf '%s\n' 'Created .env. Set PostgreSQL credentials and uncomment the Redis settings for the full native stack.'
fi

cd -- "$FRONTEND_DIR"
npm ci
printf '\n%s\n' 'Dependencies installed. Follow docs/LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md to configure services and run migrations.'
