import atexit
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

sandbox = TemporaryDirectory(prefix="analyst-tests-")
atexit.register(sandbox.cleanup)
os.environ["ANALYST_DATABASE_URL"] = f"sqlite:///{Path(sandbox.name) / 'test.sqlite3'}"
os.environ["ANALYST_STORAGE_DIR"] = str(Path(sandbox.name) / "objects")
os.environ["MPLCONFIGDIR"] = str(Path(sandbox.name) / "matplotlib")
os.environ["ANALYST_EAGER"] = "true"
os.environ["ANALYST_REDIS_URL"] = ""
os.environ["ANALYST_LLM_PROVIDER"] = "none"
os.environ["ANALYST_LLM_API_KEY"] = ""
os.environ["ANALYST_RESEARCH_API_KEY"] = ""
os.environ["ANALYST_ORIGIN"] = "http://testserver"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    from alembic.config import Config

    from alembic import command

    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as value:
        yield value
