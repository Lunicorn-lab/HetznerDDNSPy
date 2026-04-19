"""Integration tests for updater error branches."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from hetzner_ddns.config import Config
from hetzner_ddns.errors import APIError, IPLookupError
from hetzner_ddns.hetzner import HetznerDNSClient
from hetzner_ddns.state import StateStore
from hetzner_ddns.updater import run_once

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


@pytest.mark.integration
class TestUpdaterErrors:
    def test_ipv4_failure_still_proceeds_with_ipv6(
        self,
        fake_api: HTTPServer,
        api_client: HetznerDNSClient,
        sample_config: Config,
        state_store: StateStore,
    ) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_json(
            {"zones": [{"id": "z1", "name": "example.com"}]}
        )
        fake_api.expect_request("/records", method="GET").respond_with_json({"records": []})
        fake_api.expect_request("/records", method="POST").respond_with_json(
            {
                "record": {
                    "id": "new",
                    "name": "",
                    "type": "AAAA",
                    "value": "2001:db8::1",
                    "zone_id": "z1",
                    "ttl": 300,
                }
            }
        )
        with (
            patch(
                "hetzner_ddns.updater.discover_ipv4",
                side_effect=IPLookupError("no ipv4"),
            ),
            patch("hetzner_ddns.updater.discover_ipv6", return_value="2001:db8::1"),
        ):
            result = run_once(sample_config, client=api_client, store=state_store)
        assert result.ipv4 is None
        assert result.ipv6 == "2001:db8::1"

    def test_zone_missing_raises(
        self,
        fake_api: HTTPServer,
        api_client: HetznerDNSClient,
        sample_config: Config,
        state_store: StateStore,
    ) -> None:
        fake_api.expect_request("/zones", method="GET").respond_with_json({"zones": []})
        with (
            patch("hetzner_ddns.updater.discover_ipv4", return_value="1.2.3.4"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value=None),
            pytest.raises(APIError, match="not found"),
        ):
            run_once(sample_config, client=api_client, store=state_store)
