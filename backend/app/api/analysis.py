import json
from datetime import timedelta
from time import monotonic, sleep
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.agents import providers
from app.agents.workflow import AnalysisInput
from app.analytics import data, sql
from app.api.common import job_for, version_for
from app.core.config import settings
from app.core.security import DB, Actor, audit, limiter, project_for
from app.db.models import Artifact, Dashboard, Job, Project, Query, Schedule, now
from app.db.session import SessionLocal
from app.services import jobs, reports, storage

router = APIRouter(prefix="/projects/{project_id}", tags=["analysis"])
TERMINAL = {"completed", "failed", "canceled"}


class SqlRequest(BaseModel):
    version_id: str = Field(max_length=36)
    join_version_id: str | None = Field(default=None, max_length=36)
    sql: str = Field(default="", max_length=12_000)
    prompt: str = Field(default="", max_length=2000)
    title: str = Field(default="", max_length=100)
    approve_external: bool = False


class TitledResult(BaseModel):
    title: str = Field(min_length=2, max_length=100, pattern=r"\S")


class SaveDashboard(TitledResult):
    job_id: str | None = Field(default=None, max_length=36)
    job_ids: list[str] = Field(default_factory=list, max_length=6)


class ReportInput(TitledResult):
    job_id: str = Field(max_length=36)
    format: Literal["pdf", "xlsx", "pptx", "csv", "md", "html"]


class ScheduleInput(AnalysisInput):
    interval_minutes: int = Field(ge=15, le=43_200)
    approved: bool


def job_data(job: Job, full=False) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "trace": job.trace,
        "error": job.error,
        "attempt": job.attempt,
        "created_at": job.created_at.isoformat() + "Z",
        "prompt": job.payload.get("prompt") or job.payload.get("title") or job.payload.get("filename"),
        "result": job.result if full else None,
        "has_chart": bool(job.result and job.result.get("chart")),
    }


def reserve_job(db, project: Project):
    db.execute(select(Project.id).where(Project.id == project.id).with_for_update())
    count = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.project_id == project.id, Job.status.in_(["queued", "running"]))
    )
    if count >= settings().max_active_jobs:
        raise HTTPException(429, "This project has reached its active job limit.")


def create_job(db, project, user, kind, payload):
    limiter(f"jobs:{user.id}", 40, 60)
    reserve_job(db, project)
    job = Job(project_id=project.id, requested_by=user.id, kind=kind, payload=payload)
    db.add(job)
    db.flush()
    audit(db, user, project.workspace_id, f"{kind}.queued", job.id)
    db.commit()
    jobs.enqueue(job.id)
    db.refresh(job)
    return job_data(job, True)


def check_analysis(db, project: Project, body: AnalysisInput):
    if not body.roles:
        body.roles = project.roles
    if len(set(body.roles)) != len(body.roles) or not set(body.roles) <= set(project.roles):
        raise HTTPException(422, "Select distinct roles assigned to this project.")
    if body.previous_job_id:
        prior = job_for(db, project.id, body.previous_job_id)
        if prior.status != "completed" or prior.kind != "analysis":
            raise HTTPException(422, "Select a completed analysis for context.")
        if not body.version_id and prior.result.get("source"):
            body.version_id = prior.result["source"]["version_id"]
    if body.mode == "research":
        if not settings().research_api_key:
            raise HTTPException(503, "External research currently has no configured provider.")
        if not body.approve_external or body.version_id:
            raise HTTPException(
                422, "Approve sharing the research query and run it without a dataset selection."
            )
    else:
        if not body.version_id:
            raise HTTPException(422, "Select a dataset version.")
        version_for(db, project.id, body.version_id)
    if (
        body.mode == "analysis"
        and "forecast" in body.prompt.casefold()
        and body.mode != "research"
        and "hr" not in body.roles
    ):
        body.mode = "forecast"


