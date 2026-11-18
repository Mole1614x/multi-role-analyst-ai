import hashlib
import json
import re
import sqlite3
from contextlib import closing
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZipFile

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from openpyxl import load_workbook
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db.models import Dataset, Version
from app.services import storage

FORMAT_NAMES = {".csv", ".xlsx", ".json", ".parquet", ".sqlite", ".sqlite3", ".db", ".duckdb"}
DUCK_CONFIG = {
    "enable_external_access": "false",
    "allow_unsigned_extensions": "false",
    "autoinstall_known_extensions": "false",
    "autoload_known_extensions": "false",
    "memory_limit": "192MB",
    "threads": "1",
    "max_temp_directory_size": "0B",
}


def json_rows(frame: pd.DataFrame, maximum: int = 100) -> list[dict]:
    return json.loads(frame.head(maximum).to_json(orient="records", date_format="iso"))


def profile(frame: pd.DataFrame) -> dict:
    columns = []
    for name in frame:
        series = frame[name]
        item = {
            "name": name,
            "type": str(series.dtype),
            "missing": int(series.isna().sum()),
            "distinct": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            numbers = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if len(numbers):
                q1, q3 = numbers.quantile([0.25, 0.75])
                iqr = q3 - q1
                item.update(
                    min=float(numbers.min()),
                    max=float(numbers.max()),
                    mean=float(numbers.mean()),
                    median=float(numbers.median()),
                    outliers=int(((numbers < q1 - 1.5 * iqr) | (numbers > q3 + 1.5 * iqr)).sum()),
                )
        columns.append(item)
    return {
        "rows": len(frame),
        "column_count": len(frame.columns),
        "columns": columns,
        "duplicates": int(frame.duplicated().sum()),
    }


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    config = settings()
    if not len(frame.columns) or len(frame.columns) > config.max_columns or len(frame) > config.max_rows:
        raise ValueError(f"Import supports up to {config.max_rows:,} rows and {config.max_columns} columns.")
    headers = [str(column).strip() for column in frame.columns]
    if any(not header or len(header) > 120 or any(ord(ch) < 32 for ch in header) for header in headers):
        raise ValueError("Column names must be 1 to 120 printable characters.")
    if len({h.casefold() for h in headers}) != len(headers):
        raise ValueError("Column names must be unique, ignoring case.")
    frame.columns = headers
    for column in frame.columns:
        if not pd.api.types.is_object_dtype(frame[column]):
            continue
        values = frame[column].dropna()
        if len(values) and values.map(lambda value: isinstance(value, (bool, int, float, str))).all():
            frame[column] = frame[column].convert_dtypes()
        if pd.api.types.is_object_dtype(frame[column]):
            frame[column] = frame[column].map(lambda x: str(x) if x is not None else None).astype("string")
    return frame.replace([np.inf, -np.inf], np.nan)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def from_database(data: bytes, extension: str, table: str | None) -> pd.DataFrame:
    limit = settings().max_rows + 1
    with TemporaryDirectory() as directory:
        path = Path(directory) / "source"
        path.write_bytes(data)
        if extension == ".duckdb":
            with duckdb.connect(str(path), read_only=True, config=DUCK_CONFIG) as connection:
                names = [
                    row[0]
                    for row in connection.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY table_name"
                    ).fetchall()
                ]
                selected = select_table(names, table)
                return connection.execute(f"SELECT * FROM main.{quote(selected)} LIMIT {limit}").fetchdf()
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            names = [
                row[1]
                for row in connection.execute("PRAGMA table_list")
                if row[0] == "main" and row[2] == "table" and not row[1].startswith("sqlite_")
            ]
            selected = select_table(names, table)
            return pd.read_sql_query(f"SELECT * FROM main.{quote(selected)} LIMIT {limit}", connection)


def select_table(names: list[str], requested: str | None) -> str:
    if not names:
        raise ValueError("The source has no supported tables.")
    if requested is None and len(names) == 1:
        return names[0]
    if requested not in names:
        raise ValueError("Specify one of these source tables: " + ", ".join(names[:20]))
    return requested


def import_postgres(source: str, table: str) -> pd.DataFrame:
    dsn = settings().postgres_sources.get(source)
    if not dsn:
        raise ValueError("This PostgreSQL connector is unavailable.")
    identifiers = table.split(".")
    if len(identifiers) not in (1, 2) or any(
        not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", x) for x in identifiers
    ):
        raise ValueError("Use a table name or schema.table.")
    engine = create_engine(
        dsn,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=7000 -c default_transaction_read_only=on",
        },
    )
    try:
        with engine.connect() as connection:
            query = "SELECT * FROM " + ".".join(map(quote, identifiers)) + " LIMIT :limit"
            return normalize(
                pd.read_sql_query(text(query), connection, params={"limit": settings().max_rows + 1})
            )
    finally:
        engine.dispose()


