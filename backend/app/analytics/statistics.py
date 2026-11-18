import numpy as np
import pandas as pd
from scipy import stats
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import Holt

from app.analytics.data import json_rows


def forecast(frame: pd.DataFrame, date: str, value: str, horizon: int) -> dict:
    if date == value or date not in frame or value not in frame:
        raise ValueError("Choose a date field and a separate numeric measure.")
    dates = pd.to_datetime(frame[date], utc=True, errors="coerce")
    values = pd.to_numeric(frame[value], errors="coerce").replace([np.inf, -np.inf], np.nan)
    valid = pd.DataFrame({"date": dates, "value": values}).dropna()
    daily = valid.groupby(valid["date"].dt.floor("D"))["value"].sum()
    if len(daily) < 12:
        raise ValueError("Forecasting requires at least twelve distinct observed dates.")
    inferred = pd.infer_freq(daily.index)
    frequency = pd.tseries.frequencies.to_offset(inferred).freqstr if inferred is not None else None
    if frequency is None:
        raise ValueError("Provide dates at a regular daily, weekly, or monthly frequency without gaps.")
    daily = daily.asfreq(frequency)
    train, test = daily.iloc[: -max(3, len(daily) // 5)], daily.iloc[-max(3, len(daily) // 5) :]
    holt = Holt(train, initialization_method="estimated").fit()
    errors = test.to_numpy() - np.asarray(holt.forecast(len(test)))

    def scores(pred):
        return {
            "mae": float(mean_absolute_error(test, pred)),
            "rmse": float(np.sqrt(mean_squared_error(test, pred))),
        }

    baseline = scores(np.repeat(train.iloc[-1], len(test)))
    trend = scores(holt.forecast(len(test)))
    use_trend = trend["mae"] < baseline["mae"]
    future = pd.date_range(daily.index[-1], periods=horizon + 1, freq=frequency)[1:]
    estimates = (
        np.asarray(Holt(daily, initialization_method="estimated").fit().forecast(horizon))
        if use_trend
        else np.repeat(daily.iloc[-1], horizon)
    )
    residuals = errors if use_trend else test.to_numpy() - train.iloc[-1]
    margin = float(stats.t.ppf(0.975, len(test) - 1) * np.sqrt(np.mean(residuals**2)))
    return {
        "method": "Holt linear trend" if use_trend else "Last observed value",
        "parameters": {"date": date, "measure": value, "horizon": horizon, "frequency": frequency},
        "train_count": len(train),
        "test_count": len(test),
        "discarded_rows": len(frame) - len(valid),
        "models": {"last_value": baseline, "holt": trend},
        "observed": json_rows(daily.tail(120).rename("value").rename_axis("date").reset_index(), 120),
        "predictions": [
            {
                "date": t.isoformat(),
                "value": float(pred),
                "lower": float(pred - margin),
                "upper": float(pred + margin),
            }
            for t, pred in zip(future, estimates)
        ],
        "limitations": [
            "Intervals use holdout error as an approximate constant-width uncertainty band.",
            "The evaluation uses a single chronological holdout and summed observations per day.",
            "Past patterns may change. Seasonality is not modeled.",
        ],
    }


def model(
    frame: pd.DataFrame, features: list[str], target: str, classification: bool, order_by: str | None
) -> dict:
    if target not in frame or not features or target in features or len(set(features)) != len(features):
        raise ValueError("Use distinct feature columns and exclude the target from the feature list.")
    if any(feature not in frame for feature in features) or (order_by and order_by not in frame):
        raise ValueError("A selected model column is unavailable.")
    data = frame.sort_values(order_by, kind="stable") if order_by else frame
    x = data[features].apply(pd.to_numeric, errors="coerce")
    y = data[target] if classification else pd.to_numeric(data[target], errors="coerce")
    mask = x.notna().all(axis=1) & y.notna()
    x, y = x.loc[mask], y.loc[mask]
    if len(x) < 24:
        raise ValueError("Models require at least 24 complete observations.")
    if any(
        x[column].astype(str).equals(y.astype(str))
        or np.array_equal(x[column].to_numpy(), pd.to_numeric(y, errors="coerce").to_numpy())
        for column in features
    ):
        raise ValueError("A feature duplicates the target. Remove it to avoid data leakage.")
    cut = int(len(x) * 0.8)
    if classification:
        y = y.astype(str)
        if y.nunique() not in range(2, 11) or y.value_counts().min() < 5:
            raise ValueError("Use 2 to 10 target categories with at least five observations each.")
    if order_by:
        train_x, test_x, train_y, test_y = x.iloc[:cut], x.iloc[cut:], y.iloc[:cut], y.iloc[cut:]
    else:
        train_x, test_x, train_y, test_y = train_test_split(
            x, y, test_size=0.25, random_state=42, stratify=y if classification else None
        )
    if classification and train_y.nunique() < 2:
        raise ValueError("The training window must contain multiple target classes.")
    if classification:
        baseline = DummyClassifier(strategy="most_frequent")
        candidate = LogisticRegression(max_iter=500)

        def metrics(pred):
            return {
                "accuracy": float(accuracy_score(test_y, pred)),
                "macro_f1": float(f1_score(test_y, pred, average="macro", zero_division=0)),
            }
    else:
        baseline = DummyRegressor(strategy="mean")
        candidate = LinearRegression()

        def metrics(pred):
            return {
                "mae": float(mean_absolute_error(test_y, pred)),
                "rmse": float(np.sqrt(mean_squared_error(test_y, pred))),
                "r2": float(r2_score(test_y, pred)),
            }

    baseline.fit(train_x, train_y)
    pipeline = make_pipeline(StandardScaler(), candidate)
    pipeline.fit(train_x, train_y)
    coefficients = np.abs(np.atleast_2d(candidate.coef_)).mean(axis=0)
    return {
        "method": type(candidate).__name__,
        "baseline": metrics(baseline.predict(test_x)),
        "metrics": metrics(pipeline.predict(test_x)),
        "train_count": len(train_x),
        "test_count": len(test_x),
        "parameters": {
            "features": features,
            "target": target,
            "order_by": order_by,
            "classification": classification,
        },
        "standardized_coefficient_magnitudes": dict(zip(features, map(float, coefficients))),
        "limitations": [
            "A duplicate-target check cannot detect all data leakage.",
            "Holdout scores apply to this dataset and split.",
        ],
    }


def compare(frame: pd.DataFrame, group: str, value: str) -> dict:
    if group not in frame or value not in frame or group == value:
        raise ValueError("Choose a grouping column and a numeric outcome.")
    data = frame[[group, value]].dropna()
    groups = list(data.groupby(group, sort=True, observed=True))
    if len(groups) != 2 or any(len(rows) < 3 for _, rows in groups):
        raise ValueError("The comparison requires two groups with at least three observations each.")
    arrays = [pd.to_numeric(rows[value], errors="raise").to_numpy() for _, rows in groups]
    test = stats.ttest_ind(*arrays, equal_var=False)
    return {
        "method": "Welch independent-samples t-test",
        "parameters": {"group": group, "measure": value},
        "groups": [
            {"label": str(name), "n": len(a), "mean": float(a.mean())} for (name, _), a in zip(groups, arrays)
        ],
        "p_value": float(test.pvalue) if np.isfinite(test.pvalue) else None,
        "limitations": [
            "The test assumes independent observations. Confounding can affect group differences."
        ],
    }
