#!/usr/bin/env bash

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
VENV="$BACKEND_DIR/.venv"
VENV_PYTHON="$VENV/bin/python"

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing $1. Install it using docs/LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md."
}

need_node() {
  need node
  need npm
  node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(
    (major === 20 && minor >= 19) || (major === 22 && minor >= 13) || major >= 24 ? 0 : 1
  )' || fail "Install a recent Node.js 22 LTS release on Monterey or Node.js 24 LTS on a supported system."
}

need_backend() {
  [[ -x "$VENV_PYTHON" ]] || fail "Backend virtual environment missing. Run ./scripts/setup-local-macos.sh first."
  cd -- "$BACKEND_DIR"
  "$VENV_PYTHON" -c 'import fastapi, uvicorn, celery, app.core.config' >/dev/null ||
    fail "Backend dependencies are missing. Run ./scripts/setup-local-macos.sh first."
}

local_address() {
  "$VENV_PYTHON" - "$1" <<'PY'
import sys
from urllib.parse import urlsplit

from app.core.config import settings

name = sys.argv[1]
config = settings()
url = urlsplit(config.backend_url if name == "BACKEND_URL" else config.origin)
if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit(f"{name} must use an HTTP loopback address for the native dev launcher.")
print("127.0.0.1" if url.hostname == "localhost" else url.hostname, url.port or 80)
PY
}
