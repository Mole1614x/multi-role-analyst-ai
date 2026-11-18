import socket

import pytest

from app.agents import evidence


def test_full_source_agreement_disagreement_and_insufficient(monkeypatch):
    pages = {
        "https://one.example/": "<p>North region 2025 adoption was 25 percent.</p><script>South region adoption was 80%.</script>",
        "https://two.example/": "<p>North region 2025 adoption was 25%.</p><p>North region 2024 adoption was 19%.</p>",
        "https://three.example/": "<p>North region 2024 adoption was 21%.</p>",
    }

    def read(url):
        if url not in pages:
            raise TimeoutError()
        return url, evidence.source_text(pages[url], "text/html")

    monkeypatch.setattr(evidence, "read_source", read)
    sources = [
        {"url": url, "title": url, "snippet": "South region adoption was 80%."}
        for url in [*pages, "https://unavailable.example/"]
    ]
    metadata, checks = evidence.verify(
        sources,
        [
            evidence.ResearchClaim(subject="North region 2025 adoption", percent=25),
            evidence.ResearchClaim(subject="North region 2024 adoption", percent=19),
            evidence.ResearchClaim(subject="South region adoption", percent=80),
        ],
    )
    assert [entry["status"] for entry in checks] == ["supported", "conflicting", "insufficient"]
    assert [citation["url"] for citation in checks[0]["citations"]] == list(pages)[:2]
    assert [citation["stance"] for citation in checks[1]["citations"]] == ["supports", "different_value"]
    assert checks[0]["citations"][0]["retrieved_at"] == metadata[0]["retrieved_at"]
    assert metadata[-1]["read_status"] == "unavailable"


def test_source_addresses_must_all_be_public(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (None, None, None, "", ("8.8.8.8", 443)),
            (None, None, None, "", ("127.0.0.1", 443)),
        ],
    )
    with pytest.raises(ValueError, match="public"):
        evidence.public_address("example.com")
    for url in ["http://example.com", "https://user@example.com", "https://example.com:8443"]:
        with pytest.raises(ValueError, match="public HTTPS"):
            evidence.source_url(url)
