import sqlite3

import duckdb
import numpy as np
import pandas as pd
import pytest

from app.analytics import charts, data, roles, sql, statistics


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM unknown",
        "SELECT 1; SELECT 2",
        "SELECT * FROM read_csv('local.csv')",
        "ATTACH 'local.db' AS auxiliary",
        "SELECT * FROM information_schema.tables",
        "SELECT * INTO copied FROM dataset",
        "SELECT * FROM 'something.parquet'",
        "SELECT current_setting('memory_limit')",
        "WITH RECURSIVE a AS (SELECT 1) SELECT * FROM a",
    ],
)
def test_sql_rejects_disallowed_operations(query):
    with pytest.raises(ValueError):
        sql.validate(query, {"dataset"})


def test_sql_supports_registered_joins_and_ctes():
    left = pd.DataFrame({"id": [1, 2], "amount": [8, 5]})
    right = pd.DataFrame({"id": [1, 2], "region": ["North", "South"]})
    result = sql.execute(
        "WITH scoped AS (SELECT region, amount FROM dataset JOIN dataset_b USING (id)) "
        "SELECT region, SUM(amount) AS total FROM scoped GROUP BY region ORDER BY region",
        {"dataset": left, "dataset_b": right},
    )
    assert result["rows"] == [{"region": "North", "total": 8}, {"region": "South", "total": 5}]


@pytest.mark.parametrize("extension", [".csv", ".xlsx", ".json", ".parquet", ".sqlite", ".duckdb"])
def test_data_file_formats(extension, tmp_path):
    dataset = pd.DataFrame({"region": ["North", "South"], "revenue": [10, 20]})
    file = tmp_path / f"data{extension}"
    if extension == ".sqlite":
        with sqlite3.connect(file) as connection:
            dataset.to_sql("sales", connection, index=False)
    elif extension == ".duckdb":
        with duckdb.connect(str(file)) as connection:
            connection.register("source", dataset)
            connection.execute("CREATE TABLE sales AS SELECT * FROM source")
    elif extension == ".csv":
        dataset.to_csv(file, index=False)
    elif extension == ".json":
        dataset.to_json(file, orient="records")
    elif extension == ".xlsx":
        dataset.to_excel(file, index=False)
    else:
        dataset.to_parquet(file, index=False)
    parsed = data.parse(file.read_bytes(), file.name)
    assert data.profile(parsed)["rows"] == 2
    assert parsed["revenue"].sum() == 30


def test_every_role_computes_a_domain_metric():
    fields = {
        "actual": 100,
        "target": 80,
        "segment_size": 4,
        "market_size": 10,
        "revenue": 120,
        "expenses": 50,
        "attributed_revenue": 80,
        "ad_spend": 20,
        "retained": 8,
        "eligible": 10,
        "departures": 2,
        "average_headcount": 40,
        "fulfilled": 75,
        "ordered": 100,
        "period_return": 0.01,
    }
    frame = pd.DataFrame([fields] * 12)
    results = {
        role: roles.calculate(role, frame, data.profile(frame), "Analyze revenue") for role in roles.ROLES
    }
    assert len(results) == 12
    assert all(item["status"] == "computed" for item in results.values())
    assert results["sales"]["values"]["total"] == 1440
    assert results["marketing"]["values"]["ratio"] == 4
    assert results["market"]["values"]["ratio"] == 0.4
    assert results["hr"]["values"]["ratio"] == 0.05
    assert roles.calculate("hr", frame.head(), data.profile(frame.head()), "")["status"] == "suppressed"


def test_chart_and_forecast_models_against_known_data():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=32, freq="D").astype(str),
            "amount": np.arange(32) * 4 + 10,
            "predictor": np.arange(32),
            "group": ["A"] * 16 + ["B"] * 16,
        }
    )
    chart = charts.build(frame, charts.ChartSpec(x="group", y="amount"))
    assert chart["rows"][0] == {"group": "B", "value": 1664}
    forecast = statistics.forecast(frame, "date", "amount", 3)
    assert forecast["models"]["holt"]["mae"] < forecast["models"]["last_value"]["mae"]
    assert forecast["predictions"][0]["value"] == pytest.approx(138, abs=0.5)
    trained = statistics.model(frame, ["predictor"], "amount", False, "date")
    assert trained["metrics"]["r2"] == pytest.approx(1)
    classified = statistics.model(frame, ["predictor"], "group", True, None)
    assert classified["metrics"]["accuracy"] > 0.8
    tested = statistics.compare(frame, "group", "amount")
    assert tested["p_value"] < 0.001
    with pytest.raises(ValueError, match="feature"):
        statistics.model(frame, ["amount"], "amount", False, None)
