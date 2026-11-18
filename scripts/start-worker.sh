#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/local-env.sh"

mode="${1:-worker}"
if [[ $# -gt 1 || ("$mode" != "worker" && "$mode" != "beat") ]]; then
  fail "Usage: ./scripts/start-worker.sh [worker|beat]"
fi

need_backend
"$VENV_PYTHON" - <<'PY'
from app.core.config import settings

config = settings()
if not config.broker_url or config.eager:
    raise SystemExit("Configure REDIS_URL or CELERY_BROKER_URL and enable background jobs (ANALYST_EAGER=false).")
PY
if [[ "$mode" == "beat" ]]; then
  storage="$("$VENV_PYTHON" -c 'from app.core.config import settings; print(settings().storage_dir)')"
  mkdir -p -- "$storage"
  exec "$VENV_PYTHON" -m celery -A app.services.jobs:celery beat --loglevel=info \
    --schedule "$storage/celerybeat-schedule"
fi
exec "$VENV_PYTHON" -m celery -A app.services.jobs:celery worker --loglevel=info --concurrency=2
