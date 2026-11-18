from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.analytics import charts, statistics


class ForecastArgs(BaseModel):
    date: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=120)
    horizon: int = Field(ge=1, le=30)


class ModelArgs(BaseModel):
    features: list[str] = Field(min_length=1, max_length=15)
    target: str = Field(min_length=1, max_length=120)
    classification: bool
    order_by: str | None = Field(default=None, max_length=120)


class ComparisonArgs(BaseModel):
    group: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=120)


@dataclass(frozen=True)
class AnalyticalTool:
    name: str
    result_key: str
    arguments: type[BaseModel]
    calculate: Callable[..., dict[str, Any]]

    def execute(self, frame: pd.DataFrame, parameters: dict) -> dict:
        args = self.arguments.model_validate(parameters)
        return self.calculate(frame, **args.model_dump())


def build_chart(frame: pd.DataFrame, **arguments) -> dict:
    return charts.build(frame, charts.ChartSpec.model_construct(**arguments))


TOOLS: Mapping[str, AnalyticalTool] = MappingProxyType(
    {
        "forecast": AnalyticalTool("Forecast", "forecast", ForecastArgs, statistics.forecast),
        "model": AnalyticalTool("Model evaluation", "model", ModelArgs, statistics.model),
        "compare": AnalyticalTool("Statistical test", "comparison", ComparisonArgs, statistics.compare),
        "chart": AnalyticalTool("Chart builder", "chart", charts.ChartSpec, build_chart),
    }
)
