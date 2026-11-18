from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANALYST_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./analyst.sqlite3"
    redis_url: str = ""
    eager: bool = True
    origin: str = "http://localhost:3000"
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
    postgres_sources: dict[str, str] = {}
    admin_user_ids: list[str] = []


@lru_cache
def settings() -> Settings:
    return Settings()