@router.post("/analyses", status_code=202)
def analyze(project_id: str, body: AnalysisInput, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    check_analysis(db, project, body)
    return create_job(db, project, user, "analysis", body.model_dump())


@router.get("/jobs")
def list_jobs(
    project_id: str, db: DB, user: Actor, kind: Literal["analysis", "report", "import"] | None = None
):
    project_for(db, user, project_id)
    query = select(Job).where(Job.project_id == project_id)
    if kind:
        query = query.where(Job.kind == kind)
    return [
        job_data(job, full=job.kind == "report")
        for job in db.scalars(query.order_by(Job.created_at.desc()).limit(100))
    ]


@router.get("/jobs/{job_id}")
def get_job(project_id: str, job_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    return job_data(job_for(db, project_id, job_id), True)


@router.get("/jobs/{job_id}/events")
def stream(project_id: str, job_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    job_for(db, project_id, job_id)
    db.close()

    def events():
        until = monotonic() + settings().job_timeout + 10
        last = ""
        while monotonic() < until:
            with SessionLocal() as fresh:
                try:
                    project_for(fresh, user, project_id)
                    job = job_for(fresh, project_id, job_id)
                except HTTPException:
                    return
                status = job.status
                payload = json.dumps(job_data(job, full=True), separators=(",", ":"))
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if status in TERMINAL:
                return
            sleep(0.7)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/jobs/{job_id}/cancel")
def cancel(project_id: str, job_id: str, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    job_for(db, project_id, job_id)
    changed = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(["queued", "running"]))
        .values(status="canceled", error="Canceled in the workspace.")
    ).rowcount
    if not changed:
        raise HTTPException(409, "Only active jobs can be canceled.")
    audit(db, user, project.workspace_id, "job.canceled", job_id)
    db.commit()
    return job_data(db.get(Job, job_id), True)


@router.post("/jobs/{job_id}/retry")
def retry(project_id: str, job_id: str, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    reserve_job(db, project)
    job = job_for(db, project_id, job_id)
    if job.status not in {"failed", "canceled"}:
        raise HTTPException(409, "Only failed or canceled jobs can be retried.")
    if job.requested_by != user.id:
        raise HTTPException(403, "Only the original requester can retry this job.")
    job.status, job.error, job.trace = "queued", None, []
    job.checkpoint_epoch += 1
    audit(db, user, project.workspace_id, "job.retried", job_id)
    db.commit()
    jobs.enqueue(job_id)
    db.refresh(job)
    return job_data(job, True)


@router.post("/sql/draft")
def draft_query(project_id: str, body: SqlRequest, db: DB, user: Actor):
    project_for(db, user, project_id, write=True)
    limiter(f"sql:{user.id}", 60, 60)
    version = version_for(db, project_id, body.version_id)
    config = settings()
    if body.approve_external and config.llm_provider != "none" and config.llm_api_key:
        try:
            schema = [{"name": c["name"], "type": c["type"]} for c in version.profile["columns"]]
            draft, usage = providers.plan(body.prompt, schema)
            if draft.sql:
                return {
                    "sql": sql.validate(draft.sql, {"dataset"}),
                    "explanation": "Validate and inspect before execution.",
                    "provider_usage": usage,
                }
        except (ValueError, TypeError, KeyError, IndexError, httpx.HTTPError):
            pass
    try:
        return {
            "sql": sql.draft(body.prompt, data.load(version)),
            "explanation": "Aggregate derived from the request.",
        }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def query_data(query: Query) -> dict:
    return {
        "id": query.id,
        "title": query.title,
        "sql": query.sql,
        "version_id": query.version_id,
        "result": query.result,
        "created_at": query.created_at.isoformat() + "Z",
    }


@router.post("/sql")
def execute_query(project_id: str, body: SqlRequest, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    limiter(f"sql:{user.id}", 60, 60)
    version = version_for(db, project_id, body.version_id)
    secondary = version_for(db, project_id, body.join_version_id) if body.join_version_id else None
    frames = {"dataset": data.load(version)}
    if secondary:
        frames["dataset_b"] = data.load(secondary)
    try:
        result = sql.execute(body.sql, frames)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    result["source_versions"] = [v.id for v in (version, secondary) if v]
    query = Query(
        project_id=project_id,
        version_id=version.id,
        title=body.title.strip() or "Untitled query",
        sql=result["sql"],
        result=result,
    )
    db.add(query)
    db.flush()
    audit(db, user, project.workspace_id, "query.executed", query.id)
    db.commit()
    return query_data(query)


@router.get("/sql")
def query_history(project_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    queries = db.scalars(
        select(Query).where(Query.project_id == project_id).order_by(Query.created_at.desc()).limit(25)
    )
    return [query_data(query) for query in queries]


@router.get("/sql/{query_id}/export")
def download_result(project_id: str, query_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    query = db.scalar(select(Query).where(Query.project_id == project_id, Query.id == query_id))
    if not query:
        raise HTTPException(404, "Query not found.")
    return Response(
        reports.output_csv(query.result["columns"], query.result["rows"]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="query-results.csv"'},
    )


def dashboard_data(row: Dashboard) -> dict:
    return {"id": row.id, "title": row.title, "job_id": row.job_id, "chart": row.chart}


@router.get("/dashboards")
def dashboards(project_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    rows = db.scalars(
        select(Dashboard)
        .where(Dashboard.project_id == project_id)
        .order_by(Dashboard.created_at.desc())
        .limit(50)
    )
    return [dashboard_data(row) for row in rows]


@router.post("/dashboards", status_code=201)
def save_dashboard(project_id: str, body: SaveDashboard, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    ids = body.job_ids or ([body.job_id] if body.job_id else [])
    if not ids or len(set(ids)) != len(ids) or any(len(item) != 36 for item in ids):
        raise HTTPException(422, "Select up to six distinct analysis charts.")
    panels = []
    for job_id in ids:
        job = job_for(db, project_id, job_id)
        if job.status != "completed" or job.kind != "analysis" or not job.result.get("chart"):
            raise HTTPException(422, "Each selection must be a completed analysis with a chart.")
        panels.append(
            job.result["chart"] | {"source": job.result.get("source"), "title": job.payload["prompt"][:100]}
        )
    chart = panels[0] if len(panels) == 1 else {"panels": panels}
    row = Dashboard(project_id=project_id, job_id=ids[0], title=body.title.strip(), chart=chart)
    db.add(row)
    db.flush()
    audit(db, user, project.workspace_id, "dashboard.saved", row.id)
    db.commit()
    return dashboard_data(row)


@router.get("/dashboards/{dashboard_id}/export")
def export_dashboard(project_id: str, dashboard_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    record = db.scalar(
        select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.project_id == project_id)
    )
    if not record:
        raise HTTPException(404, "Dashboard not found.")
    if "panels" in record.chart:
        rows = [
            {"Panel": panel["title"]} | {f"Data: {column}": value for column, value in entry.items()}
            for panel in record.chart["panels"]
            for entry in panel["rows"]
        ]
        columns = list(dict.fromkeys(column for entry in rows for column in entry))
    else:
        rows = record.chart.get("rows", [])
        columns = list(rows[0]) if rows else []
    return Response(
        reports.output_csv(columns, rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="dashboard-data.csv"'},
    )


@router.post("/reports", status_code=202)
def report(project_id: str, body: ReportInput, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    job = job_for(db, project_id, body.job_id)
    if job.status != "completed" or job.kind != "analysis":
        raise HTTPException(422, "Select a completed analysis.")
    return create_job(
        db,
        project,
        user,
        "report",
        {"analysis_id": job.id, "title": body.title.strip(), "format": body.format},
    )


@router.get("/artifacts/{artifact_id}")
def download_report(project_id: str, artifact_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    item = db.scalar(select(Artifact).where(Artifact.id == artifact_id, Artifact.project_id == project_id))
    if not item:
        raise HTTPException(404, "Artifact not found.")
    return Response(
        storage.read(item.object_key),
        media_type=reports.FORMATS[item.format],
        headers={
            "Content-Disposition": f'attachment; filename="analysis-report.{item.format}"',
            "Content-Security-Policy": "sandbox",
        },
    )


def schedule_data(row: Schedule) -> dict:
    return {
        "id": row.id,
        "prompt": row.payload["prompt"],
        "interval_minutes": row.interval_minutes,
        "next_at": row.next_at.isoformat() + "Z",
        "enabled": row.enabled,
    }


@router.get("/schedules")
def schedules(project_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    return [
        schedule_data(row)
        for row in db.scalars(
            select(Schedule)
            .where(Schedule.project_id == project_id)
            .order_by(Schedule.created_at.desc())
            .limit(50)
        )
    ]


@router.post("/schedules", status_code=201)
def add_schedule(project_id: str, body: ScheduleInput, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    if settings().eager:
        raise HTTPException(503, "Scheduling requires the Redis worker and scheduler.")
    if not body.approved or body.approve_external or body.mode == "research":
        raise HTTPException(422, "Approve recurring local analysis before scheduling.")
    check_analysis(db, project, body)
    row = Schedule(
        project_id=project_id,
        user_id=user.id,
        payload=body.model_dump(exclude={"interval_minutes", "approved"}),
        interval_minutes=body.interval_minutes,
        next_at=now() + timedelta(minutes=body.interval_minutes),
    )
    db.add(row)
    db.flush()
    audit(db, user, project.workspace_id, "schedule.created", row.id)
    db.commit()
    return schedule_data(row)


@router.delete("/schedules/{schedule_id}", status_code=204)
def stop_schedule(project_id: str, schedule_id: str, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    schedule = db.scalar(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.project_id == project_id)
    )
    if not schedule:
        raise HTTPException(404, "Schedule not found.")
    schedule.enabled = False
    audit(db, user, project.workspace_id, "schedule.stopped", schedule.id)
    db.commit()
