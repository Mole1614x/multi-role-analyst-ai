from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.task_queue import celery


def test_local_postgres_credentials_are_encoded(monkeypatch):
    monkeypatch.delenv("ANALYST_DATABASE_URL")
    config = Settings(
        postgres_host="127.0.0.1",
        postgres_port=15432,
        postgres_db="workspace",
        postgres_user="analyst",
        postgres_password="p@ss:/word?%",
    )

    url = make_url(config.database_url)
    assert (url.drivername, url.host, url.port, url.database) == (
        "postgresql+psycopg",
        "127.0.0.1",
        15432,
        "workspace",
    )
    assert url.username == "analyst"
    assert url.password == "p@ss:/word?%"


def test_local_dotenv_aliases_and_precedence(tmp_path: Path, monkeypatch):
    for name in ("ANALYST_DATABASE_URL", "ANALYST_REDIS_URL", "ANALYST_EAGER", "ANALYST_ORIGIN"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "APP_ENV=development\n"
        "DATABASE_URL=postgresql://analyst:example@localhost/analytics\n"
        "ANALYST_DATABASE_URL=postgres://analyst:example@127.0.0.1/overridden\n"
        "REDIS_URL=redis://127.0.0.1:6379/0\n"
        "CELERY_BROKER_URL=redis://127.0.0.1:6379/2\n"
        "CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1\n"
        "FRONTEND_URL=http://localhost:3005/\n"
        "BACKEND_URL=http://127.0.0.1:8005/\n"
    )
    config = Settings(_env_file=env)
    assert config.app_env == "development"
    assert config.database_url == "postgresql+psycopg://analyst:example@127.0.0.1/overridden"
    assert config.redis_url.endswith("/0")
    assert config.broker_url.endswith("/2")
    assert config.celery_result_backend.endswith("/1")
    assert config.eager is False
    assert config.origin == "http://localhost:3005"
    assert config.backend_url == "http://127.0.0.1:8005"

    monkeypatch.setenv("ANALYST_DATABASE_URL", "sqlite:///./environment.sqlite3")
    monkeypatch.setenv("ANALYST_EAGER", "true")
    config = Settings(_env_file=env)
    assert config.database_url == "sqlite:///./environment.sqlite3"
    assert config.eager is True


def test_redis_url_is_the_default_broker():
    config = Settings(redis_url="redis://127.0.0.1:6379/0")
    assert config.broker_url == config.redis_url
    assert {"analyst.execute", "analyst.dispatch_due"} <= set(celery.tasks)


def test_dev_health_and_docs_aliases(client: TestClient):
    assert client.get("/health").json() == {"status": "ready"}
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert docs.url.path == "/api/docs"
    assert docs.headers["Content-Type"].startswith("text/html")