def parse(data: bytes, filename: str, table: str | None = None) -> pd.DataFrame:
    extension = Path(filename).suffix.lower()
    limit = settings().max_rows + 1
    stream = BytesIO(data)
    if extension not in FORMAT_NAMES or not data:
        raise ValueError("Choose a nonempty CSV, Excel, JSON, Parquet, SQLite, or DuckDB file.")
    if extension == ".csv":
        frame = pd.read_csv(stream, nrows=limit)
    elif extension == ".xlsx":
        with ZipFile(stream) as archive:
            if len(archive.infolist()) > 1000 or sum(i.file_size for i in archive.infolist()) > 80_000_000:
                raise ValueError("Workbook expands beyond the import limit.")
        workbook = load_workbook(stream, read_only=True, data_only=True, keep_links=False)
        try:
            sheet = workbook[table] if table else workbook.active
            if sheet is None or (sheet.max_column or 0) > settings().max_columns:
                raise ValueError("Choose a worksheet within the column limit.")
            records = sheet.values
            header = next(records, None)
            from itertools import islice

            frame = pd.DataFrame(list(islice(records, limit)), columns=header)
        finally:
            workbook.close()
    elif extension == ".json":
        records = json.load(stream)
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records[:limit]):
            raise ValueError("JSON imports require an array of records.")
        frame = pd.DataFrame(records[:limit])
    elif extension == ".parquet":
        file = pq.ParquetFile(stream)
        if (
            file.metadata.num_rows >= limit
            or file.metadata.num_columns > settings().max_columns
            or sum(file.metadata.row_group(i).total_byte_size for i in range(file.num_row_groups))
            > 80_000_000
        ):
            raise ValueError("Parquet file exceeds the decompressed import limit.")
        frame = file.read(use_threads=False).to_pandas()
    else:
        frame = from_database(data, extension, table)
    return normalize(frame)


def save_version(
    dataset: Dataset,
    frame: pd.DataFrame,
    number: int,
    parent: Version | None = None,
    steps: list | None = None,
) -> Version:
    details = profile(frame)
    data = frame.to_parquet(index=False)
    if len(data) > settings().max_upload_bytes * 3:
        raise ValueError("The dataset exceeds the storage allowance.")
    key = f"datasets/{dataset.project_id}/{uuid4()}.parquet"
    storage.put(key, data)
    return Version(
        dataset_id=dataset.id,
        parent_id=parent.id if parent else None,
        number=number,
        object_key=key,
        sha256=hashlib.sha256(data).hexdigest(),
        profile=details,
        transformations=steps or [],
    )


def load(version: Version) -> pd.DataFrame:
    return pd.read_parquet(BytesIO(storage.read(version.object_key)))


class Transformation(BaseModel):
    operation: str
    column: str = Field(default="", max_length=120)
    value: str = Field(default="", max_length=500)


def clean(frame: pd.DataFrame, steps: list[Transformation]) -> pd.DataFrame:
    updated = frame.copy()
    for step in steps:
        name, value = step.column, step.value
        if step.operation == "drop_duplicates":
            updated = updated.drop_duplicates()
        elif step.operation == "standardize_columns":
            updated.columns = [re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_") for h in updated.columns]
        elif name not in updated:
            raise ValueError(f"Unknown column: {name}")
        elif step.operation == "drop_column":
            updated = updated.drop(columns=name)
        elif step.operation == "drop_missing":
            updated = updated.dropna(subset=[name])
        elif step.operation == "fill_missing":
            series = updated[name]
            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                updated[name] = series.astype("Float64").fillna(float(value))
            else:
                updated[name] = series.astype("string").fillna(value)
        elif step.operation == "to_number":
            updated[name] = pd.to_numeric(updated[name], errors="coerce")
        elif step.operation == "to_date":
            updated[name] = pd.to_datetime(updated[name], errors="coerce", utc=True)
        elif step.operation == "filter_equals":
            updated = updated[updated[name].astype("string") == value]
        elif step.operation == "trim":
            updated[name] = updated[name].astype("string").str.strip()
        elif step.operation == "cap_outliers":
            series = pd.to_numeric(updated[name], errors="raise").astype(float)
            q1, q3 = series.quantile([0.25, 0.75])
            updated[name] = series.clip(q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1))
        else:
            raise ValueError("This transformation is unsupported.")
    return normalize(updated.reset_index(drop=True))
