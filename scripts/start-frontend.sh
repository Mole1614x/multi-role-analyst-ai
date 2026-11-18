#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/local-env.sh"

need_node
need_backend
[[ -x "$FRONTEND_DIR/node_modules/.bin/next" ]] || fail "Frontend dependencies are missing. Run npm ci in frontend."
read -r host port < <(local_address FRONTEND_URL)
if [[ -z "${API_INTERNAL_URL:-}" ]]; then
  BACKEND_URL="$("$VENV_PYTHON" -c 'from app.core.config import settings; print(settings().backend_url)')"
  export BACKEND_URL
fi
cd -- "$FRONTEND_DIR"
exec ./node_modules/.bin/next dev --hostname "$host" --port "$port"
