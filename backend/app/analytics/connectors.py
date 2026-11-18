import re
from urllib.parse import quote, urlsplit

import httpx
import pandas as pd
from sqlalchemy import create_engine, make_url, text

from app.analytics import data
from app.core.config import settings


def available():
    config = settings()
    return {
        "postgresql": config.postgres_sources,
        "mysql": config.mysql_sources,
        "google_sheets": config.google_sheets_sources,
        "rest": config.rest_sources,
    }


def json_response(url, headers, parameters=None):
    with (
        httpx.Client(timeout=httpx.Timeout(8, connect=4), follow_redirects=False, trust_env=False) as client,
        client.stream("GET", url, params=parameters, headers=headers) as response,
    ):
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > settings().max_upload_bytes:
                raise ValueError("The configured response is too large to import.")
        return httpx.Response(200, content=bytes(raw)).json()


def mysql(dsn, table):
    identifiers = table.split(".")
    if len(identifiers) not in (1, 2) or any(
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item) for item in identifiers
    ):
        raise ValueError("Use a table name or database.table.")
    url = make_url(dsn)
    if url.drivername not in {"mysql", "mysql+pymysql"}:
        raise ValueError("Supply a MySQL connection string for this source.")
    engine = create_engine(
        url.set(drivername="mysql+pymysql"),
        connect_args={"connect_timeout": 5, "read_timeout": 8, "write_timeout": 8},
    )
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("START TRANSACTION READ ONLY")
            relation = ".".join(f"`{item}`" for item in identifiers)
            query = text(f"SELECT /*+ MAX_EXECUTION_TIME(7000) */ * FROM {relation} LIMIT :limit")
            return data.normalize(
                pd.read_sql_query(query, connection, params={"limit": settings().max_rows + 1})
            )
    finally:
        engine.dispose()


def sheets(source):
    config = settings()
    if not (config.google_sheets_api_key or config.google_sheets_access_token):
        raise ValueError("Configure Google Sheets authorization for this import.")
    headers = {"Accept": "application/json"}
    if config.google_sheets_access_token:
        headers["Authorization"] = f"Bearer {config.google_sheets_access_token}"
    else:
        headers["X-Goog-Api-Key"] = config.google_sheets_api_key
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{source.spreadsheet_id}/values/{quote(source.range, safe='')}"
    payload = json_response(url, headers, {"valueRenderOption": "UNFORMATTED_VALUE"})
    values = payload.get("values") if isinstance(payload, dict) else None
    if not isinstance(values, list) or len(values) < 2 or not isinstance(values[0], list):
        raise ValueError("The sheet range needs a header row and at least one data row.")
    if any(not isinstance(item, list) or len(item) > len(values[0]) for item in values[1:]):
        raise ValueError("The sheet contains data outside its header columns.")
    return data.normalize(pd.DataFrame(values[1:], columns=values[0]))


def rest(source):
    parsed = urlsplit(source.url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("Configure an HTTPS endpoint without embedded credentials.")
    headers = {"Accept": "application/json"}
    if source.bearer:
        headers["Authorization"] = f"Bearer {source.bearer.get_secret_value()}"
    payload = json_response(source.url, headers)
    if source.records_key and isinstance(payload, dict):
        payload = payload.get(source.records_key)
    if not isinstance(payload, list) or not payload or not all(isinstance(item, dict) for item in payload):
        raise ValueError("The endpoint must return a nonempty JSON array of records.")
    return data.normalize(pd.DataFrame.from_records(payload))
