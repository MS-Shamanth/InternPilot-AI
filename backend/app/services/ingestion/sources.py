"""Job sources and the guarded HTTP fetcher (R10.1-R10.3, design.md §11.2).

Public sources use fixed URLs; nothing here accepts a caller-supplied URL or file path.
`HttpFetcher` is the only outbound HTTP path for ingestion and enforces: HTTPS only, exact-match
host allow-list, no redirects, a timeout, a streamed size cap and a JSON body.
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.schemas.common import JobSource as StoredJobSource
from app.schemas.ingest import RawFormat, unwrap_items

logger = logging.getLogger(__name__)

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
SEED_JOBS_FILE = "seed_jobs.json"
INGEST_FIXTURE_DIR = "ingest"
FIXTURE_FORMAT_KEY = "format"
JSON_MEDIA_TYPE = "application/json"
JSON_SUFFIX = "+json"
HTTPS_DEFAULT_PORT = 443


class SourceUnavailableError(Exception):
    """A source could not deliver a usable batch. `reason` is a fixed, safe token (§11.2):
    `disallowed_host | timeout | network_error | http_status_<code> | too_large |
    invalid_json | unexpected_shape | read_error`."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class RawBatch:
    """Raw items in one format; `source` is the value stored in `jobs.source` for them."""

    format: RawFormat
    source: StoredJobSource
    items: list[object]


class JobSource(Protocol):
    """Anything that can produce raw batches; tests substitute fakes."""

    name: str

    def fetch(self, limit: int) -> list[RawBatch]:
        """Return at most `limit` items in total, or raise `SourceUnavailableError`."""
        ...


def _is_json_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == JSON_MEDIA_TYPE or media_type.endswith(JSON_SUFFIX)


def _declared_length(response: httpx.Response) -> int | None:
    value = response.headers.get("content-length")
    return int(value) if value is not None and value.isdigit() else None


def _parse_json(body: bytes) -> object:
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise SourceUnavailableError("invalid_json") from None


