from threading import Event, Thread

import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.analytics.data import DUCK_CONFIG, json_rows, quote
from app.core.config import settings

FUNCTIONS = frozenset(
    {
        "ABS",
        "AVG",
        "CAST",
        "TRY_CAST",
        "CEIL",
        "CEILING",
        "COALESCE",
        "COUNT",
        "DATE_TRUNC",
        "TIMESTAMP_TRUNC",
        "DAY",
        "EXTRACT",
        "FLOOR",
        "GREATEST",
        "LEAST",
        "LENGTH",
        "LOWER",
        "MAX",
        "MEDIAN",
        "MIN",
        "MONTH",
        "NULLIF",
        "POWER",
        "ROUND",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
        "SQRT",
        "STDDEV",
        "STDDEV_POP",
        "STDDEV_SAMP",
        "SUM",
        "TRIM",
        "UPPER",
        "VARIANCE",
        "VAR_POP",
        "VAR_SAMP",
        "YEAR",
        "CORR",
        "GROUPING",
        "LAG",
        "LEAD",
        "CASE",
        "IF",
        "AND",
        "OR",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
        "LIKE",
        "ILIKE",
        "REGEXP_LIKE",
        "CONCAT",
        "REPLACE",
        "SUBSTRING",
        "QUANTILE_CONT",
    }
)


def validate(sql: str, aliases: set[str]) -> str:
    if not sql or len(sql) > 12_000:
        raise ValueError("Enter a query of 1 to 12,000 characters.")
    try:
        parsed = sqlglot.parse(sql, read="duckdb")
        if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise ValueError("Only one SELECT query is allowed.")
        tree = parsed[0]
        ctes = {node.alias_or_name.casefold() for node in tree.find_all(exp.CTE)}
        if ctes & aliases or any(node.args.get("recursive") for node in tree.find_all(exp.With)):
            raise ValueError("Use distinct, nonrecursive CTE aliases.")
        for node in tree.walk():
            if isinstance(node, exp.Table):
                if not isinstance(node.this, exp.Identifier) or node.catalog or node.db:
                    raise ValueError("Only registered datasets are available.")
                if node.name.casefold() not in aliases | ctes:
                    raise ValueError(f"Unregistered table: {node.name}")
            if isinstance(
                node, (exp.DDL, exp.DML, exp.Command, exp.Into, exp.Lock, exp.Parameter, exp.Placeholder)
            ):
                raise ValueError("Only read-only dataset queries are allowed.")  # noqa: TRY004
            if isinstance(node, exp.Func):
                name = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
                if name.upper() not in FUNCTIONS:
                    raise ValueError(f"Unsupported SQL function: {name}")
            if isinstance(node, (exp.Unnest, exp.Lateral, exp.Pivot, exp.Dot)):
                raise ValueError("This SQL operation is unsupported.")  # noqa: TRY004
        return tree.sql(dialect="duckdb", comments=False)
    except (SqlglotError, RecursionError) as exc:
        raise ValueError("Invalid analytical SQL.") from exc


def execute(sql: str, frames: dict[str, pd.DataFrame]) -> dict:
    canonical = validate(sql, set(frames))
    config = settings()
    with duckdb.connect(config=DUCK_CONFIG) as connection:
        for alias, frame in frames.items():
            connection.register(alias, frame)
        finished = Event()

        def interrupt():
            if not finished.wait(config.sql_timeout):
                connection.interrupt()

        deadline = Thread(target=interrupt, daemon=True)
        deadline.start()
        try:
            result = connection.execute(f"SELECT * FROM ({canonical}) AS results LIMIT 501").fetchdf()
        except duckdb.Error as exc:
            # DuckDB messages can include source values. Expose safe diagnostic classes only.
            raise ValueError(
                f"Query failed ({type(exc).__name__}). Check column names, types, and query size."
            ) from exc
        finally:
            finished.set()
            deadline.join()
    return {
        "sql": canonical,
        "columns": list(result.columns),
        "rows": json_rows(result, 500),
        "truncated": len(result) > 500,
        "engine": f"DuckDB {duckdb.__version__}",
    }


def column_for(prompt: str, columns: list[str]) -> str | None:
    import re

    text = " ".join(re.findall(r"\w+", prompt.casefold().replace("_", " ")))
    for column in sorted(columns, key=len, reverse=True):
        label = " ".join(re.findall(r"\w+", column.casefold().replace("_", " ")))
        if label and f" {label} " in f" {text} ":
            return column
    return None


def draft(prompt: str, frame: pd.DataFrame) -> str:
    import re

    numeric = list(frame.select_dtypes(include="number").columns)
    measure = column_for(prompt, numeric)
    groups = [c for c in frame.columns if c != measure]
    group_request = re.split(r"\b(?:by|per|across)\b", prompt, maxsplit=1, flags=re.IGNORECASE)
    group = column_for(group_request[1], groups) if len(group_request) == 2 else None
    if re.search(r"\b(count|how many|number of rows)\b", group_request[0], re.IGNORECASE):
        value, title = "COUNT(*)", "row_count"
    elif measure:
        function = "AVG" if re.search(r"\b(mean|average)\b", prompt, re.IGNORECASE) else "SUM"
        value, title = f"{function}({quote(measure)})", f"{function.lower()}_{measure}"
    else:
        raise ValueError("Name a numeric measure or ask to count rows.")
    if group:
        column = quote(group)
        return f"SELECT {column}, {value} AS {quote(title)} FROM dataset GROUP BY {column} ORDER BY {column}"
    return f"SELECT {value} AS {quote(title)} FROM dataset"
