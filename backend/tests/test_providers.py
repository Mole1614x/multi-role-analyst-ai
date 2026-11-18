import json

import httpx
import pytest
import respx

from app.agents import providers
from app.core.config import settings


@pytest.mark.parametrize("name", ["openai", "gemini"])
def test_opt_in_planner_uses_only_request_and_schema(monkeypatch, name):
    config = settings()
    monkeypatch.setattr(config, "llm_provider", name)
    monkeypatch.setattr(config, "llm_api_key", "test-only-credential")
    monkeypatch.setattr(config, "llm_model", "fixture-model")
    body = json.dumps({"objective": "Compute sales", "sql": "SELECT SUM(revenue) FROM dataset"})
    with respx.mock as mock:
        if name == "openai":
            route = mock.post("https://api.openai.com/v1/chat/completions").respond(
                json={
                    "choices": [{"message": {"content": body}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 5},
                }
            )
        else:
            route = mock.post(
                "https://generativelanguage.googleapis.com/v1beta/models/fixture-model:generateContent"
            ).respond(
                json={
                    "candidates": [{"content": {"parts": [{"text": body}]}}],
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 5},
                }
            )
        plan, usage = providers.plan("Compute sales", [{"name": "revenue", "type": "int64"}])
    assert plan.sql == "SELECT SUM(revenue) FROM dataset"
    assert usage["input_tokens"] == 12 and usage["output_tokens"] == 5
    assert b"revenue" in route.calls.last.request.content


def test_research_preserves_https_citations_and_retrieval_date(monkeypatch):
    monkeypatch.setattr(settings(), "research_api_key", "test-only-credential")
    with respx.mock as mock:
        route = mock.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "web": {
                        "results": [
                            {
                                "url": "https://example.gov/data",
                                "title": "Public dataset",
                                "description": "Summary",
                            },
                            {"url": "javascript:alert(1)", "title": "Malformed result"},
                        ]
                    }
                },
            )
        )
        sources = providers.research("market information")
    assert route.called
    assert len(sources) == 1
    assert sources[0]["url"] == "https://example.gov/data"
    assert sources[0]["retrieved_at"]
    assert "primary publisher" in sources[0]["assessment"]
