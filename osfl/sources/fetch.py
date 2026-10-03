"""Fetchers return raw file bytes. Live = polite httpx downloads; fixture/dir = local files.

Only the fetcher differs between live and test runs: parsing, classification, matching and run
bookkeeping are the same code either way.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx


class FetchError(Exception):
    """A file could not be downloaded or read. The message names the file."""


class Fetcher(Protocol):
    def fetch(self, filename: str, url: str) -> bytes: ...


class LiveFetcher:
    """One request at a time, at least `min_interval_s` apart, retried 3 times on 5xx/network."""

    BACKOFF_S = (2.0, 4.0, 8.0)

    def __init__(
        self,
        user_agent: str,
        min_interval_s: float,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        timeout_s: float = 120.0,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            transport=transport,
            timeout=timeout_s,
            follow_redirects=True,
        )
        self._min_interval = min_interval_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._last: float | None = None

    def _wait_turn(self, at_least: float = 0.0) -> None:
        if self._last is None:
            return
        gap = max(self._min_interval, at_least)
        remaining = self._last + gap - self._monotonic()
        if remaining > 0:
            self._sleep(remaining)

    def fetch(self, filename: str, url: str) -> bytes:
        problem = ""
        for attempt in range(len(self.BACKOFF_S) + 1):
            self._wait_turn(self.BACKOFF_S[attempt - 1] if attempt else 0.0)
            self._last = self._monotonic()
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                problem = f"{filename}: {type(exc).__name__}"
                continue
            if response.status_code >= 500:
                problem = f"{filename}: HTTP {response.status_code}"
                continue
            if response.status_code >= 400:
                raise FetchError(f"{filename}: HTTP {response.status_code}")
            return response.content
        raise FetchError(problem)


class FixtureFetcher:
    """Reads `fixtures/dbpr_weekly/<name>/<file>` or `fixtures/dbpr_plan_review/<name>`.

    Errors configured in `fixtures/errors.json` are raised as FetchError, so failure paths run
    through the same code as real HTTP errors.
    """

    def __init__(self, fixture: str, fixtures_dir: Path) -> None:
        self.fixture = fixture
        self.root = fixtures_dir
        errors_file = fixtures_dir / "errors.json"
        all_errors = json.loads(errors_file.read_text("utf-8")) if errors_file.exists() else {}
        self.errors: dict[str, str] = all_errors.get(fixture.removesuffix(".csv"), {})

    def fetch(self, filename: str, url: str) -> bytes:
        if filename in self.errors:
            raise FetchError(self.errors[filename])
        folder = self.root / "dbpr_weekly" / self.fixture
        if folder.is_dir():
            path = folder / filename
        else:
            path = self.root / "dbpr_plan_review" / self.fixture
        if not path.is_file():
            raise FetchError(f"{filename}: fixture {self.fixture!r} has no such file")
        return path.read_bytes()


class LocalFetcher:
    """For the CLI and manual uploads: a folder holding the files, or explicit file contents."""

    def __init__(self, folder: Path | None = None, files: dict[str, bytes] | None = None) -> None:
        self.folder = folder
        self.files = files or {}

    def fetch(self, filename: str, url: str) -> bytes:
        if filename in self.files:
            return self.files[filename]
        if self.folder is not None and (self.folder / filename).is_file():
            return (self.folder / filename).read_bytes()
        raise FetchError(f"{filename}: not found")
