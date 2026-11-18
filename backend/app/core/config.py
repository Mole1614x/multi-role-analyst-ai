from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


class SheetSource(BaseModel):
    spreadsheet_id: str = Field(pattern=r"^[A-Za-z0-9_-]{5,150}$")
    range: str = Field(min_length=1, max_length=200)


class RestSource(BaseModel):
    url: str = Field(max_length=2000, repr=False)
    records_key: str = Field(default="", max_length=150)
    bearer: SecretStr | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANALYST_",
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str = Field(
        default="sqlite:///./analyst.sqlite3",
        validation_alias=AliasChoices("ANALYST_DATABASE_URL", "DATABASE_URL"),
    )
    postgres_host: str = Field(default="127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, ge=1, le=65535, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(default="analyst", validation_alias="POSTGRES_DB")
    postgres_user: str = Field(default="analyst", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="", validation_alias="POSTGRES_PASSWORD", repr=False)
    redis_url: str = Field(default="", validation_alias=AliasChoices("ANALYST_REDIS_URL", "REDIS_URL"))
    celery_broker_url: str = Field(
        default="", validation_alias=AliasChoices("ANALYST_CELERY_BROKER_URL", "CELERY_BROKER_URL")
    )
    celery_result_backend: str = Field(
        default="", validation_alias=AliasChoices("ANALYST_CELERY_RESULT_BACKEND", "CELERY_RESULT_BACKEND")
    )
    eager: bool | None = None
    task_backend: Literal["local", "celery", "eager"] | None = Field(
        default=None, validation_alias=AliasChoices("ANALYST_TASK_BACKEND", "TASK_BACKEND")
    )
    origin: str = Field(
        default="http://localhost:3000", validation_alias=AliasChoices("ANALYST_ORIGIN", "FRONTEND_URL")
    )
    backend_url: str = Field(default=DEFAULT_BACKEND_URL, validation_alias="BACKEND_URL")
    cookie_secure: bool = False
    storage_dir: Path = Path("storage")
    s3_bucket: str = ""
    s3_endpoint: str = ""
    max_upload_bytes: int = 20_000_000
    max_rows: int = 200_000
    max_columns: int = 120
    max_datasets: int = 30
    max_versions: int = 30
    max_active_jobs: int = 4
    sql_timeout: float = 8.0
    job_timeout: int = 120
    session_hours: int = 72
    llm_provider: Literal["none", "openai", "gemini"] = "none"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_input_cost_per_million: float = 0
    llm_output_cost_per_million: float = 0
    research_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_from: str = ""
    smtp_username: str = ""
    smtp_password: str = ""
    postgres_sources: dict[str, str] = Field(default_factory=dict, repr=False)
    mysql_sources: dict[str, str] = Field(default_factory=dict, repr=False)
    google_sheets_sources: dict[str, SheetSource] = Field(default_factory=dict)
    google_sheets_api_key: str = Field(default="", repr=False)
    google_sheets_access_token: str = Field(default="", repr=False)
    rest_sources: dict[str, RestSource] = Field(default_factory=dict)
    admin_user_ids: list[str] = []

    @field_validator("backend_url", "origin")
    @classmethod
    def http_origin(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use an HTTP or HTTPS origin with an optional port.")
        _ = parsed.port  # Validate the port before startup.
        return value.rstrip("/")

    @model_validator(mode="after")
    def local_services(self) -> "Settings":
        if "database_url" not in self.model_fields_set and self.postgres_password:
            url = URL.create(
                "postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            )
        else:
            url = make_url(self.database_url)
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+psycopg")
        self.database_url = url.render_as_string(hide_password=False)
        if self.task_backend is None:
            if self.eager is True:
                self.task_backend = "eager"
            elif self.broker_url or self.eager is False:
                self.task_backend = "celery"
            else:
                self.task_backend = "local"
        self.eager = self.task_backend == "eager"
        return self

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url


@lru_cache
def settings() -> Settings:
    env_file = getenv("ANALYST_ENV_FILE")
    return Settings(_env_file=env_file) if env_file else Settings()
