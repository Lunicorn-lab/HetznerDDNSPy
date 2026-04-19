"""Integration tests — updater + HTTP-mocked Hetzner API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from hetzner_ddns.config import Config
from hetzner_ddns.hetzner import HetznerDNSClient
from hetzner_ddns.state import IPState, StateStore
from hetzner_ddns.updater import run_once

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


@pytest.mark.integration
class TestFirstRun:
    def test_creates_missing_records(
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
                    "type": "A",
                    "value": "1.2.3.4",
                    "zone_id": "z1",
                    "ttl": 300,
                }
            }
        )

        with (
            patch("hetzner_ddns.updater.discover_ipv4", return_value="1.2.3.4"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value="2001:db8::1"),
        ):
            result = run_once(sample_config, client=api_client, store=state_store)

        assert result.ip_changed is True
        assert result.created >= 1
        # state persisted
        assert state_store.load().ipv4 == "1.2.3.4"
        assert state_store.load().ipv6 == "2001:db8::1"


@pytest.mark.integration
class TestSkipWhenUnchanged:
    def test_no_api_calls_if_ip_same(
        self,
        fake_api: HTTPServer,
        api_client: HetznerDNSClient,
        sample_config: Config,
        state_store: StateStore,
    ) -> None:
        # Pre-seed state so it matches the discovered IPs.
        state_store.save(IPState(ipv4="1.2.3.4", ipv6="2001:db8::1"))

        with (
            patch("hetzner_ddns.updater.discover_ipv4", return_value="1.2.3.4"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value="2001:db8::1"),
        ):
            result = run_once(sample_config, client=api_client, store=state_store)

        assert result.ip_changed is False
        assert result.planned == 0
        # fake_api had no expectations → will pass check_assertions()


@pytest.mark.integration
class TestIPChangeTriggersUpdate:
    def test_update_on_change(
        self,
        fake_api: HTTPServer,
        api_client: HetznerDNSClient,
        sample_config: Config,
        state_store: StateStore,
    ) -> None:
        state_store.save(IPState(ipv4="9.9.9.9", ipv6=None))

        fake_api.expect_request("/zones", method="GET").respond_with_json(
            {"zones": [{"id": "z1", "name": "example.com"}]}
        )
        fake_api.expect_request("/records", method="GET").respond_with_json(
            {
                "records": [
                    {
                        "id": "r1",
                        "name": "",
                        "type": "A",
                        "value": "9.9.9.9",
                        "zone_id": "z1",
                        "ttl": 300,
                    },
                    {
                        "id": "r2",
                        "name": "www",
                        "type": "A",
                        "value": "9.9.9.9",
                        "zone_id": "z1",
                        "ttl": 300,
                    },
                ]
            }
        )
        fake_api.expect_request("/records/r1", method="PUT").respond_with_json(
            {
                "record": {
                    "id": "r1",
                    "name": "",
                    "type": "A",
                    "value": "1.2.3.4",
                    "zone_id": "z1",
                    "ttl": 300,
                }
            }
        )
        fake_api.expect_request("/records/r2", method="PUT").respond_with_json(
            {
                "record": {
                    "id": "r2",
                    "name": "www",
                    "type": "A",
                    "value": "1.2.3.4",
                    "zone_id": "z1",
                    "ttl": 300,
                }
            }
        )
        # Create AAAA for apex + www
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
            patch("hetzner_ddns.updater.discover_ipv4", return_value="1.2.3.4"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value="2001:db8::1"),
        ):
            result = run_once(sample_config, client=api_client, store=state_store)

        assert result.ip_changed is True
        assert result.updated == 2
        assert result.created == 2  # AAAA for apex + www


@pytest.mark.integration
class TestDryRun:
    def test_dry_run_never_mutates(
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

        with (
            patch("hetzner_ddns.updater.discover_ipv4", return_value="1.2.3.4"),
            patch("hetzner_ddns.updater.discover_ipv6", return_value=None),
        ):
            result = run_once(sample_config, client=api_client, store=state_store, dry_run=True)

        assert result.dry_run is True
        assert result.created == 0
        # State not written in dry-run
        assert state_store.load().ipv4 is None
