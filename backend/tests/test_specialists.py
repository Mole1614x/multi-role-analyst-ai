import pandas as pd

from app.analytics.specialists import calculate


def test_finance_totals_and_missing_data():
    frame = pd.DataFrame(
        {
            "actual": [120, 60, None],
            "budget": [100, 100, 300],
            "cash_inflow": [150, 65, None],
            "cash_outflow": [80, 110, 200],
        }
    )
    variance, cash = calculate("finance", frame, "budget variance and cash flow")
    assert variance["excluded_rows"] == cash["excluded_rows"] == 1
    assert variance["values"] == {"actual": 180, "budget": 200, "variance": -20, "variance_rate": -0.1}
    assert cash["values"] == {"cash_inflow": 215, "cash_outflow": 190, "net_cash_flow": 25}
    assert (
        calculate("finance", pd.DataFrame({"actual": [4], "budget": [0]}), "budget variance")[0]["values"][
            "variance_rate"
        ]
        is None
    )


def test_last_touch_attribution():
    frame = pd.DataFrame(
        {
            "conversion_id": ["a", "a", "b"],
            "channel": ["email", "search", "email"],
            "touch_at": ["2025-01-01", "2025-01-03", "2025-01-02"],
            "conversion_value": [75, 75, 25],
        }
    )
    result = calculate("marketing", frame, "attribution")[0]["values"]
    assert result == {
        "conversions": 2,
        "revenue": 100,
        "channels": [
            {"channel": "email", "conversions": 1, "revenue": 25},
            {"channel": "search", "conversions": 1, "revenue": 75},
        ],
    }
    frame.loc[0, "touch_at"] = frame.loc[1, "touch_at"]
    assert calculate("marketing", frame, "attribution")[0]["status"] == "unavailable"


def test_cohort_churn_includes_zero_denominator():
    frame = pd.DataFrame({"cohort": ["Jan", "Jan", "Feb"], "eligible": [10, 30, 0], "retained": [8, 22, 0]})
    assert calculate("product", frame, "cohort churn")[0]["values"] == {
        "cohorts": [
            {
                "cohort": "Feb",
                "eligible": 0,
                "retained": 0,
                "churned": 0,
                "retention_rate": None,
                "churn_rate": None,
            },
            {
                "cohort": "Jan",
                "eligible": 40,
                "retained": 30,
                "churned": 10,
                "retention_rate": 0.75,
                "churn_rate": 0.25,
            },
        ]
    }
