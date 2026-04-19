"""Unit tests for the Hetzner API client against a loopback HTTP fixture."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hetzner_ddns.errors import APIError, AuthError, RateLimitError, TransientAPIError
from hetzner_ddns.hetzner import HetznerDNSClient

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


class TestClientBasics:
    def test_rejects_non_https_non_loopback(self) -> None:
        with pytest.raises(ValueError, match="non-HTTPS"):
            HetznerDNSClient("tok_xxxxxxxxxxxxxxxx", base_url="http://hetzner.example.com")

    def test_rejects_empty_token(self) -> None:
        with pytest.raises(ValueError, match="api_token"):
            HetznerDNSClient("")


class TestFindZone:
    def test_hit(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request(
            "/zones",
            query_string="name=example.com",
            method="GET",
        ).respond_with_json({"zones": [{"id": "zone1", "name": "example.com"}]})
        zone = api_client.find_zone("example.com")
        assert zone is not None
        assert zone.id == "zone1"

    def test_miss(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_json({"zones": []})
        assert api_client.find_zone("example.com") is None


class TestListRecords:
    def test_returns_parsed_records(
        self, fake_api: HTTPServer, api_client: HetznerDNSClient
    ) -> None:
        fake_api.expect_request("/records", method="GET").respond_with_json(
            {
                "records": [
                    {
                        "id": "r1",
                        "name": "",
                        "type": "A",
                        "value": "1.2.3.4",
                        "zone_id": "z1",
                        "ttl": 300,
                    },
                    {
                        "id": "r2",
                        "name": "www",
                        "type": "AAAA",
                        "value": "2001:db8::1",
                        "zone_id": "z1",
                        "ttl": 300,
                    },
                ]
            }
        )
        records = api_client.list_records("z1")
        assert len(records) == 2
        assert records[0].id == "r1"
        assert records[1].type == "AAAA"


class TestCreateAndUpdate:
    def test_create(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request("/records", method="POST").respond_with_json(
            {
                "record": {
                    "id": "new1",
                    "name": "www",
                    "type": "A",
                    "value": "1.2.3.4",
                    "zone_id": "z1",
                    "ttl": 300,
                }
            }
        )
        rec = api_client.create_record(zone_id="z1", name="www", type="A", value="1.2.3.4", ttl=300)
        assert rec.id == "new1"

    def test_update(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request("/records/abc", method="PUT").respond_with_json(
            {
                "record": {
                    "id": "abc",
                    "name": "www",
                    "type": "A",
                    "value": "5.6.7.8",
                    "zone_id": "z1",
                    "ttl": 300,
                }
            }
        )
        rec = api_client.update_record(
            "abc", zone_id="z1", name="www", type="A", value="5.6.7.8", ttl=300
        )
        assert rec.value == "5.6.7.8"


class TestErrorHandling:
    def test_401_raises_auth(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request("/zones").respond_with_data("nope", status=401)
        with pytest.raises(AuthError):
            api_client.find_zone("example.com")

    def test_429_retries_then_raises(
        self, fake_api: HTTPServer, api_client: HetznerDNSClient
    ) -> None:
        fake_api.expect_request("/zones").respond_with_data("rate", status=429)
        with pytest.raises(RateLimitError):
            api_client.find_zone("example.com")

    def test_5xx_retries_then_raises(
        self, fake_api: HTTPServer, api_client: HetznerDNSClient
    ) -> None:
        fake_api.expect_request("/zones").respond_with_data("boom", status=503)
        with pytest.raises(TransientAPIError):
            api_client.find_zone("example.com")

    def test_4xx_other_raises_apierror(
        self, fake_api: HTTPServer, api_client: HetznerDNSClient
    ) -> None:
        fake_api.expect_request("/zones").respond_with_data("nope", status=400)
        with pytest.raises(APIError):
            api_client.find_zone("example.com")

    def test_invalid_json_raises(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request("/zones").respond_with_data(
            "not json at all", content_type="application/json"
        )
        with pytest.raises(APIError, match="invalid JSON"):
            api_client.find_zone("example.com")


class TestAuthHeader:
    def test_sends_auth_header(self, fake_api: HTTPServer, api_client: HetznerDNSClient) -> None:
        fake_api.expect_request(
            "/zones",
            headers={"Auth-API-Token": "tok_testtoken1234567890"},
        ).respond_with_json({"zones": []})
        api_client.find_zone("example.com")
