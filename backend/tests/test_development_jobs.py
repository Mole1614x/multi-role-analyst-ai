from threading import Event
from time import monotonic, sleep

from fastapi.testclient import TestClient
from test_api import SALES, account, project

from app.core.config import settings
from app.db.models import Job
from app.db.session import SessionLocal
from app.main import app
from app.services import jobs
from app.services.local_tasks import LocalExecutor


def wait_for_job(client, base, job_id):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        job = client.get(base + "/jobs/" + job_id).json()
        if job["status"] in {"completed", "failed", "canceled"}:
            return job
        sleep(0.03)
    raise AssertionError(f"Job {job_id} did not finish")


def test_local_import_and_analysis_use_the_background_worker(monkeypatch):
    monkeypatch.setattr(settings(), "task_backend", "local")
    # A stalled worker must not hold open the upload request.
    started, release = Event(), Event()
    execute = jobs.execute_job

    def delayed(job_id):
        started.set()
        if release.wait(8):
            execute(job_id)

    monkeypatch.setattr(jobs, "execute_job", delayed)
    with TestClient(app) as client:
        _, _, workspace = account(client)
        base = project(client, workspace)
        try:
            response = client.post(base + "/datasets", files={"file": ("sales.csv", SALES)})
            assert response.status_code == 202
            job_id = response.json()["job_id"]
            assert started.wait(3)
            assert client.get(base + "/jobs/" + job_id).json()["status"] == "queued"
            assert client.get(base + "/datasets").json() == []
        finally:
            release.set()

        job = wait_for_job(client, base, job_id)
        assert job["status"] == "completed", job
        assert job["result"]["rows"] == 4
        version = job["result"]["version_id"]
        assert client.get(f"{base}/versions/{version}").json()["profile"]["duplicates"] == 1

        result = client.post(
            base + "/analyses", json={"prompt": "Total revenue by region", "version_id": version}
        )
        assert result.status_code == 202
        analysis = wait_for_job(client, base, result.json()["id"])
        assert analysis["status"] == "completed", analysis
        assert analysis["result"]["query"]["rows"][0]["sum_revenue"] == 200.0

        report = client.post(
            base + "/reports", json={"job_id": analysis["id"], "title": "Revenue", "format": "csv"}
        )
        assert report.status_code == 202
        finished_report = wait_for_job(client, base, report.json()["id"])
        assert finished_report["status"] == "completed", finished_report
        assert "artifact_id" in finished_report["result"]


def test_interrupted_local_jobs_are_marked_failed(monkeypatch):
    monkeypatch.setattr(settings(), "task_backend", "local")
    with TestClient(app) as client:
        _, user_id, workspace = account(client)
        base = project(client, workspace)
        project_id = base.rsplit("/", 1)[-1]
    with SessionLocal() as db:
        local = Job(project_id=project_id, requested_by=user_id, kind="import", payload={"_runner": "local"})
        celery = Job(
            project_id=project_id, requested_by=user_id, kind="import", payload={"_runner": "celery"}
        )
        db.add_all([local, celery])
        db.commit()

    with TestClient(app):
        pass
    with SessionLocal() as db:
        assert db.get(Job, local.id).status == "failed"
        assert "Retry" in db.get(Job, local.id).error
        assert db.get(Job, celery.id).status == "queued"


def test_local_worker_keeps_a_fixed_capacity():
    worker = LocalExecutor(capacity=2)
    started, release = Event(), Event()

    def run(_id):
        started.set()
        release.wait(5)

    try:
        assert worker.submit(run, "first")
        assert started.wait(3)
        assert worker.submit(run, "second")
        assert not worker.submit(run, "third")
    finally:
        worker.close()
        release.set()
