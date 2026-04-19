"""Retry/backoff behaviour of HetznerDNSClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hetzner_ddns.errors import AuthError, TransientAPIError
from hetzner_ddns.hetzner import HetznerDNSClient

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


class TestRetry:
    def test_recovers_from_one_5xx(
        self, fake_api: HTTPServer, api_client: HetznerDNSClient
    ) -> None:
        fake_api.expect_oneshot_request("/zones", method="GET").respond_with_data(
            "boom", status=503
        )
        fake_api.expect_oneshot_request("/zones", method="GET").respond_with_json(
            {"zones": [{"id": "z1", "name": "example.com"}]}
        )
        zone = api_client.find_zone("example.com")
        assert zone is not None

    def test_recovers_from_one_429(
        self, fake_api: HTTPServer, api_client: HetznerDNSClient
    ) -> None:
        fake_api.expect_oneshot_request("/zones", method="GET").respond_with_data(
            "slow down", status=429, headers={"Retry-After": "0"}
        )
        fake_api.expect_oneshot_request("/zones", method="GET").respond_with_json({"zones": []})
        assert api_client.find_zone("example.com") is None

    def test_403_is_auth_error(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_data("forbidden", status=403)
        with pytest.raises(AuthError):
            api_client.find_zone("example.com")


class TestInvalidBaseUrl:
    def test_rejects_non_http_scheme(self) -> None:
        with pytest.raises(ValueError, match="http"):
            HetznerDNSClient("tok_xxx", base_url="ftp://example.com")

    def test_allows_loopback_http(self) -> None:
        c = HetznerDNSClient("tok_xxxxxxxxxxxxxxxxx", base_url="http://127.0.0.1:1/api")
        assert c is not None


class TestPathValidation:
    def test_path_must_start_with_slash(self, api_client: HetznerDNSClient) -> None:
        with pytest.raises(ValueError, match="start with"):
            api_client._request("GET", "zones")


class TestNetworkError:
    def test_unreachable_raises_transient(self) -> None:
        # Point to a port that nothing is listening on.
        c = HetznerDNSClient(
            "tok_xxxxxxxxxxxxxxxxx",
            base_url="http://127.0.0.1:1/api",
            timeout=0.2,
            max_retries=1,
            sleep=lambda _s: None,
        )
        with pytest.raises(TransientAPIError):
            c.find_zone("example.com")
