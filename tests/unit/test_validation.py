"""Unit tests for validation helpers."""

from __future__ import annotations

import pytest

from hetzner_ddns.errors import ValidationError
from hetzner_ddns.validation import (
    validate_interval,
    validate_ipv4,
    validate_ipv6,
    validate_record_name,
    validate_ttl,
    validate_zone,
)


class TestValidateZone:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("example.com", "example.com"),
            ("Example.COM", "example.com"),
            ("example.com.", "example.com"),
            ("sub.example.co.uk", "sub.example.co.uk"),
        ],
    )
    def test_valid(self, raw: str, expected: str) -> None:
        assert validate_zone(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            " ",
            "no-tld",
            ".example.com",
            "example..com",
            "example.-com",
            "example.com-",
            "exa mple.com",
            "foo.bar.123",  # TLD must be letters
            "x" * 300,
            "a." * 130 + "com",
        ],
    )
    def test_invalid(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            validate_zone(raw)

    def test_non_string(self) -> None:
        with pytest.raises(ValidationError):
            validate_zone(123)  # type: ignore[arg-type]


class TestValidateRecordName:
    @pytest.mark.parametrize("name", ["@", "www", "homelab", "sub.domain", "a-b-c"])
    def test_valid(self, name: str) -> None:
        assert validate_record_name(name) == name

    @pytest.mark.parametrize("name", ["", " ", "-bad", "bad-", "has space", "a" * 300])
    def test_invalid(self, name: str) -> None:
        with pytest.raises(ValidationError):
            validate_record_name(name)


class TestValidateIPs:
    def test_ipv4_valid(self) -> None:
        assert validate_ipv4("93.184.216.34") == "93.184.216.34"

    @pytest.mark.parametrize(
        "addr",
        [
            "127.0.0.1",
            "169.254.1.1",
            "224.0.0.1",
            "0.0.0.0",  # noqa: S104 — test data for a negative case
            "not-an-ip",
            "",
            "999.1.1.1",
        ],
    )
    def test_ipv4_invalid(self, addr: str) -> None:
        with pytest.raises(ValidationError):
            validate_ipv4(addr)

    def test_ipv6_valid(self) -> None:
        assert validate_ipv6("2001:db8::1") == "2001:db8::1"

    @pytest.mark.parametrize("addr", ["::1", "fe80::1", "ff00::1", "::", "nope", ""])
    def test_ipv6_invalid(self, addr: str) -> None:
        with pytest.raises(ValidationError):
            validate_ipv6(addr)


class TestValidateTTLAndInterval:
    @pytest.mark.parametrize("ttl", [60, 300, 3600, 86400])
    def test_ttl_valid(self, ttl: int) -> None:
        assert validate_ttl(ttl) == ttl

    @pytest.mark.parametrize("ttl", [0, 59, 86401, 100_000])
    def test_ttl_invalid(self, ttl: int) -> None:
        with pytest.raises(ValidationError):
            validate_ttl(ttl)

    def test_ttl_rejects_bool(self) -> None:
        with pytest.raises(ValidationError):
            validate_ttl(True)

    @pytest.mark.parametrize("interval", [10, 60, 300, 86400])
    def test_interval_valid(self, interval: int) -> None:
        assert validate_interval(interval) == interval

    @pytest.mark.parametrize("interval", [0, 9, 86401])
    def test_interval_invalid(self, interval: int) -> None:
        with pytest.raises(ValidationError):
            validate_interval(interval)
