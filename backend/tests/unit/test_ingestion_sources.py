"""Unit tests for `HttpFetcher` guards and job sources (R10.1-R10.3, design.md §11.2).

No network: every HTTP exchange goes through `httpx.MockTransport`.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

from app.schemas.common import JobSource
from app.schemas.ingest import RawFormat
from app.services.ingestion.sources import (
    ARBEITNOW_URL,
    ArbeitnowSource,
    FixtureSource,
    HttpFetcher,
    PayloadSource,
    RemotiveSource,
    SourceUnavailableError,
)

pytestmark = pytest.mark.unit

ALLOWED_HOSTS = ("remotive.com", "www.arbeitnow.com")
MAX_BYTES = 1_000
JSON_HEADERS = {"content-type": "application/json"}

type Handler = Callable[[httpx.Request], httpx.Response]


def fetcher_for(handler: Handler, max_bytes: int = MAX_BYTES) -> HttpFetcher:
    return HttpFetcher(ALLOWED_HOSTS, 5, max_bytes, transport=httpx.MockTransport(handler))


def json_response(document: object) -> httpx.Response:
    return httpx.Response(200, headers=JSON_HEADERS, content=json.dumps(document).encode())


def failing_handler(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"no request expected, got {request.url}")


def reason_of(fetcher: HttpFetcher, url: str) -> str:
    with pytest.raises(SourceUnavailableError) as caught:
        fetcher.get_json(url)
    return caught.value.reason


def test_fetcher_returns_decoded_json_for_allowed_https_host() -> None:
    fetcher = fetcher_for(lambda request: json_response({"jobs": []}))
    assert fetcher.get_json("https://remotive.com/api/remote-jobs") == {"jobs": []}


@pytest.mark.parametrize(
    "url",
    [
        "http://remotive.com/api/remote-jobs",
        "https://evil.example.com/api",
        "https://remotive.com.evil.example/api",
        "https://user:pass@remotive.com/api",
        "https://remotive.com:8443/api",
        "file:///etc/passwd",
    ],
)
def test_fetcher_rejects_disallowed_url_before_any_request(url: str) -> None:
    assert reason_of(fetcher_for(failing_handler), url) == "disallowed_host"


def test_fetcher_does_not_follow_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "remotive.com"
        return httpx.Response(302, headers={"location": "https://evil.example.com/"})

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "http_status_302"


def test_fetcher_rejects_non_2xx_status() -> None:
    fetcher = fetcher_for(lambda request: httpx.Response(503))
    assert reason_of(fetcher, "https://remotive.com/api") == "http_status_503"


def test_fetcher_rejects_declared_oversized_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=JSON_HEADERS, content=b"[" + b"1," * 600 + b"1]")

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "too_large"


def test_fetcher_aborts_oversized_stream_without_content_length() -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(100):
            yield b"[" + b" " * 50

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=JSON_HEADERS, content=chunks())

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "too_large"


def test_fetcher_rejects_non_json_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "invalid_json"


def test_fetcher_rejects_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=JSON_HEADERS, content=b"{not json")

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "invalid_json"


def test_fetcher_translates_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "timeout"


def test_fetcher_translates_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert reason_of(fetcher_for(handler), "https://remotive.com/api") == "network_error"


def test_remotive_source_uses_fixed_url_with_limit_and_truncates() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return json_response({"jobs": [{"id": 1}, {"id": 2}, {"id": 3}]})

    batches = RemotiveSource(fetcher_for(handler)).fetch(2)
    assert seen == ["https://remotive.com/api/remote-jobs?limit=2"]
    assert len(batches) == 1
    assert batches[0].format is RawFormat.REMOTIVE
    assert batches[0].source is JobSource.REMOTIVE
    assert batches[0].items == [{"id": 1}, {"id": 2}]


def test_arbeitnow_source_reads_data_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ARBEITNOW_URL
        return json_response({"data": [{"slug": "a"}]})

    batches = ArbeitnowSource(fetcher_for(handler)).fetch(10)
    assert batches[0].items == [{"slug": "a"}]
    assert batches[0].source is JobSource.ARBEITNOW


def test_source_with_unexpected_shape_is_unavailable() -> None:
    source = RemotiveSource(fetcher_for(lambda request: json_response({"jobs": "nope"})))
    with pytest.raises(SourceUnavailableError) as caught:
        source.fetch(10)
    assert caught.value.reason == "unexpected_shape"


def test_payload_source_unwraps_object_and_applies_limit() -> None:
    source = PayloadSource(RawFormat.ARBEITNOW, {"data": [{"slug": "a"}, {"slug": "b"}]})
    batches = source.fetch(1)
    assert batches[0].format is RawFormat.ARBEITNOW
    assert batches[0].source is JobSource.PAYLOAD
    assert batches[0].items == [{"slug": "a"}]


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_fixture_source_reads_seed_then_sorted_ingest_files(tmp_path: Path) -> None:
    write_json(tmp_path / "seed_jobs.json", [{"external_id": "seed-001"}])
    write_json(tmp_path / "ingest" / "b.json", {"format": "remotive", "jobs": [{"id": 2}]})
    write_json(tmp_path / "ingest" / "a.json", [{"external_id": "fx-1"}])
    (tmp_path / "ingest" / "notes.txt").write_text("ignored", encoding="utf-8")

    batches = FixtureSource(tmp_path, MAX_BYTES).fetch(10)

    assert [(batch.source, batch.format) for batch in batches] == [
        (JobSource.SEED, RawFormat.NORMALIZED),
        (JobSource.FIXTURE, RawFormat.NORMALIZED),
        (JobSource.FIXTURE, RawFormat.REMOTIVE),
    ]
    assert [batch.items for batch in batches] == [
        [{"external_id": "seed-001"}],
        [{"external_id": "fx-1"}],
        [{"id": 2}],
    ]


def test_fixture_source_limit_applies_across_files(tmp_path: Path) -> None:
    write_json(tmp_path / "seed_jobs.json", [{"external_id": "1"}, {"external_id": "2"}])
    write_json(tmp_path / "ingest" / "a.json", [{"external_id": "3"}])
    batches = FixtureSource(tmp_path, MAX_BYTES).fetch(2)
    assert sum(len(batch.items) for batch in batches) == 2


def test_fixture_source_with_no_files_returns_nothing(tmp_path: Path) -> None:
    assert FixtureSource(tmp_path, MAX_BYTES).fetch(10) == []


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"{broken", "invalid_json"),
        (b'{"format": "unknown", "jobs": []}', "unexpected_shape"),
        (b'{"items": []}', "unexpected_shape"),
        (b"[" + b" " * MAX_BYTES + b"]", "too_large"),
    ],
)
def test_fixture_source_bad_file_is_unavailable(
    tmp_path: Path, content: bytes, reason: str
) -> None:
    (tmp_path / "seed_jobs.json").write_bytes(content)
    with pytest.raises(SourceUnavailableError) as caught:
        FixtureSource(tmp_path, MAX_BYTES).fetch(10)
    assert caught.value.reason == reason


def test_fetcher_rejects_missing_content_type() -> None:
    fetcher = fetcher_for(lambda request: httpx.Response(200, content=b"{}"))
    assert reason_of(fetcher, "https://remotive.com/api") == "invalid_json"


def test_fetcher_rejects_unparseable_port_before_any_request() -> None:
    fetcher = fetcher_for(failing_handler)
    assert reason_of(fetcher, "https://remotive.com:not-a-port/api") == "disallowed_host"


def test_payload_source_with_unexpected_shape_is_unavailable() -> None:
    source = PayloadSource(RawFormat.NORMALIZED, {"unexpected": "shape"})
    with pytest.raises(SourceUnavailableError) as caught:
        source.fetch(10)
    assert caught.value.reason == "unexpected_shape"
