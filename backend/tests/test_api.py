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


def test_workflow_checkpoint_approval_cancel_and_retry(client):
    _, _, workspace = account(client)
    base = project(client, workspace)
    version = upload(client, base)
    submitted = client.post(
        base + "/analyses",
        json={
            "prompt": "Investigate regional revenue",
            "version_id": version,
            "steps": [
                {"prompt": "Total revenue by region"},
                {"prompt": "Show the average instead", "require_approval": True},
                {
                    "prompt": "Chart by region",
                    "mode": "chart",
                    "require_approval": True,
                    "chart": {"type": "bar", "x": "region", "y": "revenue", "aggregation": "sum"},
                },
            ],
        },
    )
    assert submitted.status_code == 202, submitted.text
    job = submitted.json()
    assert job["status"] == "awaiting_approval", job
    result = job["result"]
    assert result["pending_approval"] == 1
    assert len(result["completed_steps"]) == 1
    url = base + "/jobs/" + job["id"]
    assert client.get(url).json()["result"] == result
    assert client.post(url + "/approve/0").status_code == 409
    assert client.post(url + "/cancel").json()["status"] == "canceled"
    assert client.post(url + "/retry").json()["result"] == result
    second = client.post(url + "/approve/1").json()
    assert second["status"] == "awaiting_approval", second
    assert second["result"]["pending_approval"] == 2
    assert second["result"]["completed_steps"][:1] == result["completed_steps"]
    assert client.post(url + "/approve/1").status_code == 409
    final = client.post(url + "/approve/2").json()
    assert final["status"] == "completed", final
    assert len(final["result"]["completed_steps"]) == 3
    assert final["result"]["plan"]["objective"] == "Investigate regional revenue"
    assert final["result"]["chart"]["rows"][0]["group"] == "North"


def test_workflow_rejects_cross_project_version_and_unassigned_roles(client):
    _, _, workspace = account(client)
    base = project(client, workspace)
    other = project(client, workspace)
    version = upload(client, base)
    outside = upload(client, other)
    body = {
        "prompt": "Test analysis plan",
        "version_id": version,
        "steps": [
            {"prompt": "Summarize revenue"},
            {"prompt": "Analyze outliers", "version_id": outside},
        ],
    }
    assert client.post(base + "/analyses", json=body).status_code == 404
    body["steps"][1] = {"prompt": "Analyze turnover", "roles": ["hr"]}
    assert client.post(base + "/analyses", json=body).status_code == 422


def test_dashboard_links_are_opt_in_scoped_read_only_and_revocable(client):
    email, _, workspace = account(client)
    base = project(client, workspace)
    version = upload(client, base)
    analysis = post_analysis(client, base, version)
    dash = client.post(base + "/dashboards", json={"title": "Shared sales", "job_id": analysis["id"]}).json()
    private = client.post(
        base + "/dashboards", json={"title": "Private sales", "job_id": analysis["id"]}
    ).json()
    share = base + f"/dashboards/{dash['id']}/share"
    public = "/api/public/dashboard"
    assert not dash["shared"] and not private["shared"]
    assert client.get(public).status_code == 404
    assert client.post(share, json={"confirmed": False}).status_code == 422
    first_link = client.post(share, json={"confirmed": True}).json()["path"]
    current_link = client.post(share, json={"confirmed": True}).json()["path"]
    first = {"Authorization": "Bearer " + first_link.split("#")[1]}
    current = {"Authorization": "Bearer " + current_link.split("#")[1]}
    assert client.get(public, headers=first).status_code == 404
    client.post("/api/auth/logout")
    response = client.get(public, headers=current)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    visible = response.json()
    assert set(visible) == {"title", "chart"} and visible["title"] == "Shared sales"
    assert set(visible["chart"]["rows"][0]) == {"region", "sum_revenue"}
    assert "source" not in visible["chart"] and "title" not in visible["chart"]
    assert client.post(public, headers=current, json={"title": "Changed"}).status_code == 405
    assert client.get(base + "/dashboards", headers=current).status_code == 401
    _, _, other_workspace = account(client)
    other = project(client, other_workspace)
    assert client.delete(other + f"/dashboards/{dash['id']}/share").status_code == 404
    assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    assert client.delete(share).status_code == 204
    assert client.get(public, headers=current).status_code == 404


