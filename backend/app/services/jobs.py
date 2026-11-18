from contextlib import contextmanager
from datetime import timedelta
from time import sleep
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import OperationalError

from app.agents.workflow import AnalysisInput, JobCancelled, run
from app.analytics import data
from app.core.config import settings
from app.core.observability import jobs, log
from app.core.task_queue import celery
from app.db.models import (
    Artifact,
    Dataset,
    Job,
    Membership,
    Project,
    ResetToken,
    Schedule,
    Session,
    Version,
    now,
)
from app.db.session import SessionLocal
from app.services import reports, storage
from app.services.local_tasks import LocalExecutor

_executor: LocalExecutor | None = None
LOCAL_INTERRUPTED = "The development server stopped before this job finished. Retry the job."


def job_payload(payload: dict) -> dict:
    return {**payload, "_runner": settings().task_backend}


def fail_pending(message: str, job_id: str | None = None):
    with SessionLocal() as db:
        pending = update(Job).where(
            Job.status.in_(["queued", "running"]), Job.payload["_runner"].as_string() == "local"
        )
        if job_id is not None:
            pending = pending.where(Job.id == job_id)
        db.execute(
            pending.values(status="failed", error=message).execution_options(synchronize_session=False)
        )
        db.commit()


@contextmanager
def local_execution():
    global _executor
    if settings().task_backend != "local":
        yield
        return

    fail_pending(LOCAL_INTERRUPTED)
    _executor = LocalExecutor()
    try:
        yield
    finally:
        _executor.close()
        _executor = None


def run_local(job_id: str):
    try:
        for attempt in range(3):
            try:
                execute_job(job_id)
                return
            except OperationalError:
                if attempt == 2:
                    raise
                sleep(0.15 * (attempt + 1))
    except Exception as exc:  # noqa: BLE001
        log("local_job_failed", job_id=job_id, error_type=type(exc).__name__)
        fail_pending(
            "The job could not be processed. Retry after checking the source or local database.", job_id
        )


def enqueue(job_id: str):
    if settings().task_backend == "local":
        executor = _executor
        if executor is None or not executor.submit(run_local, job_id):
            fail_pending("The development worker is unavailable or its queue is full. Retry shortly.", job_id)
        return

    try:
        execute.delay(job_id)
    except Exception as exc:  # noqa: BLE001
        log("job_dispatch_failed", job_id=job_id, error_type=type(exc).__name__)


def persist_dataset(db, project_id: str, name: str, source: str, frame):
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update()).scalar_one()
    count = db.scalar(select(func.count()).select_from(Dataset).where(Dataset.project_id == project_id))
    if count >= settings().max_datasets:
        raise ValueError("This project reached its dataset quota.")
    dataset = Dataset(project_id=project_id, name=name, source=source)
    db.add(dataset)
    db.flush()
    version = data.save_version(dataset, frame, 1)
    db.add(version)
    db.flush()
    return dataset, version


@celery.task(name="analyst.execute", autoretry_for=(OperationalError,), retry_backoff=True, max_retries=2)
def execute(job_id: str):
    execute_job(job_id)


