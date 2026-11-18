"""Deterministic specialist calculations over explicitly named fields."""

import math

import pandas as pd


def budget(rows):
    actual, budgeted = (math.fsum(rows[name]) for name in ("actual", "budget"))
    variance = actual - budgeted
    return {
        "actual": actual,
        "budget": budgeted,
        "variance": variance,
        "variance_rate": variance / abs(budgeted) if budgeted else None,
    }


def cash_flow(rows):
    if (rows[["cash_inflow", "cash_outflow"]] < 0).any().any():
        raise ValueError("Cash inflows and outflows must be nonnegative.")
    incoming, outgoing = (math.fsum(rows[name]) for name in ("cash_inflow", "cash_outflow"))
    return {"cash_inflow": incoming, "cash_outflow": outgoing, "net_cash_flow": incoming - outgoing}


def attribution(rows):
    rows = rows.copy()
    rows["touch_at"] = pd.to_datetime(rows["touch_at"], errors="coerce", utc=True, format="mixed")
    if rows["touch_at"].isna().any() or (rows["conversion_value"] < 0).any():
        raise ValueError("Provide valid touch timestamps and nonnegative conversion values.")
    conversions = rows.groupby("conversion_id", sort=False)
    if conversions["conversion_value"].nunique().gt(1).any():
        raise ValueError("Each conversion must have one value across its touchpoints.")
    latest = rows.loc[rows["touch_at"].eq(conversions["touch_at"].transform("max"))]
    if latest.groupby("conversion_id")["channel"].nunique().gt(1).any():
        raise ValueError("The last eligible touch must identify one channel per conversion.")
    assigned = latest.drop_duplicates("conversion_id")
    credits = assigned.groupby("channel")["conversion_value"].agg(["size", "sum"])
    if len(credits) > 100:
        raise ValueError("Use at most 100 attribution channels.")
    return {
        "conversions": len(assigned),
        "revenue": math.fsum(assigned["conversion_value"]),
        "channels": [
            {"channel": str(channel), "conversions": int(size), "revenue": float(revenue)}
            for channel, (size, revenue) in credits.iterrows()
        ],
    }


def cohort(rows):
    eligible, retained = rows["eligible"], rows["retained"]
    if (
        (eligible < 0) | (retained < 0) | (retained > eligible) | (eligible % 1 != 0) | (retained % 1 != 0)
    ).any():
        raise ValueError("Provide whole, nonnegative cohort counts with retained at most eligible.")
    groups = rows.groupby("cohort", sort=True)[["eligible", "retained"]].sum()
    if len(groups) > 100:
        raise ValueError("Use at most 100 cohort labels.")
    return {
        "cohorts": [
            {
                "cohort": str(label),
                "eligible": int(total),
                "retained": int(kept),
                "churned": int(total - kept),
                "retention_rate": float(kept / total) if total else None,
                "churn_rate": float((total - kept) / total) if total else None,
            }
            for label, (total, kept) in groups.iterrows()
        ]
    }


def correlation(rows):
    if len(rows) < 3 or rows["x"].nunique() < 2 or rows["y"].nunique() < 2:
        raise ValueError("Provide at least three complete pairs and two varying measures.")
    value = float(rows["x"].corr(rows["y"]))
    if not math.isfinite(value):
        raise ValueError("The measures exceed the numerical range for correlation.")
    return {"pearson_r": value}


def business_case(rows):
    benefit, cost = (math.fsum(rows[name]) for name in ("expected_benefit", "implementation_cost"))
    if (rows["implementation_cost"] < 0).any():
        raise ValueError("Implementation cost must be nonnegative.")
    net = benefit - cost
    return {
        "expected_benefit": benefit,
        "implementation_cost": cost,
        "net_benefit": net,
        "return_on_cost": net / cost if cost else None,
    }


def market_sizing(rows):
    total, reachable, obtainable = (
        rows[name] for name in ("total_accounts", "serviceable_accounts", "obtainable_accounts")
    )
    if (rows < 0).any().any() or (rows.iloc[:, :3] % 1 != 0).any().any():
        raise ValueError("Provide whole nonnegative account counts and nonnegative annual unit revenue.")
    if ((total < reachable) | (reachable < obtainable)).any():
        raise ValueError("Obtainable accounts cannot exceed serviceable accounts or the total market.")
    return {
        label: math.fsum(count * rows["annual_revenue_per_account"])
        for label, count in (("tam", total), ("sam", reachable), ("som", obtainable))
    }


