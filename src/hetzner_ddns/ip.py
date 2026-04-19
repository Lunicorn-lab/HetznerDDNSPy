"""Public-IP discovery with provider fallback and strict validation."""

from __future__ import annotations

import logging
import random
import ssl
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from hetzner_ddns.errors import IPLookupError, ValidationError
from hetzner_ddns.validation import validate_ipv4, validate_ipv6

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: Final[float] = 10.0


@dataclass(frozen=True, slots=True)
class Provider:
    """Public-IP provider endpoint."""

    name: str
    url: str


IPV4_PROVIDERS: Final[tuple[Provider, ...]] = (
    Provider("icanhazip", "https://ipv4.icanhazip.com"),
    Provider("ifconfig.me", "https://ifconfig.me/ip"),
    Provider("ipify", "https://api.ipify.org"),
)

IPV6_PROVIDERS: Final[tuple[Provider, ...]] = (
    Provider("icanhazip", "https://ipv6.icanhazip.com"),
    Provider("ifconfig.co", "https://ifconfig.co/ip"),
    Provider("ipify", "https://api6.ipify.org"),
)


def _fetch(url: str, *, timeout: float, ssl_context: ssl.SSLContext | None) -> str:
    req = urllib.request.Request(  # noqa: S310 — https URL validated below
        url,
        headers={"User-Agent": "hetzner-ddns/2.0 (+https://github.com/Lunicorn/HetznerDDNSPy)"},
        method="GET",
    )
    if not url.startswith("https://"):
        raise ValidationError(f"Refusing non-HTTPS IP provider URL: {url}")
    ctx = ssl_context or ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    with urllib.request.urlopen(  # noqa: S310  # nosec B310
        req, timeout=timeout, context=ctx
    ) as resp:
        raw: bytes = resp.read(256)
    return raw.decode("ascii", errors="strict").strip()


def _discover(
    providers: Iterable[Provider],
    *,
    validator: object,
    timeout: float,
    ssl_context: ssl.SSLContext | None,
    shuffle: bool,
) -> str:
    candidates = list(providers)
    if shuffle:
        random.shuffle(candidates)
    errors: list[str] = []
    for p in candidates:
        try:
            value = _fetch(p.url, timeout=timeout, ssl_context=ssl_context)
            validated: str = validator(value)  # type: ignore[operator]
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.debug("provider %s failed: %s", p.name, exc)
            errors.append(f"{p.name}: {exc}")
            continue
        except ValidationError as exc:
            log.debug("provider %s returned invalid data: %s", p.name, exc)
            errors.append(f"{p.name}: {exc}")
            continue
        else:
            log.debug("provider %s -> %s", p.name, validated)
            return validated
    raise IPLookupError("All providers failed: " + "; ".join(errors))


def discover_ipv4(
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    providers: Iterable[Provider] = IPV4_PROVIDERS,
    ssl_context: ssl.SSLContext | None = None,
    shuffle: bool = True,
) -> str:
    """Return the machine's public IPv4, raising :class:`IPLookupError` on total failure."""
    return _discover(
        providers,
        validator=validate_ipv4,
        timeout=timeout,
        ssl_context=ssl_context,
        shuffle=shuffle,
    )


def discover_ipv6(
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    providers: Iterable[Provider] = IPV6_PROVIDERS,
    ssl_context: ssl.SSLContext | None = None,
    shuffle: bool = True,
) -> str:
    """Return the machine's public IPv6, raising :class:`IPLookupError` on total failure."""
    return _discover(
        providers,
        validator=validate_ipv6,
        timeout=timeout,
        ssl_context=ssl_context,
        shuffle=shuffle,
    )
