"""Tests for public-IP discovery."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hetzner_ddns.errors import IPLookupError, ValidationError
from hetzner_ddns.ip import Provider, discover_ipv4, discover_ipv6


class TestDiscoverIPv4:
    def test_happy_path(self) -> None:
        with patch("hetzner_ddns.ip._fetch", return_value="93.184.216.34"):
            assert discover_ipv4(shuffle=False) == "93.184.216.34"

    def test_falls_through_invalid(self) -> None:
        outputs = iter(["not-an-ip", "127.0.0.1", "93.184.216.34"])

        def fake(*_a: object, **_kw: object) -> str:
            return next(outputs)

        with patch("hetzner_ddns.ip._fetch", side_effect=fake):
            assert discover_ipv4(shuffle=False) == "93.184.216.34"

    def test_all_fail(self) -> None:
        with (
            patch("hetzner_ddns.ip._fetch", side_effect=OSError("boom")),
            pytest.raises(IPLookupError),
        ):
            discover_ipv4(shuffle=False, timeout=0.1)

    def test_rejects_non_https_provider(self) -> None:
        bad = [Provider("bad", "http://example.com/ip")]
        with pytest.raises(IPLookupError):
            discover_ipv4(providers=bad, shuffle=False, timeout=0.1)


class TestDiscoverIPv6:
    def test_happy_path(self) -> None:
        with patch("hetzner_ddns.ip._fetch", return_value="2001:db8::1"):
            assert discover_ipv6(shuffle=False) == "2001:db8::1"

    def test_rejects_loopback(self) -> None:
        with (
            patch("hetzner_ddns.ip._fetch", return_value="::1"),
            pytest.raises(IPLookupError),
        ):
            discover_ipv6(shuffle=False, timeout=0.1)

    def test_validation_error_propagates_as_lookup_error(self) -> None:
        def bad(*_a: object, **_kw: object) -> str:
            raise ValidationError("parser is broken")

        with patch("hetzner_ddns.ip._fetch", side_effect=bad), pytest.raises(IPLookupError):
            discover_ipv6(shuffle=False, timeout=0.1)