def execute_job(job_id: str):
    with SessionLocal() as db:
        claimed = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "queued")
            .values(
                status="running",
                started_at=now(),
                attempt=Job.attempt + 1,
                error=None,
            )
            .returning(Job.attempt)
        ).first()
        db.commit()
        if not claimed:
            return
        attempt = claimed[0]
        job = db.get(Job, job_id)
        steps = list(job.trace)

        def progress(label, details):
            steps.append({"step": label, "details": details, "at": now().isoformat() + "Z"})
            changed = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "running", Job.attempt == attempt)
                .values(trace=list(steps))
                .execution_options(synchronize_session=False)
            ).rowcount
            db.commit()
            if not changed:
                raise JobCancelled()

        object_key = None
        try:
            project = db.get(Project, job.project_id)
            member = db.scalar(
                select(Membership).where(
                    Membership.workspace_id == project.workspace_id, Membership.user_id == job.requested_by
                )
            )
            if member is None or member.role == "viewer":
                raise ValueError("Workspace write access has been removed.")
            if job.kind == "analysis":
                request = AnalysisInput.model_validate(job.payload)
                version = db.get(Version, request.version_id) if request.version_id else None
                previous = db.get(Job, request.previous_job_id) if request.previous_job_id else None
                context = (
                    {
                        "id": previous.id,
                        "summary": previous.result["summary"],
                        "objective": previous.result["plan"]["objective"],
                    }
                    if previous
                    else None
                )
                result = run(f"{job_id}:{job.checkpoint_epoch}", request, version, progress, context)
            elif job.kind == "report":
                progress("Report generation", {"format": job.payload["format"]})
                source = db.get(Job, job.payload["analysis_id"])
                format_name = job.payload["format"]
                content = reports.generate(format_name, job.payload["title"], source.result)
                object_key = f"reports/{job.project_id}/{uuid4()}.{format_name}"
                storage.put(object_key, content)
                artifact = Artifact(
                    project_id=job.project_id, job_id=job.id, format=format_name, object_key=object_key
                )
                db.add(artifact)
                db.flush()
                result = {"artifact_id": artifact.id, "format": format_name, "title": job.payload["title"]}
            elif job.kind == "import":
                progress("Reading source", {"name": job.payload["filename"]})
                frame = data.parse(
                    storage.read(job.payload["key"]), job.payload["filename"], job.payload.get("table")
                )
                progress("Profiling", {"rows": len(frame)})
                dataset, version = persist_dataset(
                    db, job.project_id, job.payload["filename"], "upload", frame
                )
                object_key = version.object_key
                result = {"dataset_id": dataset.id, "version_id": version.id, "rows": len(frame)}
            else:
                raise ValueError("Unknown job kind.")
            changed = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "running", Job.attempt == attempt)
                .values(status="completed", result=result)
                .execution_options(synchronize_session=False)
            ).rowcount
            if not changed:
                raise JobCancelled()
            db.commit()
            jobs.labels(job.kind, "completed").inc()
        except JobCancelled:
            db.rollback()
            if object_key:
                storage.remove(object_key)
        except OperationalError:
            db.rollback()
            if object_key:
                storage.remove(object_key)
            db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "running", Job.attempt == attempt)
                .values(status="queued")
            )
            db.commit()
            raise
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            if object_key:
                storage.remove(object_key)
            message = (
                str(exc) if type(exc) is ValueError else "Processing failed. Check the source and try again."
            )
            if isinstance(exc, SoftTimeLimitExceeded):
                message = "The job exceeded its time budget."
            db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "running", Job.attempt == attempt)
                .values(status="failed", error=message[:500])
            )
            db.commit()
            jobs.labels(job.kind, "failed").inc()
            log("job_failed", job_id=job_id, error_type=type(exc).__name__)
        finally:
            # Staged uploads remain available to retry a canceled or failed import.
            if job.kind == "import":
                state = db.scalar(select(Job.status).where(Job.id == job_id))
                if state == "completed":
                    storage.remove(job.payload["key"])


@celery.task(name="analyst.dispatch_due")
def dispatch_due():
    current = now()
    cutoff = current - timedelta(seconds=settings().job_timeout + 15)
    with SessionLocal() as db:
        db.execute(delete(Session).where(Session.expires_at < current))
        db.execute(delete(ResetToken).where(ResetToken.expires_at < current))
        db.execute(
            update(Job)
            .where(Job.status == "running", Job.started_at < cutoff, Job.attempt >= 3)
            .values(status="failed", error="The worker could not finish this job after three attempts.")
        )
        db.execute(
            update(Job)
            .where(Job.status == "running", Job.started_at < cutoff, Job.attempt < 3)
            .values(status="queued")
        )
        schedules = db.scalars(
            select(Schedule)
            .where(Schedule.enabled.is_(True), Schedule.next_at <= current)
            .order_by(Schedule.next_at)
            .limit(40)
            .with_for_update(skip_locked=True)
        ).all()
        for schedule in schedules:
            project = db.scalar(select(Project).where(Project.id == schedule.project_id).with_for_update())
            member = db.scalar(
                select(Membership).where(
                    Membership.workspace_id == project.workspace_id, Membership.user_id == schedule.user_id
                )
            )
            if not member or member.role == "viewer":
                schedule.enabled = False
                continue
            schedule.next_at = current + timedelta(minutes=schedule.interval_minutes)
            active = db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.project_id == project.id, Job.status.in_(["queued", "running"]))
            )
            if active < settings().max_active_jobs:
                db.add(
                    Job(
                        project_id=project.id,
                        requested_by=schedule.user_id,
                        kind="analysis",
                        payload=schedule.payload,
                    )
                )
        db.commit()
        ready = db.scalars(
            select(Job.id).where(Job.status == "queued").order_by(Job.created_at).limit(100)
        ).all()
    for job_id in ready:
        enqueue(job_id)
