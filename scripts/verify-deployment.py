#!/usr/bin/env python3
"""Create and verify synthetic recovery data and exercise a loopback-only deployment."""

import argparse
import hashlib
import http.client
import http.cookiejar
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

CSV = b"region,revenue\nNorth,60\nNorth,40\nSouth,25\nNorth,60\n"


class Client:
    def __init__(self, origin):
        self.origin = origin.rstrip("/")
        self.http = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, data=None, *, expected=200, body=None, headers=None, raw=False):
        headers = dict(headers or {})
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        resource = Request(self.origin + path, data=body, headers=headers, method=method)
        try:
            response = self.http.open(resource, timeout=25)
        except HTTPError as exc:
            response = exc
        with response:
            content = response.read()
            if response.status not in (expected if isinstance(expected, tuple) else (expected,)):
                raise RuntimeError(f"{method} {path} returned {response.status}: {content[:500]!r}")
            return content if raw else json.loads(content) if content else None

    def register(self):
        account = {"email": secrets.token_hex(10) + "@example.com", "password": secrets.token_urlsafe(24)}
        self.call("POST", "/api/auth/register", account | {"name": "Recovery drill"}, expected=201)
        return account

    def poll(self, base, job, desired="completed"):
        deadline = monotonic() + 40
        while monotonic() < deadline:
            current = self.call("GET", f"{base}/jobs/{job}")
            if current["status"] == desired:
                return current
            if current["status"] in {"failed", "canceled", "completed"}:
                raise RuntimeError(f"Job {job} ended as {current['status']}: {current['error']}")
            sleep(.15)
        raise RuntimeError(f"Job {job} did not reach {desired}.")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def seed(client):
    account = client.register()
    workspace = client.call("GET", "/api/workspaces")[0]["id"]
    project = client.call("POST", "/api/projects", {
        "workspace_id": workspace, "name": "Recovery drill", "roles": ["sales"],
    }, expected=201)
    base = "/api/projects/" + project["id"]
    boundary = "drill-" + secrets.token_hex(8)
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="background"\r\n\r\ntrue\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sales.csv"\r\n'
        'Content-Type: text/csv\r\n\r\n'
    ).encode() + CSV + f"\r\n--{boundary}--\r\n".encode()
    uploaded = client.call("POST", base + "/datasets", body=body, expected=(201, 202),
                           headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    original = client.poll(base, uploaded["job_id"])["result"]["version_id"]
    cleaned = client.call("POST", f"{base}/versions/{original}/clean", {
        "steps": [{"operation": "drop_duplicates"}],
    })
    version = cleaned["id"]
    analysis = client.call("POST", base + "/analyses", {
        "version_id": version, "prompt": "Total revenue by region",
    }, expected=202)
    completed = client.poll(base, analysis["id"])
    assert completed["result"]["chart"]["rows"][0]["sum_revenue"] == 100
    dashboard = client.call("POST", base + "/dashboards", {
        "title": "Backup verification dashboard", "job_id": analysis["id"],
    }, expected=201)
    report = client.call("POST", base + "/reports", {
        "title": "Backup verification report", "job_id": analysis["id"], "format": "csv",
    }, expected=202)
    artifact = client.poll(base, report["id"])["result"]["artifact_id"]
    versions = {item: digest(client.call("GET", f"{base}/versions/{item}/export", raw=True))
                for item in (original, version)}
    report_content = client.call("GET", f"{base}/artifacts/{artifact}", raw=True)
    assert b"North,100" in report_content
    return {"account": account, "base": base, "versions": versions, "version": version,
            "dashboard": dashboard["id"], "report": artifact, "report_hash": digest(report_content),
            "analysis": analysis["id"]}


def verify(client, state):
    client.call("POST", "/api/auth/login", state["account"])
    base = state["base"]
    client.call("GET", base)
    dashboards = client.call("GET", base + "/dashboards")
    assert any(item["id"] == state["dashboard"] for item in dashboards)
    assert client.call("GET", f"{base}/jobs/{state['analysis']}")["status"] == "completed"
    for item, expected in state["versions"].items():
        assert digest(client.call("GET", f"{base}/versions/{item}/export", raw=True)) == expected
    content = client.call("GET", f"{base}/artifacts/{state['report']}", raw=True)
    assert digest(content) == state["report_hash"]
    print("Account, project, dashboard, job, two dataset versions, and report verified.")


def exercise(client, state, maximum, workers, iterations):
    verify(client, state)
    base, version = state["base"], state["version"]
    outside = Client(client.origin)
    outside.register()
    outside.call("GET", base, expected=404)
    outside.call("GET", f"{base}/versions/{version}/export", expected=404)
    outside.call("GET", f"{base}/artifacts/{state['report']}", expected=404)
    outside.call("POST", base + "/analyses", {"prompt": "Total revenue", "version_id": version}, expected=404)
    client.call("POST", base + "/sql", {"version_id": version, "sql": "DELETE FROM dataset"}, expected=422)

    target = urlsplit(client.origin)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=10)
    try:
        connection.putrequest("POST", base + "/datasets")
        connection.putheader("Content-Type", "multipart/form-data; boundary=limit-check")
        connection.putheader("Content-Length", str(maximum + 70_001))
        connection.endheaders()
        with connection.getresponse() as response:
            assert response.status == 413
    finally:
        connection.close()
    print("Tenant isolation, upload size gate, and read-only SQL checks passed.")

    def work(_):
        begin = monotonic()
        job = client.call("POST", base + "/analyses", {
            "version_id": version, "prompt": "Total revenue by region",
        }, expected=202)
        result = client.poll(base, job["id"])["result"]
        assert result["chart"]["rows"][0]["sum_revenue"] == 100
        return monotonic() - begin

    started = monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        times = sorted(pool.map(work, range(iterations)))
    tail = times[(95 * len(times) + 99) // 100 - 1]
    print(f"{iterations} analysis jobs completed with {workers} concurrent clients in "
          f"{monotonic() - started:.2f}s, p95 end-to-end {tail:.2f}s, zero incorrect or failed jobs.")
    metrics = client.call("GET", "/metrics", raw=True).decode()
    assert "analyst_job_records" in metrics
    assert "analyst_broker_queue_depth" in metrics
    assert "analyst_job_metrics_broker_up 1.0" in metrics
    print("Persisted job counts and Redis queue metrics verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seed", "verify", "exercise"])
    parser.add_argument("origin")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--upload-limit", type=int, default=20_000_000)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--iterations", type=int, choices=range(1, 36), default=16)
    args = parser.parse_args()
    target = urlsplit(args.origin)
    if target.scheme != "http" or target.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Use a loopback HTTP deployment created for this drill.")
    client = Client(args.origin)
    client.call("GET", "/api/health/ready")
    if args.command == "seed":
        with args.fixture.open("x", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
            json.dump(seed(client), output)
    else:
        state = json.loads(args.fixture.read_text())
        if args.command == "verify":
            verify(client, state)
        else:
            exercise(client, state, args.upload_limit, args.workers, args.iterations)


if __name__ == "__main__":
    main()