def probabilities(rows):
    if not rows["probability"].between(0, 1).all():
        raise ValueError("Enter probabilities as fractions from zero to one.")


def pipeline(rows):
    probabilities(rows)
    if (rows["deal_amount"] < 0).any():
        raise ValueError("Deal amounts must be nonnegative.")
    return {
        "pipeline_amount": math.fsum(rows["deal_amount"]),
        "weighted_amount": math.fsum(rows["deal_amount"] * rows["probability"]),
    }


def hiring_funnel(rows):
    applicants, interviewed, hired = (rows[name] for name in ("applicants", "interviewed", "hired"))
    if (rows < 0).any().any() or (rows % 1 != 0).any().any():
        raise ValueError("Hiring stages require whole nonnegative counts.")
    if ((applicants < interviewed) | (interviewed < hired)).any():
        raise ValueError("Applicant, interview, and hire counts must decrease through the funnel.")
    total, interviews, hires = (int(series.sum()) for series in (applicants, interviewed, hired))
    if min(total, interviews, hires, total - interviews, interviews - hires) < 10:
        raise ValueError(
            "Aggregate funnel stages and their differences must each represent at least ten people."
        )
    return {
        "applicants": total,
        "interview_rate": interviews / total,
        "interview_to_hire_rate": hires / interviews,
    }


def inventory(rows):
    if (rows < 0).any().any():
        raise ValueError("Inventory and demand must be nonnegative.")
    quantity, demand = (math.fsum(rows[name]) for name in ("average_inventory", "daily_demand"))
    return {
        "average_inventory": quantity,
        "daily_demand": demand,
        "days_of_supply": quantity / demand if demand else None,
    }


def uniqueness(rows):
    key = rows["record_key"]
    duplicates = int(key.duplicated().sum())
    return {
        "duplicate_entries": duplicates,
        "distinct_keys": len(key) - duplicates,
        "uniqueness_rate": 1 - duplicates / len(key),
    }


def expected_loss(rows):
    probabilities(rows)
    if (rows["impact"] < 0).any():
        raise ValueError("Loss impacts must be nonnegative.")
    return {
        "expected_loss": math.fsum(rows["impact"] * rows["probability"]),
        "total_impact": math.fsum(rows["impact"]),
    }


def drawdown(rows):
    returns = rows["period_return"]
    if (returns < -1).any():
        raise ValueError("Enter periodic returns as decimals greater than or equal to minus one.")
    wealth = peak = 1.0
    largest = 0.0
    for period_return in returns:
        wealth *= 1 + period_return
        if not math.isfinite(wealth):
            raise ValueError("The compounded return exceeds the supported numerical range.")
        peak = max(wealth, peak)
        largest = max(largest, 1 - wealth / peak)
    return {"maximum_drawdown": largest, "compounded_return": wealth - 1}


