from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from typing import Literal, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import BaseModel, ConfigDict, Field

from app.agents import evidence, providers
from app.analytics import charts, roles, specialists, sql
from app.analytics.data import load
from app.analytics.tools import TOOLS
from app.core.config import settings
from app.db.checkpoints import checkpointer
from app.db.models import Version


class AnalysisStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=3, max_length=2000)
    version_id: str | None = Field(default=None, max_length=36)
    roles: list[str] = Field(default_factory=list, max_length=12)
    mode: Literal["analysis", "research", "forecast", "model", "compare", "chart"] = "analysis"
    approve_external: bool = False
    date: str = Field(default="", max_length=120)
    value: str = Field(default="", max_length=120)
    horizon: int = Field(default=6, ge=1, le=30)
    classification: bool = False
    features: list[str] = Field(default_factory=list, max_length=15)
    chart: charts.ChartSpec | None = None
    claims: list[evidence.ResearchClaim] = Field(default_factory=list, max_length=5)


class PlannedStep(AnalysisStep):
    require_approval: bool = False


class AnalysisInput(AnalysisStep):
    # Existing persisted job payloads contain queue metadata.
    model_config = ConfigDict(extra="ignore")
    steps: list[PlannedStep] = Field(default_factory=list, max_length=6)
    previous_job_id: str | None = Field(default=None, max_length=36)


class State(TypedDict, total=False):
    mode: str
    method: str
    query: str | None
    result: dict
    limitations: list[str]
    provider_usage: dict
    plan: dict


class JobCancelled(Exception):
    pass


