import pandas as pd
import pytest

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


@pytest.mark.parametrize(
    ("role", "prompt", "inputs", "metric", "expected"),
    [
        ("data", "Pearson correlation", {"x": [1, 2, 3, None], "y": [2, 4, 6, 8]}, "pearson_r", 1),
        (
            "business",
            "Business case",
            {"expected_benefit": [90, 30], "implementation_cost": [50, 30]},
            "return_on_cost",
            0.5,
        ),
        (
            "market",
            "TAM, SAM, SOM",
            {
                "total_accounts": [200, 100],
                "serviceable_accounts": [100, 60],
                "obtainable_accounts": [40, 20],
                "annual_revenue_per_account": [5, 10],
            },
            "som",
            400,
        ),
        (
            "sales",
            "Weighted pipeline",
            {"deal_amount": [100, 50], "probability": [0.5, 0.2]},
            "weighted_amount",
            60,
        ),
        (
            "hr",
            "Hiring funnel",
            {"applicants": [60], "interviewed": [30], "hired": [15]},
            "interview_to_hire_rate",
            0.5,
        ),
        (
            "operations",
            "Inventory coverage",
            {"average_inventory": [20, 40], "daily_demand": [4, 6]},
            "days_of_supply",
            6,
        ),
        ("bi", "Key uniqueness", {"record_key": [" A ", "A", "B", None]}, "uniqueness_rate", 2 / 3),
        ("risk", "Expected loss", {"impact": [100, 300], "probability": [0.1, 0.2]}, "expected_loss", 70),
        ("investment", "Maximum drawdown", {"period_return": [0.2, -0.5, 0.1]}, "maximum_drawdown", 0.5),
    ],
)
def test_other_specialist_methods(role, prompt, inputs, metric, expected):
    finding = calculate(role, pd.DataFrame(inputs), prompt)[0]
    assert finding["status"] == "computed", finding
    assert finding["values"][metric] == pytest.approx(expected)


def test_hiring_funnel_discloses_no_small_count():
    frame = pd.DataFrame({"applicants": [40], "interviewed": [20], "hired": [9]})
    result = calculate("hr", frame, "hiring funnel")[0]
    assert "values" not in result
