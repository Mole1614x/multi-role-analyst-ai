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
    incoming, outgoing = (math.fsum(rows[name]) for name in ("cash_inflow", "cash_outflow"))
    return {"cash_inflow": incoming, "cash_outflow": outgoing, "net_cash_flow": incoming - outgoing}


def attribution(rows):
    rows = rows.copy()
    rows["touch_at"] = pd.to_datetime(rows["touch_at"], errors="coerce", utc=True, format="mixed")
    if rows["touch_at"].isna().any() or (rows["conversion_value"] < 0).any():
        raise ValueError("Provide valid touch timestamps and nonnegative conversion values.")
    credits = {}
    for _, group in rows.groupby("conversion_id", sort=False):
        if group["conversion_value"].nunique() != 1:
            raise ValueError("Each conversion must have one value across its touchpoints.")
        last = group.loc[group["touch_at"] == group["touch_at"].max(), "channel"].unique()
        if len(last) != 1:
            raise ValueError("The last eligible touch must identify one channel per conversion.")
        channel = str(last[0])
        current = credits.setdefault(channel, {"conversions": 0, "revenue": 0.0})
        current["conversions"] += 1
        current["revenue"] += float(group["conversion_value"].iloc[0])
    if len(credits) > 100:
        raise ValueError("Use at most 100 attribution channels.")
    return {
        "conversions": sum(item["conversions"] for item in credits.values()),
        "revenue": math.fsum(item["revenue"] for item in credits.values()),
        "channels": [{"channel": name, **item} for name, item in sorted(credits.items())],
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


METHODS = {
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
        if compute is cash_flow and (observed[list(numeric)] < 0).any().any():
            finding["reason"] = "Cash inflows and outflows must be nonnegative."
            continue
        try:
            values = compute(observed)
        except (ValueError, OverflowError) as exc:
            finding["reason"] = str(exc)
        else:
            finding.update(status="computed", values=values, sample_size=len(observed))
    return results
