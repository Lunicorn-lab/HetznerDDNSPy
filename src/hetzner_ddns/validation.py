# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict input validation — defence in depth against API injection & config abuse."""

from __future__ import annotations

import ipaddress
import re
from typing import Final

from hetzner_ddns.errors import ValidationError

# RFC 1123 hostname labels, with single '@' allowed for apex records
_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?=.{1,63}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)
_ZONE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
_RECORD_NAME_MAX: Final[int] = 255


def validate_zone(zone: str) -> str:
    """Validate a DNS zone (apex domain like ``example.com``). Returns normalised form."""
    if not isinstance(zone, str):
        raise ValidationError("ZONE must be a string")
    zone = zone.strip().rstrip(".").lower()
    if not zone or not _ZONE_RE.match(zone):
        raise ValidationError(f"Invalid zone name: {zone!r}")
    return zone


def validate_record_name(name: str) -> str:
    """Validate a record name. ``@`` means apex. Returns the original token."""
    if not isinstance(name, str):
        raise ValidationError("Record name must be a string")
    name = name.strip()
    if name == "@":
        return name
    if len(name) > _RECORD_NAME_MAX:
        raise ValidationError(f"Record name too long: {name!r}")
    for label in name.split("."):
        if not _LABEL_RE.match(label):
            raise ValidationError(f"Invalid record label: {label!r} in {name!r}")
    return name


def validate_ipv4(addr: str) -> str:
    """Validate an IPv4 address. Rejects private/reserved ranges unless explicitly allowed."""
    if not isinstance(addr, str):
        raise ValidationError("IPv4 must be a string")
    addr = addr.strip()
    try:
        parsed = ipaddress.IPv4Address(addr)
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise ValidationError(f"Invalid IPv4: {addr!r}") from exc
    if parsed.is_loopback or parsed.is_link_local or parsed.is_multicast or parsed.is_unspecified:
        raise ValidationError(f"Refusing non-routable IPv4: {addr}")
    return str(parsed)


def validate_ipv6(addr: str) -> str:
    """Validate an IPv6 address."""
    if not isinstance(addr, str):
        raise ValidationError("IPv6 must be a string")
    addr = addr.strip()
    try:
        parsed = ipaddress.IPv6Address(addr)
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise ValidationError(f"Invalid IPv6: {addr!r}") from exc
    if parsed.is_loopback or parsed.is_link_local or parsed.is_multicast or parsed.is_unspecified:
        raise ValidationError(f"Refusing non-routable IPv6: {addr}")
    return parsed.compressed


def validate_ttl(ttl: int) -> int:
    """Validate a DNS TTL (Hetzner allows 60-86400)."""
    if not isinstance(ttl, int) or isinstance(ttl, bool):
        raise ValidationError("TTL must be an integer")
    if ttl < 60 or ttl > 86400:
        raise ValidationError(f"TTL out of range [60, 86400]: {ttl}")
    return ttl


def validate_interval(interval: int) -> int:
    """Validate a daemon-mode interval (seconds)."""
    if not isinstance(interval, int) or isinstance(interval, bool):
        raise ValidationError("INTERVAL must be an integer")
    if interval < 10 or interval > 86400:
        raise ValidationError(f"INTERVAL out of range [10, 86400]: {interval}")
    return interval
