from dataclasses import asdict, dataclass

import pandas as pd

from app.analytics.sql import column_for


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    template: str
    tool: str
    output: str
    policy: str
    columns: tuple[str, ...] = ()


ROLES: dict[str, Role] = {}


def register(role: Role) -> None:
    if role.id in ROLES:
        raise ValueError(f"Role already registered: {role.id}")
    ROLES[role.id] = role


for definition in (
    Role(
        "data",
        "Data Analyst",
        "Profile data and summarize a numeric measure",
        "summary",
        "Descriptive statistics",
        "Verify sample size and missingness.",
    ),
    Role(
        "business",
        "Business Analyst",
        "Compare actual vs target by reporting period",
        "variance",
        "Plan variance",
        "Identify target currency and comparable time periods.",
        ("actual", "target"),
    ),
    Role(
        "market",
        "Market Research Analyst",
        "Estimate market share from segment and market size",
        "ratio",
        "Segment share",
        "Mark sizing estimates and record primary evidence.",
        ("segment_size", "market_size"),
    ),
    Role(
        "finance",
        "Financial Analyst",
        "Calculate profit margin from revenue and expenses",
        "margin",
        "Profit and margin",
        "Validate units and report missing observations.",
        ("revenue", "expenses"),
    ),
    Role(
        "marketing",
        "Marketing Analyst",
        "Calculate return on ad spend",
        "ratio",
        "ROAS",
        "Report attributed revenue and avoid causal claims.",
        ("attributed_revenue", "ad_spend"),
    ),
    Role(
        "sales",
        "Sales Analyst",
        "Calculate booked revenue",
        "total",
        "Total revenue",
        "Verify currency, refunds, and reporting period.",
        ("revenue",),
    ),
    Role(
        "product",
        "Product Analyst",
        "Measure active users retained",
        "ratio",
        "Retention rate",
        "Use a matching cohort and time window.",
        ("retained", "eligible"),
    ),
    Role(
        "hr",
        "HR Analyst",
        "Measure aggregate turnover for a group of at least ten",
        "ratio",
        "Turnover rate",
        "Suppress small samples and exclude individual employment recommendations.",
        ("departures", "average_headcount"),
    ),
    Role(
        "operations",
        "Operations Analyst",
        "Calculate fulfillment rate",
        "ratio",
        "Fulfillment rate",
        "Check fulfillment and demand have the same units.",
        ("fulfilled", "ordered"),
    ),
    Role(
        "bi",
        "Business Intelligence Analyst",
        "Monitor missing cells and duplicate rows",
        "quality",
        "Data quality scorecard",
        "Make completeness denominator and duplicate checks visible.",
    ),
    Role(
        "risk",
        "Risk Analyst",
        "Find outliers using the interquartile range",
        "outliers",
        "Outlier count",
        "Treat outliers as review candidates.",
    ),
    Role(
        "investment",
        "Investment Analyst",
        "Measure historical periodic return and volatility",
        "returns",
        "Compounded return and observed volatility",
        "Check return frequency and decimal input.",
        ("period_return",),
    ),
):
    register(definition)


def definitions() -> list[dict]:
    return [asdict(role) for role in ROLES.values()]


def calculate(role_id: str, frame: pd.DataFrame, details: dict, prompt: str) -> dict:
    role = ROLES[role_id]
    result = {"role": role.id, "metric": role.output, "method": role.tool, "review": role.policy}
    numeric = list(frame.select_dtypes(include="number").columns)
    if role_id == "hr" and len(frame) < 10:
        return result | {
            "status": "suppressed",
            "reason": "At least ten aggregate observations are required.",
        }
    if role.tool == "quality":
        total = details["rows"] * details["column_count"]
        missing = sum(column["missing"] for column in details["columns"])
        return result | {
            "status": "computed",
            "values": {
                "missing_cells": missing,
                "duplicate_rows": details["duplicates"],
                "completeness": (total - missing) / total if total else None,
            },
        }
    measure = column_for(prompt, numeric) or next(iter(numeric), None)
    if role.tool in {"summary", "outliers"}:
        if not measure:
            return result | {"status": "unavailable", "reason": "A numeric column is required."}
        stats = next(col for col in details["columns"] if col["name"] == measure)
        keys = {"min", "max", "mean", "median"} if role.tool == "summary" else {"outliers"}
        values = {key: stats[key] for key in keys if key in stats}
        if not values:
            return result | {"status": "unavailable", "reason": "The selected column has no observations."}
        return result | {"status": "computed", "inputs": [measure], "values": values}
    match = {name.casefold(): name for name in numeric}
    if not all(name in match for name in role.columns):
        return result | {
            "status": "unavailable",
            "reason": "Required numeric columns: " + ", ".join(role.columns),
        }
    names = [match[name] for name in role.columns]
    observed = frame[names].dropna()
    if observed.empty or (role_id == "hr" and len(observed) < 10):
        return result | {"status": "unavailable", "reason": "Insufficient complete observations."}
    totals = observed.sum()
    evidence = {"status": "computed", "inputs": names, "sample_size": len(observed)}
    if role.tool == "total":
        values = {"total": float(totals.iloc[0])}
    elif role.tool == "returns":
        series = observed[names[0]]
        if (series < -1).any():
            return result | {
                "status": "unavailable",
                "reason": "Periodic returns must be decimal values at least -1.",
            }
        values = {
            "compounded_return": float((1 + series).prod() - 1),
            "observed_volatility": float(series.std()) if len(series) > 1 else None,
        }
    else:
        first, second = map(float, totals)
        values = {"first_total": first, "second_total": second}
        if role.tool == "variance":
            values["variance"] = first - second
        elif role.tool == "margin":
            values |= {"profit": first - second, "margin": (first - second) / first if first else None}
        else:
            values["ratio"] = first / second if second else None
    return result | evidence | {"values": values}
