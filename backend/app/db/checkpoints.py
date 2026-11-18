from contextlib import contextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.engine import make_url

from app.core.config import settings


def postgres_url() -> str | None:
    url = make_url(settings().database_url)
    if url.get_backend_name() == "postgresql":
        return url.set(drivername="postgresql").render_as_string(hide_password=False)
    return None


@contextmanager
def checkpointer():
    uri = postgres_url()
    if uri is None:
        yield InMemorySaver()
    else:
        with PostgresSaver.from_conn_string(uri) as storage:
            yield storage
