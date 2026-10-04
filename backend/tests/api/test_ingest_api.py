"""API tests for `POST /api/jobs/ingest` (R10, R12, design.md §8, §11).

Sources are replaced through the `get_ingestion_sources` dependency; HTTP goes through
`httpx.MockTransport`, so no test touches the network.
"""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.jobs import get_ingestion_sources
from app.models import User
from app.services.ingestion.service import IngestionSources
from app.services.ingestion.sources import (
    ArbeitnowSource,
    FixtureSource,
    HttpFetcher,
    RemotiveSource,
)

pytestmark = pytest.mark.api

INGEST_PATH = "/api/jobs/ingest"
RESULT_FIELDS = {
    "requested_source",
    "source",
    "fallback_used",
    "fetched",
    "created",
    "updated",
    "duplicates",
    "rejected",
    "errors",
}
REMOTIVE_JOB = {
    "id": 42,
    "url": "https://remotive.com/remote-jobs/42",
    "title": "Junior Python Developer",
    "company_name": "Acme",
    "job_type": "full_time",
    "candidate_required_location": "Worldwide",
    "tags": ["python", "django"],
    "description": "<p>Python &amp; SQL</p>",
}


def normalized_job(external_id: str, title: str) -> dict[str, object]:
    return {
        "external_id": external_id,
        "title": title,
        "company": "Example Co",
        "location": "Remote",
        "employment_type": "internship",
        "work_mode": "remote",
        "description": "Build things.",
        "application_url": f"https://jobs.example.com/{external_id}",
        "required_skills": ["React"],
    }


def remotive_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "remotive.com":
        return httpx.Response(200, json={"jobs": [REMOTIVE_JOB]})
    return httpx.Response(500)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    (tmp_path / "seed_jobs.json").write_text(
        json.dumps([normalized_job("seed-001", "Frontend Intern")]), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def ingest_app(app: FastAPI, data_dir: Path) -> FastAPI:
    fetcher = HttpFetcher(
        ["remotive.com", "www.arbeitnow.com"], 5, 5_000_000, httpx.MockTransport(remotive_handler)
    )
    sources = IngestionSources(
        remotive=RemotiveSource(fetcher),
        arbeitnow=ArbeitnowSource(fetcher),
        fixture=FixtureSource(data_dir, 5_000_000),
    )
    app.dependency_overrides[get_ingestion_sources] = lambda: sources
    return app


@pytest.fixture
def ingest_client(ingest_app: FastAPI, client: TestClient, demo_user: User) -> TestClient:
    return client


def test_ingest_remotive_returns_result_shape(ingest_client: TestClient) -> None:
    response = ingest_client.post(INGEST_PATH, json={"source": "remotive", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESULT_FIELDS
    assert body == {
        "requested_source": "remotive",
        "source": "remotive",
        "fallback_used": False,
        "fetched": 1,
        "created": 1,
        "updated": 0,
        "duplicates": 0,
        "rejected": 0,
        "errors": [],
    }
    jobs = ingest_client.get("/api/jobs", params={"source": "remotive"}).json()["items"]
    assert [(job["title"], job["experience_level"]) for job in jobs] == [
        ("Junior Python Developer", "junior")
    ]


def test_ingest_arbeitnow_failure_falls_back_to_fixture(ingest_client: TestClient) -> None:
    response = ingest_client.post(INGEST_PATH, json={"source": "arbeitnow"})

    assert response.status_code == 200
    body = response.json()
    assert (body["source"], body["fallback_used"], body["created"]) == ("fixture", True, 1)
    assert body["errors"] == [{"index": None, "reason": "arbeitnow: http_status_500"}]


def test_ingest_failure_without_fallback_returns_502_envelope(ingest_client: TestClient) -> None:
    response = ingest_client.post(INGEST_PATH, json={"source": "arbeitnow", "fallback": False})

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "INGESTION_SOURCE_UNAVAILABLE"
    assert error["details"] == {"source": "arbeitnow", "reason": "http_status_500"}
    assert ingest_client.get("/api/jobs").json()["total"] == 0


def test_ingest_payload_normalized_creates_jobs(ingest_client: TestClient) -> None:
    payload = {"jobs": [normalized_job("p-1", "Data Intern"), normalized_job("p-2", "")]}
    response = ingest_client.post(
        INGEST_PATH, json={"source": "payload", "format": "normalized", "payload": payload}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["fetched"], body["created"], body["rejected"]) == (2, 1, 1)
    assert body["errors"][0]["index"] == 1


@pytest.mark.parametrize(
    "body",
    [
        {"source": "fixture", "unexpected": True},
        {"source": "linkedin"},
        {"source": "fixture", "limit": 501},
        {"source": "fixture", "payload": []},
        {"source": "payload", "payload": []},
        {"source": "payload", "format": "normalized"},
        {"source": "payload", "format": "normalized", "payload": {"items": []}},
        {"source": "payload", "format": "normalized", "payload": [{}] * 501},
    ],
)
def test_ingest_invalid_request_returns_422(
    ingest_client: TestClient, body: dict[str, object]
) -> None:
    response = ingest_client.post(INGEST_PATH, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_ingest_body_over_5_mb_returns_413(ingest_client: TestClient) -> None:
    oversized = json.dumps(
        {"source": "payload", "format": "normalized", "payload": [{"d": "x" * 5_100_000}]}
    )
    response = ingest_client.post(
        INGEST_PATH, content=oversized, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
