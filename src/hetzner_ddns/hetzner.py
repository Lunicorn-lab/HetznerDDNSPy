"""Hetzner DNS API client — minimal, retrying, TLS-verified."""

from __future__ import annotations

import json
import logging
import random
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Final, Literal

from hetzner_ddns import __version__
from hetzner_ddns.errors import (
    APIError,
    AuthError,
    RateLimitError,
    TransientAPIError,
)

log = logging.getLogger(__name__)

DEFAULT_BASE_URL: Final[str] = "https://dns.hetzner.com/api/v1"
DEFAULT_TIMEOUT: Final[float] = 15.0
MAX_RETRIES: Final[int] = 5
BACKOFF_BASE: Final[float] = 0.5
BACKOFF_CAP: Final[float] = 30.0
USER_AGENT: Final[str] = f"hetzner-ddns/{__version__} (+https://github.com/Lunicorn/HetznerDDNSPy)"

HttpMethod = Literal["GET", "POST", "PUT", "DELETE"]


@dataclass(frozen=True, slots=True)
class Record:
    """A Hetzner DNS record as returned by the API."""

    id: str
    name: str
    type: str
    value: str
    zone_id: str
    ttl: int | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Record:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "")),
            type=str(data["type"]),
            value=str(data["value"]),
            zone_id=str(data["zone_id"]),
            ttl=int(data["ttl"]) if data.get("ttl") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class Zone:
    """A Hetzner DNS zone."""

    id: str
    name: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Zone:
        return cls(id=str(data["id"]), name=str(data["name"]))


class HetznerDNSClient:
    """Thin, stdlib-only Hetzner DNS API client with retry & backoff."""

    def __init__(
        self,
        api_token: str,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        ssl_context: ssl.SSLContext | None = None,
        sleep: object = time.sleep,
    ) -> None:
        if not api_token or not api_token.strip():
            raise ValueError("api_token is required")
        base_url = base_url or DEFAULT_BASE_URL
        timeout = DEFAULT_TIMEOUT if timeout is None else timeout
        max_retries = MAX_RETRIES if max_retries is None else max_retries
        if not base_url.startswith(("https://", "http://")):
            raise ValueError(f"base_url must be http(s): {base_url!r}")
        # Only allow plain HTTP for the loopback test fixtures — production must be TLS.
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(f"Refusing non-HTTPS base_url: {base_url}")
        self._token = api_token
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._sleep = sleep
        if ssl_context is None:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        self._ssl = ssl_context

    # ---- HTTP plumbing ------------------------------------------------------
    def _compute_backoff(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, BACKOFF_CAP)
        expo: float = min(BACKOFF_CAP, BACKOFF_BASE * (2**attempt))
        jitter = 0.5 + random.random() * 0.5  # noqa: S311 — jitter, not security
        return expo * jitter

    def _request(  # noqa: PLR0912 — branches match HTTP status handling, splitting hurts clarity
        self,
        method: HttpMethod,
        path: str,
        *,
        query: dict[str, str | int] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            raise ValueError(f"path must start with '/': {path!r}")
        url = self._base + path
        if query:
            url += "?" + urllib.parse.urlencode({k: str(v) for k, v in query.items()})

        headers = {
            "Auth-API-Token": self._token,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            req = urllib.request.Request(  # noqa: S310 — scheme validated in __init__
                url,
                data=body,
                headers=headers,
                method=method,
            )
            try:
                with urllib.request.urlopen(  # noqa: S310  # nosec B310
                    req,
                    timeout=self._timeout,
                    context=self._ssl,
                ) as resp:
                    payload = resp.read()
            except urllib.error.HTTPError as exc:
                err_body = exc.read(2048).decode("utf-8", errors="replace")
                retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
                log.warning(
                    "Hetzner API %s %s -> HTTP %d: %s",
                    method,
                    path,
                    exc.code,
                    err_body[:200],
                )
                if exc.code in (401, 403):
                    raise AuthError(
                        f"auth rejected by Hetzner API ({exc.code})", status=exc.code
                    ) from exc
                if exc.code == 429:
                    if attempt >= self._max_retries:
                        raise RateLimitError("rate limited", status=429) from exc
                    self._sleep(self._compute_backoff(attempt, retry_after))  # type: ignore[operator]
                    last_exc = exc
                    continue
                if 500 <= exc.code < 600:
                    if attempt >= self._max_retries:
                        raise TransientAPIError(
                            f"server error {exc.code}", status=exc.code
                        ) from exc
                    self._sleep(self._compute_backoff(attempt, retry_after))  # type: ignore[operator]
                    last_exc = exc
                    continue
                raise APIError(f"API error {exc.code}: {err_body[:200]}", status=exc.code) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                log.warning("Hetzner API %s %s network error: %s", method, path, exc)
                if attempt >= self._max_retries:
                    raise TransientAPIError(f"network error: {exc}") from exc
                self._sleep(self._compute_backoff(attempt, None))  # type: ignore[operator]
                last_exc = exc
                continue
            if not payload:
                return {}
            try:
                return json.loads(payload)  # type: ignore[no-any-return]
            except json.JSONDecodeError as exc:
                raise APIError(f"invalid JSON from Hetzner: {exc}") from exc

        # Should never get here, but keeps type-checker happy.
        raise TransientAPIError(f"exhausted retries: {last_exc!r}")

    # ---- Public API ---------------------------------------------------------
    def find_zone(self, zone_name: str) -> Zone | None:
        data = self._request("GET", "/zones", query={"name": zone_name})
        for z in data.get("zones", []):
            if isinstance(z, dict) and z.get("name") == zone_name:
                return Zone.from_api(z)
        return None

    def list_records(self, zone_id: str, *, per_page: int = 500) -> list[Record]:
        data = self._request("GET", "/records", query={"zone_id": zone_id, "per_page": per_page})
        return [Record.from_api(r) for r in data.get("records", []) if isinstance(r, dict)]

    def create_record(
        self,
        *,
        zone_id: str,
        name: str,
        type: str,  # noqa: A002 — Hetzner API uses "type"
        value: str,
        ttl: int,
    ) -> Record:
        payload = {"zone_id": zone_id, "name": name, "type": type, "value": value, "ttl": ttl}
        data = self._request("POST", "/records", json_body=payload)
        return Record.from_api(data.get("record", data))

    def update_record(
        self,
        record_id: str,
        *,
        zone_id: str,
        name: str,
        type: str,  # noqa: A002 — Hetzner API uses "type"
        value: str,
        ttl: int,
    ) -> Record:
        payload = {"zone_id": zone_id, "name": name, "type": type, "value": value, "ttl": ttl}
        data = self._request(
            "PUT",
            f"/records/{urllib.parse.quote(record_id, safe='')}",
            json_body=payload,
        )
        return Record.from_api(data.get("record", data))


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
