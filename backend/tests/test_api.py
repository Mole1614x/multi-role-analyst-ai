from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

SALES = b"date,region,revenue,expenses\n2025-01-01,North,100,60\n2025-01-02,South,70,40\n2025-01-03,North,50,30\n2025-01-03,North,50,30\n"
PASSWORD = "correct test password 123"


def account(client, name="Taylor"):
    email = f"{uuid4().hex}@example.com"
    response = client.post("/api/auth/register", json={"name": name, "email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    workspace = client.get("/api/workspaces").json()[0]
    return email, response.json()["id"], workspace["id"]


def project(client, workspace, roles=None):
    response = client.post(
        "/api/projects",
        json={
            "workspace_id": workspace,
            "name": "Revenue analysis",
            "roles": roles or ["data", "sales", "finance", "bi"],
        },
    )
    assert response.status_code == 201, response.text
    return "/api/projects/" + response.json()["id"]


def upload(client, base, csv=SALES):
    response = client.post(base + "/datasets", files={"file": ("sales.csv", csv)})
    assert response.status_code == 201, response.text
    return response.json()["versions"][0]["id"]


def post_analysis(client, base, version, **fields):
    response = client.post(
        base + "/analyses", json={"version_id": version, "prompt": "Total revenue by region"} | fields
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "completed", body
    return body


def test_auth_workspace_access_and_csrf(client):
    email, owner, workspace = account(client)
    base = project(client, workspace)
    version = upload(client, base)
    assert client.get("/api/health/ready").status_code == 200
    assert client.get("/api/auth/me").json()["id"] == owner
    assert client.post("/api/auth/logout", headers={"Origin": "https://unrelated.example"}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get(base).status_code == 401
    second_email, second, second_workspace = account(client, "Morgan")
    second_base = project(client, second_workspace)
    assert client.get(base).status_code == 404
    assert client.get(f"{second_base}/versions/{version}").status_code == 404
    assert (
        client.post(f"{second_base}/sql", json={"version_id": version, "sql": "SELECT 1"}).status_code == 404
    )
    assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    assert (
        client.put(
            f"/api/workspaces/{workspace}/members", json={"user_id": second, "role": "viewer"}
        ).status_code
        == 200
    )
    assert (
        client.post("/api/auth/login", json={"email": second_email, "password": PASSWORD}).status_code == 200
    )
    assert client.get(f"{base}/versions/{version}").status_code == 200
    assert (
        client.post(base + "/analyses", json={"version_id": version, "prompt": "Total revenue"}).status_code
        == 403
    )
    assert client.get("/api/admin").status_code == 404


def test_ingestion_cleaning_sql_and_multi_role_workflow(client):
    _, _, workspace = account(client)
    base = project(client, workspace)
    version = upload(client, base)
    original = client.get(f"{base}/versions/{version}").json()
    assert original["profile"]["duplicates"] == 1
    clean = {"steps": [{"operation": "drop_duplicates"}]}
    preview = client.post(f"{base}/versions/{version}/clean", json=clean | {"preview": True})
    assert preview.json()["after"]["rows"] == 3
    updated = client.post(f"{base}/versions/{version}/clean", json=clean)
    assert updated.status_code == 200, updated.text
    current = updated.json()["id"]
    assert updated.json()["parent_id"] == version
    assert client.get(f"{base}/versions/{version}").json()["sha256"] == original["sha256"]
    draft = client.post(
        base + "/sql/draft", json={"version_id": current, "prompt": "Total revenue by region"}
    )
    assert draft.status_code == 200
    query = client.post(
        base + "/sql", json={"version_id": current, "sql": draft.json()["sql"], "title": "Regional sales"}
    )
    assert query.status_code == 200, query.text
    assert query.json()["result"]["rows"] == [
        {"region": "North", "sum_revenue": 150},
        {"region": "South", "sum_revenue": 70},
    ]
    assert b"150" in client.get(base + f"/sql/{query.json()['id']}/export").content
    invalid = client.post(base + "/sql", json={"version_id": current, "sql": "DELETE FROM dataset"})
    assert invalid.status_code == 422
    analysis = post_analysis(client, base, current)
    findings = {item["role"]: item for item in analysis["result"]["role_findings"]}
    assert findings["sales"]["values"]["total"] == 220
    assert findings["finance"]["values"]["profit"] == 90
    assert analysis["result"]["source"]["sha256"] == updated.json()["sha256"]
    assert analysis["result"]["chart"]["rows"] == query.json()["result"]["rows"]
    steps = [item["step"] for item in analysis["trace"]]
    assert steps[0] == "Supervisor" and steps[-1] == "Validation"
    with client.stream("GET", base + f"/jobs/{analysis['id']}/events") as stream:
        assert '"completed"' in next(stream.iter_lines())
    dashboard = client.post(
        base + "/dashboards", json={"job_id": analysis["id"], "title": "Regional revenue"}
    )
    assert dashboard.status_code == 201, dashboard.text
    assert client.get(base + "/dashboards").json()[0]["title"] == "Regional revenue"
    assert b"North" in client.get(base + f"/dashboards/{dashboard.json()['id']}/export").content
    assert client.get(base + "/jobs").json()[0]["status"] == "completed"
    follow_up = post_analysis(
        client, base, None, prompt="Show the average instead", previous_job_id=analysis["id"]
    )
    assert follow_up["result"]["query"]["rows"][0]["avg_revenue"] == 75
    assert follow_up["result"]["source"]["version_id"] == current
    combined = client.post(
        base + "/dashboards",
        json={"job_ids": [analysis["id"], follow_up["id"]], "title": "Revenue comparisons"},
    )
    assert combined.status_code == 201, combined.text
    assert len(combined.json()["chart"]["panels"]) == 2
    content = client.get(base + f"/dashboards/{combined.json()['id']}/export").content
    assert b"Data: avg_revenue" in content
    plotly = client.get(base + f"/dashboards/{combined.json()['id']}/export?format=plotly").json()
    assert plotly["figures"][1]["data"][0]["y"] == [75, 70]


@pytest.mark.parametrize("format_name", ["pdf", "xlsx", "pptx", "md", "html", "csv"])
def test_report_formats_open_with_real_results(client, format_name):
    _, _, workspace = account(client)
    base = project(client, workspace)
    analysis = post_analysis(client, base, upload(client, base))
    response = client.post(
        base + "/reports",
        json={"job_id": analysis["id"], "title": "Regional revenue reporting", "format": format_name},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "completed", job
    download = client.get(base + "/artifacts/" + job["result"]["artifact_id"])
    assert "attachment" in download.headers["content-disposition"]
    if format_name == "pdf":
        reader = PdfReader(BytesIO(download.content))
        assert "Regional revenue reporting" in reader.pages[0].extract_text()
    elif format_name == "xlsx":
        book = load_workbook(BytesIO(download.content), read_only=True)
        assert book["Summary"]["A1"].value == "Regional revenue reporting"
        assert book["Result data"]["A2"].value == "North"
    elif format_name == "pptx":
        deck = Presentation(BytesIO(download.content))
        assert deck.slides[0].shapes.title.text == "Regional revenue reporting"
        assert any(slide.shapes.title.text == "Result data preview" for slide in deck.slides)
    elif format_name == "html":
        assert b"data:image/png;base64," in download.content and b"North" in download.content
    else:
        assert b"Executive summary" in download.content and b"North" in download.content


def test_import_errors_research_disabled_and_job_retry(client):
    _, _, workspace = account(client)
    base = project(client, workspace)
    assert client.post(base + "/datasets", files={"file": ("broken.xlsx", b"invalid")}).status_code == 422
    assert client.post(base + "/datasets", files={"file": ("binary.exe", b"invalid")}).status_code == 422
    response = client.post(
        base + "/analyses",
        json={"prompt": "Find market share online", "mode": "research", "approve_external": True},
    )
    assert response.status_code == 503
    version = upload(client, base)
    fail = client.post(
        base + "/analyses",
        json={
            "version_id": version,
            "prompt": "Forecast revenue",
            "mode": "forecast",
            "date": "date",
            "value": "revenue",
        },
    ).json()
    assert fail["status"] == "failed" and "twelve" in fail["error"]
    retry = client.post(base + f"/jobs/{fail['id']}/retry").json()
    assert retry["attempt"] == 2 and retry["status"] == "failed"
    assert client.post(base + f"/jobs/{fail['id']}/cancel").status_code == 409
