import sys

from celery.utils.nodenames import default_nodename
from kombu.exceptions import OperationalError

from app.core.task_queue import celery


def main() -> int:
    worker = default_nodename(None)
    try:
        with celery.connection_for_write(connect_timeout=3) as connection:
            connection.ensure_connection(max_retries=0)
            replies = celery.control.ping(destination=[worker], timeout=5, connection=connection)
    except (OperationalError, OSError) as exc:
        print(f"Celery health check could not reach the broker ({type(exc).__name__}).", file=sys.stderr)
        return 1

    if any(reply.get(worker) == {"ok": "pong"} for reply in replies):
        return 0
    print(f"Celery worker {worker} did not answer the health check.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
