from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Dataset, Job, Version


def version_for(db: Session, project_id: str, version_id: str) -> Version:
    version = db.scalar(
        select(Version)
        .join(Dataset, Version.dataset_id == Dataset.id)
        .where(Version.id == version_id, Dataset.project_id == project_id)
    )
    if not version:
        raise HTTPException(404, "Dataset version not found.")
    return version


def job_for(db: Session, project_id: str, job_id: str) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.project_id == project_id))
    if not job:
        raise HTTPException(404, "Job not found.")
    return job
