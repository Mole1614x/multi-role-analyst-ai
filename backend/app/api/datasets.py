from pathlib import PurePath
from typing import Annotated
from uuid import uuid4
from zipfile import BadZipFile

import pyarrow as pa
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.analytics import data
from app.api.common import version_for
from app.core.config import settings
from app.core.security import DB, Actor, audit, limiter, project_for
from app.db.models import Dataset, Job, Version
from app.services import jobs, storage

router = APIRouter(prefix="/projects/{project_id}", tags=["data"])


class Cleaning(BaseModel):
    steps: list[data.Transformation] = Field(min_length=1, max_length=15)
    preview: bool = False


class Connector(BaseModel):
    source: str = Field(max_length=100)
    table: str = Field(min_length=1, max_length=140)


def item(version: Version) -> dict:
    return {
        "id": version.id,
        "dataset_id": version.dataset_id,
        "number": version.number,
        "sha256": version.sha256,
        "parent_id": version.parent_id,
        "profile": version.profile,
        "transformations": version.transformations,
        "created_at": version.created_at.isoformat() + "Z",
    }


@router.get("/datasets")
def datasets(project_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    rows = db.execute(
        select(Dataset, Version)
        .join(Version, Version.dataset_id == Dataset.id)
        .where(Dataset.project_id == project_id)
        .order_by(Dataset.created_at.desc(), Version.number.desc())
    )
    output: dict[str, dict] = {}
    for dataset, version in rows:
        output.setdefault(
            dataset.id, {"id": dataset.id, "name": dataset.name, "source": dataset.source, "versions": []}
        )["versions"].append(item(version))
    return list(output.values())


def import_frame(project, db, user, frame, name, source):
    version = None
    try:
        dataset, version = jobs.persist_dataset(db, project.id, name, source, frame)
        audit(db, user, project.workspace_id, "dataset.imported", dataset.id)
        db.commit()
    except Exception:
        db.rollback()
        if version:
            storage.remove(version.object_key)
        raise
    return {"id": dataset.id, "name": dataset.name, "versions": [item(version)]}


@router.post("/datasets", status_code=201)
def upload(
    project_id: str,
    db: DB,
    user: Actor,
    response: Response,
    file: Annotated[UploadFile, File()],
    table: Annotated[str, Form(max_length=120)] = "",
    background: Annotated[bool, Form()] = False,
):
    project = project_for(db, user, project_id, write=True)
    limiter(f"imports:{user.id}", 45, 60)
    config = settings()
    name = PurePath((file.filename or "").replace("\\", "/")).name
    if (
        not name
        or len(name) > 220
        or PurePath(name).suffix.lower() not in data.FORMAT_NAMES
        or any(ord(c) < 32 for c in name)
    ):
        raise HTTPException(422, "Choose a CSV, Excel, JSON, Parquet, SQLite, or DuckDB file.")
    content = file.file.read(config.max_upload_bytes + 1)
    if not content:
        raise HTTPException(422, "The uploaded file is empty.")
    if len(content) > config.max_upload_bytes:
        raise HTTPException(413, f"The file exceeds {config.max_upload_bytes:,} bytes.")
    if config.task_backend == "local" or (
        config.task_backend == "celery" and (background or len(content) > 2_000_000)
    ):
        from app.api.analysis import reserve_job

        reserve_job(db, project)
        key = f"staging/{project_id}/{uuid4()}"
        storage.put(key, content)
        try:
            job = Job(
                project_id=project_id,
                requested_by=user.id,
                kind="import",
                payload=jobs.job_payload({"key": key, "filename": name, "table": table or None}),
            )
            db.add(job)
            db.flush()
            audit(db, user, project.workspace_id, "import.queued", job.id)
            db.commit()
        except Exception:
            storage.remove(key)
            raise
        jobs.enqueue(job.id)
        if config.task_backend == "local":
            response.status_code = 202
        return {"job_id": job.id}
    try:
        frame = data.parse(content, name, table or None)
        return import_frame(project, db, user, frame, name, "upload")
    except ValueError as exc:
        raise HTTPException(
            422, str(exc) if type(exc) is ValueError else "The file has an invalid structure."
        ) from exc
    except (
        OSError,
        TypeError,
        KeyError,
        OverflowError,
        data.sqlite3.Error,
        data.duckdb.Error,
        pa.ArrowException,
        BadZipFile,
    ) as exc:
        raise HTTPException(422, "The selected file or table could not be read.") from exc


@router.get("/connectors")
def connectors(project_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    return [
        {"name": name, "type": "postgresql"}
        for name in sorted(settings().postgres_sources)
        if user.id in settings().admin_user_ids
    ]


@router.post("/connectors", status_code=201)
def connect(project_id: str, body: Connector, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    if user.id not in settings().admin_user_ids:
        raise HTTPException(403, "Only deployment administrators can import configured database sources.")
    from sqlalchemy.exc import SQLAlchemyError

    try:
        return import_frame(
            project, db, user, data.import_postgres(body.source, body.table), body.table, body.source
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(422, "The configured source or table is unavailable.") from exc


@router.get("/versions/{version_id}")
def preview(project_id: str, version_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    version = version_for(db, project_id, version_id)
    return item(version) | {"rows": data.json_rows(data.load(version), 100)}


@router.get("/versions/{version_id}/export")
def export(project_id: str, version_id: str, db: DB, user: Actor):
    project_for(db, user, project_id)
    version = version_for(db, project_id, version_id)
    return Response(
        storage.read(version.object_key),
        media_type="application/vnd.apache.parquet",
        headers={"Content-Disposition": f'attachment; filename="dataset-v{version.number}.parquet"'},
    )


@router.post("/versions/{version_id}/clean")
def clean(project_id: str, version_id: str, body: Cleaning, db: DB, user: Actor):
    project = project_for(db, user, project_id, write=True)
    base = version_for(db, project_id, version_id)
    try:
        frame = data.clean(data.load(base), body.steps)
        if body.preview:
            return {"before": base.profile, "after": data.profile(frame), "rows": data.json_rows(frame, 40)}
        dataset = db.scalar(select(Dataset).where(Dataset.id == base.dataset_id).with_for_update())
        number = db.scalar(select(func.max(Version.number)).where(Version.dataset_id == dataset.id)) + 1
        if number > settings().max_versions:
            raise ValueError("This dataset reached its version quota.")
        version = data.save_version(dataset, frame, number, base, [step.model_dump() for step in body.steps])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(version)
    audit(db, user, project.workspace_id, "dataset.cleaned", dataset.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        storage.remove(version.object_key)
        raise HTTPException(409, "Versions changed concurrently. Retry this transformation.") from exc
    return item(version)
