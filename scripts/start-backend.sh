#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/local-env.sh"

need_backend
read -r host port < <(local_address BACKEND_URL)
exec "$VENV_PYTHON" -m uvicorn app.main:app --reload --host "$host" --port "$port" --no-proxy-headers