METHODS = {
    "data": (
        (
            ("pearson correlation",),
            "Pearson correlation",
            ("x", "y"),
            (),
            correlation,
            "Complete numeric pairs should represent matched observations.",
        ),
    ),
    "business": (
        (
            ("business case",),
            "Business case return",
            ("expected_benefit", "implementation_cost"),
            (),
            business_case,
            "Use one currency and a common horizon. Expected benefits are scenario inputs.",
        ),
    ),
    "market": (
        (
            ("market sizing", "tam sam som", "tam, sam"),
            "Market sizing",
            (
                "total_accounts",
                "serviceable_accounts",
                "obtainable_accounts",
                "annual_revenue_per_account",
            ),
            (),
            market_sizing,
            "Inputs are assumptions. Use disjoint segments, a common annual horizon, and one currency.",
        ),
    ),
    "sales": (
        (
            ("weighted pipeline", "sales pipeline"),
            "Weighted sales pipeline",
            ("deal_amount", "probability"),
            (),
            pipeline,
            "Use distinct deals, one currency, and calibrated close probabilities.",
        ),
    ),
    "hr": (
        (
            ("hiring funnel",),
            "Aggregate hiring funnel",
            ("applicants", "interviewed", "hired"),
            (),
            hiring_funnel,
            "Use disjoint aggregate counts for a common intake cohort.",
        ),
    ),
    "operations": (
        (
            ("days of supply", "inventory coverage"),
            "Inventory coverage",
            ("average_inventory", "daily_demand"),
            (),
            inventory,
            "Use comparable measures in one unit across disjoint inventory categories.",
        ),
    ),
    "bi": (
        (
            ("key uniqueness",),
            "Record key uniqueness",
            (),
            ("record_key",),
            uniqueness,
            "Evaluate one key after trimming surrounding whitespace. The rate uses nonempty keys.",
        ),
    ),
    "risk": (
        (
            ("expected loss",),
            "Expected loss",
            ("impact", "probability"),
            (),
            expected_loss,
            "Use incremental impact in one unit and probabilities for the same horizon.",
        ),
    ),
    "investment": (
        (
            ("maximum drawdown", "max drawdown"),
            "Maximum drawdown",
            ("period_return",),
            (),
            drawdown,
            "Use chronologically ordered simple period returns for one portfolio.",
        ),
    ),
    "finance": (
        (
            ("budget variance",),
            "Budget variance",
            ("actual", "budget"),
            (),
            budget,
            "Amounts share a currency and reporting period. Positive variance means above budget.",
        ),
        (
            ("cash flow", "cash-flow"),
            "Cash flow",
            ("cash_inflow", "cash_outflow"),
            (),
            cash_flow,
            "Use period cash amounts in the same currency and enter outflows as positive amounts.",
        ),
    ),
    "marketing": (
        (
            ("attribution", "last touch", "last-touch"),
            "Last-touch attribution",
            ("conversion_value",),
            ("conversion_id", "channel", "touch_at"),
            attribution,
            "Supply eligible pre-conversion touches and repeated conversion values in one currency. Credit is observational.",
        ),
    ),
    "product": (
        (
            ("cohort", "churn"),
            "Cohort retention and churn",
            ("eligible", "retained"),
            ("cohort",),
            cohort,
            "Use nonoverlapping counts per cohort and the same observation window. Rates are fractions.",
        ),
    ),
}


def calculate(role: str, frame: pd.DataFrame, prompt: str) -> list[dict]:
    results = []
    names = {str(name).casefold(): name for name in frame.columns}
    for triggers, metric, numeric, labels, compute, assumptions in METHODS.get(role, ()):
        if not any(trigger in prompt.casefold() for trigger in triggers):
            continue
        fields = (*numeric, *labels)
        finding = {
            "role": role,
            "metric": metric,
            "method": metric,
            "review": assumptions,
            "inputs": list(fields),
            "status": "unavailable",
        }
        results.append(finding)
        if any(name not in names for name in fields):
            finding["reason"] = "Required columns: " + ", ".join(fields)
            continue
        rows = frame[[names[name] for name in fields]].copy()
        rows.columns = list(fields)
        for name in numeric:
            rows[name] = pd.to_numeric(rows[name], errors="coerce").replace(
                [float("inf"), float("-inf")], float("nan")
            )
        for name in labels:
            rows[name] = rows[name].astype("string").str.strip().replace("", pd.NA)
        observed = rows.dropna()
        finding["excluded_rows"] = len(rows) - len(observed)
        if observed.empty:
            finding["reason"] = "No complete observations."
            continue
        if compute is attribution and len(observed) != len(rows):
            finding["reason"] = "Every touch must be complete to identify the last touch reliably."
            continue
        if compute is drawdown and len(observed) != len(rows):
            finding["reason"] = "The chronological return series must contain every period."
            continue
        try:
            values = compute(observed)
        except (ValueError, OverflowError) as exc:
            finding["reason"] = str(exc)
        else:
            if any(isinstance(value, float) and not math.isfinite(value) for value in values.values()):
                finding["reason"] = "The result exceeds the supported numerical range."
                continue
            finding.update(status="computed", values=values, sample_size=len(observed))
    return results
