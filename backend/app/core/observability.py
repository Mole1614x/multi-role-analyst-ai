import json
import logging

from prometheus_client import Counter, Histogram

logger = logging.getLogger("uvicorn.error")
requests = Counter("analyst_http_requests", "HTTP requests", ("method", "status"))
latency = Histogram("analyst_http_duration_seconds", "HTTP request latency")
jobs = Counter("analyst_jobs", "Job outcomes", ("kind", "status"))
tokens = Counter("analyst_llm_tokens", "Tokens consumed", ("provider", "direction"))


def log(event: str, **fields):
    logger.info(json.dumps({"event": event, **fields}, default=str))