class HttpFetcher:
    """GET a JSON document from an allow-listed HTTPS host with strict limits (§11.2)."""

    def __init__(
        self,
        allowed_hosts: Iterable[str],
        timeout_seconds: float,
        max_bytes: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport

    def get_json(self, url: str) -> object:
        """Fetch and decode `url`; every failure becomes `SourceUnavailableError`."""
        self._check_url(url)
        try:
            body = self._download(url)
        except httpx.TimeoutException:
            raise SourceUnavailableError("timeout") from None
        except httpx.HTTPError:
            raise SourceUnavailableError("network_error") from None
        return _parse_json(body)

    def _check_url(self, url: str) -> None:
        """Reject before any request unless the URL is plain HTTPS to an allow-listed host."""
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            raise SourceUnavailableError("disallowed_host") from None
        allowed = (
            parts.scheme == "https"
            and parts.hostname is not None
            and parts.hostname in self._allowed_hosts
            and parts.username is None
            and parts.password is None
            and port in (None, HTTPS_DEFAULT_PORT)
        )
        if not allowed:
            raise SourceUnavailableError("disallowed_host")

    def _download(self, url: str) -> bytes:
        with (
            httpx.Client(
                timeout=self._timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client,
            client.stream("GET", url, headers={"Accept": JSON_MEDIA_TYPE}) as response,
        ):
            if not response.is_success:
                raise SourceUnavailableError(f"http_status_{response.status_code}")
            if not _is_json_content_type(response.headers.get("content-type")):
                raise SourceUnavailableError("invalid_json")
            declared = _declared_length(response)
            if declared is not None and declared > self._max_bytes:
                raise SourceUnavailableError("too_large")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > self._max_bytes:
                    raise SourceUnavailableError("too_large")
            return bytes(body)


def _items_at(document: object, key: str) -> list[object]:
    items = document.get(key) if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise SourceUnavailableError("unexpected_shape")
    return items


class RemotiveSource:
    """Remotive public API; items under `jobs` (§11.2)."""

    name = StoredJobSource.REMOTIVE.value

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    def fetch(self, limit: int) -> list[RawBatch]:
        document = self._fetcher.get_json(f"{REMOTIVE_URL}?limit={int(limit)}")
        items = _items_at(document, "jobs")[:limit]
        return [RawBatch(RawFormat.REMOTIVE, StoredJobSource.REMOTIVE, items)]


class ArbeitnowSource:
    """Arbeitnow public API; items under `data`, truncated to `limit` (§11.2)."""

    name = StoredJobSource.ARBEITNOW.value

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    def fetch(self, limit: int) -> list[RawBatch]:
        document = self._fetcher.get_json(ARBEITNOW_URL)
        items = _items_at(document, "data")[:limit]
        return [RawBatch(RawFormat.ARBEITNOW, StoredJobSource.ARBEITNOW, items)]


class PayloadSource:
    """A caller-supplied payload (e.g. captured with the MCP fetch tool), already size-checked
    by `IngestRequest`; a top-level object is unwrapped at `jobs`/`data` (§11.2)."""

    name = StoredJobSource.PAYLOAD.value

    def __init__(self, raw_format: RawFormat, payload: object) -> None:
        self._format = raw_format
        self._payload = payload

    def fetch(self, limit: int) -> list[RawBatch]:
        items = unwrap_items(self._payload)
        if items is None:
            raise SourceUnavailableError("unexpected_shape")
        return [RawBatch(self._format, StoredJobSource.PAYLOAD, items[:limit])]


def _fixture_batch(document: object, source: StoredJobSource) -> RawBatch:
    """A fixture file is a list in normalized format, or an object with an optional `format`
    (default `normalized`) and its items under `jobs`/`data`."""
    raw_format = RawFormat.NORMALIZED
    if isinstance(document, dict):
        declared = document.get(FIXTURE_FORMAT_KEY, RawFormat.NORMALIZED.value)
        if not isinstance(declared, str) or declared not in {member.value for member in RawFormat}:
            raise SourceUnavailableError("unexpected_shape")
        raw_format = RawFormat(declared)
    items = unwrap_items(document)
    if items is None:
        raise SourceUnavailableError("unexpected_shape")
    return RawBatch(raw_format, source, items)


class FixtureSource:
    """Local files only: `DATA_DIR/seed_jobs.json` then `DATA_DIR/ingest/*.json` by filename.

    `seed_jobs.json` items keep `source="seed"` so a fallback run updates the seeded rows;
    `ingest/*.json` items are stored as `source="fixture"`. Missing files are skipped.
    """

    name = StoredJobSource.FIXTURE.value

    def __init__(self, data_dir: Path, max_bytes: int) -> None:
        self._data_dir = data_dir
        self._max_bytes = max_bytes

    def fetch(self, limit: int) -> list[RawBatch]:
        batches: list[RawBatch] = []
        remaining = limit
        for path, source in self._files():
            if remaining <= 0:
                break
            batch = _fixture_batch(self._read(path), source)
            items = batch.items[:remaining]
            remaining -= len(items)
            batches.append(RawBatch(batch.format, source, items))
        return batches

    def _files(self) -> list[tuple[Path, StoredJobSource]]:
        files: list[tuple[Path, StoredJobSource]] = []
        seed_file = self._data_dir / SEED_JOBS_FILE
        if seed_file.is_file():
            files.append((seed_file, StoredJobSource.SEED))
        ingest_dir = self._data_dir / INGEST_FIXTURE_DIR
        if ingest_dir.is_dir():
            paths = sorted(
                (path for path in ingest_dir.glob("*.json") if path.is_file()),
                key=lambda path: path.name,
            )
            files.extend((path, StoredJobSource.FIXTURE) for path in paths)
        if not files:
            logger.warning("No fixture job files found in the data directory")
        return files

    def _read(self, path: Path) -> object:
        try:
            if path.stat().st_size > self._max_bytes:
                raise SourceUnavailableError("too_large")
            body = path.read_bytes()
        except OSError:
            raise SourceUnavailableError("read_error") from None
        return _parse_json(body)
