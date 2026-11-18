from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.analytics.data import json_rows


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "pie", "scatter", "histogram", "heatmap", "kpi", "table"] = "bar"
    x: str = Field(min_length=1, max_length=120)
    y: str = Field(default="", max_length=120)
    aggregation: Literal["sum", "mean", "count"] = "sum"


def build(frame: pd.DataFrame, spec: ChartSpec) -> dict:
    x, y, kind = spec.x, spec.y, spec.type
    numeric = set(frame.select_dtypes(include="number").columns)
    if x not in frame or (y and y not in frame):
        raise ValueError("Choose columns from the selected dataset.")
    if kind == "table":
        return {
            "type": kind,
            "columns": list(frame.columns)[:12],
            "rows": json_rows(frame.iloc[:, :12], 100),
            "method": "First 100 observations",
        }
    if kind == "heatmap":
        fields = [column for column in frame if column in numeric][:12]
        if len(fields) < 2:
            raise ValueError("A correlation heatmap needs two numeric columns.")
        correlation = frame[fields].corr()
        return {
            "type": kind,
            "columns": fields,
            "rows": json_rows(correlation.reset_index(names="column")),
            "method": "Pearson correlation, pairwise complete observations",
        }
    if kind == "histogram":
        if x not in numeric or frame[x].dropna().empty:
            raise ValueError("Choose a numeric column with observations.")
        counts, edges = np.histogram(frame[x].dropna().to_numpy(dtype=float), bins=12)
        return {
            "type": kind,
            "x": "bin",
            "y": "count",
            "rows": [
                {"bin": f"{edges[i]:.3g} to {edges[i + 1]:.3g}", "count": int(count)}
                for i, count in enumerate(counts)
            ],
            "method": f"Histogram of {x} with twelve equal-width bins",
        }
    if kind == "scatter":
        if x == y or x not in numeric or y not in numeric:
            raise ValueError("Choose two different numeric columns.")
        series = frame[[x, y]].dropna()
        return {
            "type": kind,
            "x": x,
            "y": y,
            "rows": json_rows(series, 300),
            "method": "First 300 complete pairs",
        }
    if kind == "kpi":
        if x not in numeric and spec.aggregation != "count":
            raise ValueError("Choose a numeric measure or Count.")
        value = getattr(frame[x], spec.aggregation)()
        return {
            "type": kind,
            "x": "metric",
            "y": "value",
            "rows": [{"metric": x, "value": float(value) if pd.notna(value) else None}],
            "method": spec.aggregation,
        }
    if spec.aggregation == "count":
        series = frame.groupby(x, sort=True, observed=True).size()
    elif y in numeric and x != y:
        grouped = frame.groupby(x, sort=True, observed=True)[y]
        series = grouped.sum(min_count=1) if spec.aggregation == "sum" else grouped.mean()
    else:
        raise ValueError("Choose a numeric measure distinct from the grouping column, or Count.")
    if kind == "pie" and (series < 0).any():
        raise ValueError("Pie charts require nonnegative group values.")
    limited = series.head(100) if kind == "line" else series.nlargest(12 if kind == "pie" else 30)
    return {
        "type": kind,
        "x": "group",
        "y": "value",
        "rows": json_rows(limited.rename("value").rename_axis("group").reset_index()),
        "method": f"{spec.aggregation} of {y or 'rows'} grouped by {x}",
        "truncated": len(limited) < len(series),
    }


def plotly_document(chart: dict) -> dict:
    import plotly.graph_objects as go

    kind = chart["type"]
    rows = chart["rows"]
    x, y = chart.get("x", "group"), chart.get("y", "value")
    labels = [row.get(x) for row in rows]
    values = [row.get(y) for row in rows]
    if kind == "line":
        series = [go.Scatter(x=labels, y=values, mode="lines", name=y)]
        for bound in ("lower", "upper"):
            if any(bound in row for row in rows):
                series.append(
                    go.Scatter(
                        x=labels,
                        y=[row.get(bound) for row in rows],
                        mode="lines",
                        name=bound,
                        line={"dash": "dot"},
                    )
                )
    elif kind == "pie":
        series = [go.Pie(labels=labels, values=values)]
    elif kind == "scatter":
        series = [go.Scatter(x=labels, y=values, mode="markers")]
    elif kind == "heatmap":
        columns = chart["columns"]
        series = [
            go.Heatmap(
                x=columns,
                y=[row["column"] for row in rows],
                z=[[row.get(column) for column in columns] for row in rows],
                zmin=-1,
                zmax=1,
            )
        ]
    elif kind == "table":
        columns = chart["columns"]
        series = [
            go.Table(
                header={"values": columns},
                cells={"values": [[row.get(column) for row in rows] for column in columns]},
            )
        ]
    elif kind == "kpi" and values and values[0] is not None:
        series = [go.Indicator(mode="number", value=values[0])]
    else:
        series = [go.Bar(x=labels, y=values)]
    return go.Figure(
        data=series, layout={"title": {"text": chart.get("title", chart["method"])}, "template": None}
    ).to_plotly_json()