def test_connector_scope_and_common_import_pipeline(client, monkeypatch):
    import httpx
    import respx

    from app.core.config import RestSource, SheetSource, settings

    _, owner, workspace = account(client)
    base = project(client, workspace)
    monkeypatch.setattr(
        settings(),
        "google_sheets_sources",
        {
            "budget": SheetSource(spreadsheet_id="test_sheet", range="Sales!A1:B3"),
        },
    )
    monkeypatch.setattr(settings(), "google_sheets_api_key", "mock-test-key")
    monkeypatch.setattr(
        settings(),
        "rest_sources",
        {
            "sales": RestSource(url="https://connector.example/sales", records_key="records"),
        },
    )
    request = {"type": "rest", "source": "sales"}
    assert client.get(base + "/connectors").json() == []
    assert client.post(base + "/connectors", json=request).status_code == 403
    monkeypatch.setattr(settings(), "admin_user_ids", [owner])
    assert client.get(base + "/connectors").json() == [
        {"name": "budget", "type": "google_sheets"},
        {"name": "sales", "type": "rest"},
    ]
    with respx.mock:
        rest = respx.get("https://connector.example/sales").respond(
            json={
                "records": [
                    {"region": "West", "revenue": 15},
                    {"region": "East", "revenue": 30},
                ]
            }
        )
        sheet = respx.get(
            url__regex=r"https://sheets\.googleapis\.com/v4/spreadsheets/test_sheet/values/.*"
        ).respond(
            json={"values": [["region", "revenue"], ["West", 15], ["East", 30]]},
        )
        for body in [request, {"type": "google_sheets", "source": "budget"}]:
            response = client.post(base + "/connectors", json=body)
            assert response.status_code == 201, response.text
            version = response.json()["versions"][0]
            assert version["profile"]["rows"] == 2 and version["number"] == 1
            assert client.get(base + "/versions/" + version["id"]).json()["rows"][0]["revenue"] == 15
        assert rest.called and sheet.calls[0].request.headers["X-Goog-Api-Key"] == "mock-test-key"
        rest.mock(return_value=httpx.Response(302, headers={"Location": "https://elsewhere.example/"}))
        assert client.post(base + "/connectors", json=request).status_code == 422


def test_research_job_records_per_claim_evidence(client, monkeypatch):
    from app.agents import evidence, providers
    from app.core.config import settings

    _, _, workspace = account(client)
    base = project(client, workspace)
    source = {"url": "https://reports.example/a", "title": "Adoption report"}
    monkeypatch.setattr(settings(), "research_api_key", "synthetic-key")
    monkeypatch.setattr(providers, "research", lambda query: [source])
    monkeypatch.setattr(evidence, "read_source", lambda url: (url, "Regional adoption 2025 was 25%."))
    response = client.post(
        base + "/analyses",
        json={
            "prompt": "Regional adoption 2025",
            "mode": "research",
            "approve_external": True,
            "claims": [{"subject": "Regional adoption 2025", "percent": 25}],
        },
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "completed", body
    check = body["result"]["claim_checks"][0]
    assert check["status"] == "supported"
    assert check["citations"][0]["url"] == source["url"]


def test_draft_workflow_uses_explicit_sequence_without_model_provider(client):
    _, _, workspace = account(client)
    base = project(client, workspace)
    version = upload(client, base)
    response = client.post(
        base + "/analyses",
        json={
            "prompt": "Total revenue by region and then average revenue by region",
            "version_id": version,
            "plan_from_prompt": True,
        },
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "awaiting_approval"
    assert job["result"]["pending_approval"] == 0 and job["result"]["completed_steps"] == []
    assert [step["prompt"] for step in job["result"]["steps"]] == [
        "Total revenue by region",
        "average revenue by region",
    ]
    approved = client.post(base + "/jobs/" + job["id"] + "/approve/0").json()
    assert approved["status"] == "completed", approved
    assert len(approved["result"]["completed_steps"]) == 2