def run(
    job_id: str,
    request: AnalysisStep,
    version: Version | None,
    progress: Callable[[str, dict], None],
    previous: dict | None = None,
) -> dict:
    end = monotonic() + settings().job_timeout - 4
    frame: pd.DataFrame | None = None
    profile = version.profile if version else {}
    privacy_hr = "hr" in request.roles

    def source_frame() -> pd.DataFrame:
        nonlocal frame
        if version is None:
            raise ValueError("Pick a dataset version for this analysis.")
        if frame is None:
            frame = load(version)
        return frame

    def step(label: str, **details):
        if monotonic() > end:
            raise ValueError("The analysis exceeded its time budget.")
        progress(label, details)

    def supervise(_state: State):
        step("Supervisor", roles=request.roles, mode=request.mode)
        return {"mode": request.mode, "limitations": [], "result": {}, "provider_usage": {}}

    def plan(state: State):
        step("Planning", mode=request.mode)
        limitations = []
        query = None
        method = "Local analytical planner"
        if request.mode != "research":
            observed = source_frame()
            assert version is not None
            step("Data ingestion", source_version=version.id, rows=len(observed))
            step("Data quality", transformations=version.transformations)
        if request.mode == "analysis" and not privacy_hr:
            config = settings()
            if request.approve_external and config.llm_provider != "none" and config.llm_api_key:
                try:
                    columns = [{"name": c["name"], "type": c["type"]} for c in profile["columns"]]
                    plan_value, usage = providers.plan(request.prompt, columns)
                    state = state | {"provider_usage": usage}
                    query = sql.validate(plan_value.sql, {"dataset"}) if plan_value.sql else None
                    method = f"{usage['provider']} planning"
                except (ValueError, KeyError, TypeError, IndexError, providers.httpx.HTTPError):
                    limitations.append("The model plan was unavailable or rejected. Local planning was used.")
            if not query:
                try:
                    query = sql.draft(request.prompt, source_frame())
                except ValueError:
                    if previous and previous.get("objective"):
                        try:
                            query = sql.draft(f"{request.prompt} {previous['objective']}", source_frame())
                            step("Previous analysis context", source_job=previous["id"])
                        except ValueError:
                            pass
                    if not query:
                        limitations.append(
                            "No aggregate query could be inferred. Role-specific metrics are shown when available."
                        )
        return {
            "query": query,
            "method": method,
            "limitations": limitations,
            "provider_usage": state["provider_usage"],
            "plan": {
                "objective": request.prompt,
                "roles": request.roles,
                "mode": request.mode,
                "previous_analysis": previous,
            },
        }

    def analyze(state: State):
        frame = source_frame()
        step("Statistical analysis")
        role_ids = ["hr"] if privacy_hr else request.roles
        with ThreadPoolExecutor(max_workers=min(3, max(1, len(role_ids)))) as pool:
            groups = pool.map(
                lambda role: (
                    specialists.calculate(role, frame, request.prompt)
                    or [roles.calculate(role, frame, profile, request.prompt)]
                ),
                role_ids,
            )
            metrics = [finding for group in groups for finding in group]
        response = {"role_findings": metrics}
        if not privacy_hr:
            response["profile"] = profile
        if state.get("query"):
            step("SQL", query=state["query"])
            try:
                response["query"] = sql.execute(state["query"], {"dataset": frame})
            except ValueError as exc:
                return {"result": response, "limitations": state["limitations"] + [str(exc)]}
        return {"result": response}

    def specialized(_state: State):
        if request.mode == "research":
            step("Research", provider="Brave Search")
            if not request.approve_external:
                raise ValueError("Approve sending the research query to the provider.")
            sources = providers.research(request.prompt)
            step("Source retrieval", candidates=len(sources))
            sources, claims = evidence.verify(sources, request.claims)
            return {
                "result": {"evidence": sources, "claim_checks": claims},
                "limitations": [
                    "Claim checks apply to explicit percentages near the supplied subject phrase in readable sources.",
                    "Review citations for scope, date, units and publisher independence before relying on a claim.",
                ],
            }
        if privacy_hr:
            raise ValueError("HR workflows currently support aggregate turnover analysis only.")
        frame = source_frame()
        tool = TOOLS[request.mode]
        if request.mode == "forecast":
            metric = request.value or sql.column_for(
                request.prompt, list(frame.select_dtypes(include="number"))
            )
            dates = request.date or next(
                (c for c in frame if c.casefold() in {"date", "month", "week", "timestamp"}), ""
            )
            if not dates or not metric:
                raise ValueError("Choose a date field and a separate numeric measure.")
            parameters = {"date": dates, "value": metric, "horizon": request.horizon}
        elif request.mode == "model":
            parameters = {
                "features": request.features,
                "target": request.value,
                "classification": request.classification,
                "order_by": request.date or None,
            }
        elif request.mode == "compare":
            parameters = {"group": request.date, "value": request.value}
        else:
            if request.chart is None:
                raise ValueError("Select chart fields.")
            parameters = request.chart.model_dump()
        step(tool.name, **parameters)
        return {"result": {tool.result_key: tool.execute(frame, parameters)}}

    def visualize(state: State):
        step("Visualization")
        result = state["result"]
        query = result.get("query")
        if query and query["rows"] and len(query["columns"]) == 2:
            x, y = query["columns"]
            if all(isinstance(row[y], (int, float)) for row in query["rows"]):
                return {
                    "result": result
                    | {
                        "chart": {
                            "type": "bar",
                            "x": x,
                            "y": y,
                            "rows": query["rows"][:30],
                            "method": "Validated SQL result",
                            "truncated": len(query["rows"]) > 30,
                        }
                    }
                }
        if "forecast" in result:
            data = result["forecast"]
            return {
                "result": result
                | {
                    "chart": {
                        "type": "line",
                        "x": "date",
                        "y": "value",
                        "rows": data["observed"] + data["predictions"],
                        "method": data["method"],
                    }
                }
            }
        return {}

    def interpret(state: State):
        step("Insights")
        result = state["result"]
        computed = sum(item["status"] == "computed" for item in result.get("role_findings", []))
        summaries = {
            "analysis": f"{computed} role-specific metric groups computed.",
            "forecast": "Forecast estimates are based on an evaluated chronological holdout.",
            "model": "Baseline and candidate metrics are measured on held-out rows.",
            "research": f"{len(result.get('evidence', []))} candidate sources were retrieved.",
            "chart": "Chart values were computed from the selected dataset version.",
            "compare": "The group comparison uses an independent-samples statistical test.",
        }
        return {
            "result": result
            | {
                "summary": summaries[request.mode],
                "hypotheses": [],
                "assumptions": ["Field definitions and units match the workflow inputs."] if version else [],
                "recommendations": ["Review flagged data limitations before applying the findings."],
            }
        }

    def validate(state: State):
        import json

        step("Validation")
        result = state["result"]
        for key in ("forecast", "model", "comparison"):
            if key in result:
                state["limitations"].extend(result[key]["limitations"])
        if result.get("query", {}).get("truncated"):
            state["limitations"].append("SQL output was limited to 500 rows.")
        if privacy_hr:
            state["limitations"].append(
                "The HR workflow reports aggregate results only. Other role analyses were skipped."
            )
        source = (
            {
                "dataset_id": version.dataset_id,
                "version_id": version.id,
                "version": version.number,
                "sha256": version.sha256,
                "transformations": version.transformations,
            }
            if version
            else None
        )
        final = result | {
            "source": source,
            "plan": state["plan"],
            "provider_usage": state["provider_usage"],
            "limitations": state["limitations"],
            "method": state["method"],
            "validated": True,
            "parameters": request.model_dump(mode="json", exclude={"approve_external"}),
        }
        json.dumps(final, allow_nan=False)
        return {"result": final}

    graph = StateGraph(State)
    for name, function in (
        ("supervisor", supervise),
        ("planner", plan),
        ("analysis", analyze),
        ("specialized", specialized),
        ("visualize", visualize),
        ("insights", interpret),
        ("validate", validate),
    ):
        graph.add_node(name, function)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "planner")
    graph.add_conditional_edges(
        "planner", lambda s: s["mode"] == "analysis", {True: "analysis", False: "specialized"}
    )
    graph.add_edge("analysis", "visualize")
    graph.add_edge("specialized", "visualize")
    graph.add_edge("visualize", "insights")
    graph.add_edge("insights", "validate")
    graph.add_edge("validate", END)
    options = {"configurable": {"thread_id": job_id}, "recursion_limit": 10}
    with checkpointer() as checkpoint, tracing_context(enabled=False):
        compiled = graph.compile(checkpointer=checkpoint)
        snapshot = compiled.get_state(options)
        if not snapshot.created_at:
            return compiled.invoke({}, options)["result"]
        if snapshot.next:
            return compiled.invoke(None, options)["result"]
        return snapshot.values["result"]
