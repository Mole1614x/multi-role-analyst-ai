#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/local-env.sh"

if [[ $# -gt 1 || ("${1:-}" != "" && "$1" != "--running") ]]; then
  fail "Usage: ./scripts/check-local-services.sh [--running]"
fi

need_backend
"$VENV_PYTHON" - "${1:-}" <<'PY'
import sys
from urllib.request import urlopen

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.task_queue import celery
from app.db.session import check_db

config = settings()
postgres = make_url(config.database_url).get_backend_name() == "postgresql"
failures = 0
if not postgres:
    print("PostgreSQL is not configured. Set DATABASE_URL or the POSTGRES_* values.", file=sys.stderr)
    failures += 1
else:
    try:
        check_db()
        print("PostgreSQL: connected")
    except SQLAlchemyError as exc:
        print("PostgreSQL: connection failed. Check the host, port, role and database.", file=sys.stderr)
        print(f"Database error type: {type(exc).__name__}", file=sys.stderr)
        failures += 1

if not config.redis_url:
    print("Redis is not configured. Set REDIS_URL in .env.", file=sys.stderr)
    failures += 1
if not config.broker_url or config.eager:
    print("Celery background processing is disabled. Configure its Redis broker and ANALYST_EAGER.", file=sys.stderr)
    failures += 1

for url in dict.fromkeys(filter(None, (config.redis_url, config.broker_url, config.celery_result_backend))):
    try:
        with Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2) as client:
            client.ping()
        print("Redis: PONG")
    except (RedisError, ValueError):
        print("Redis: connection failed. Check its service, port and URL.", file=sys.stderr)
        failures += 1

if sys.argv[1] == "--running":
    for label, url in (("Uvicorn", config.backend_url + "/health"),
                       ("Next.js API proxy", config.origin + "/api/health/ready")):
        try:
            with urlopen(url, timeout=5) as response:
                print(f"{label}: HTTP {response.status}")
        except OSError:
            print(f"{label}: unavailable. Check the launcher and port.", file=sys.stderr)
            failures += 1
    if not failures:
        workers = celery.control.inspect(timeout=5).registered() or {}
        if any({"analyst.dispatch_due", "analyst.execute"} <= set(tasks) for tasks in workers.values()):
            print("Celery: worker is reachable and both project tasks are registered")
        else:
            print("Celery: no worker reported both project tasks. Run ./scripts/start-worker.sh.", file=sys.stderr)
            failures += 1

raise SystemExit(bool(failures))
PY
