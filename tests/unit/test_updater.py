"""Unit tests for the reconciliation planner (pure function, no HTTP)."""

from __future__ import annotations

from hetzner_ddns.hetzner import Record, Zone
from hetzner_ddns.updater import plan_actions

ZONE = Zone(id="z1", name="example.com")


def _rec(**kw: object) -> Record:
    defaults = {"id": "r1", "zone_id": "z1", "ttl": 300}
    defaults.update(kw)
    return Record(**defaults)  # type: ignore[arg-type]


class TestPlanActions:
    def test_create_when_no_existing(self) -> None:
        plans = plan_actions(
            zone=ZONE,
            records=("@",),
            existing=[],
            new_ipv4="1.2.3.4",
            new_ipv6=None,
        )
        assert len(plans) == 1
        assert plans[0].kind == "create"
        assert plans[0].type == "A"
        assert plans[0].name == ""
        assert plans[0].value == "1.2.3.4"

    def test_noop_when_up_to_date(self) -> None:
        existing = [_rec(id="r1", name="www", type="A", value="1.2.3.4")]
        plans = plan_actions(
            zone=ZONE,
            records=("www",),
            existing=existing,
            new_ipv4="1.2.3.4",
            new_ipv6=None,
        )
        assert plans[0].kind == "noop"
        assert plans[0].existing_id == "r1"

    def test_update_when_changed(self) -> None:
        existing = [_rec(id="r1", name="www", type="A", value="9.9.9.9")]
        plans = plan_actions(
            zone=ZONE,
            records=("www",),
            existing=existing,
            new_ipv4="1.2.3.4",
            new_ipv6=None,
        )
        assert plans[0].kind == "update"
        assert plans[0].existing_id == "r1"
        assert plans[0].value == "1.2.3.4"

    def test_multiple_records_and_both_families(self) -> None:
        existing = [
            _rec(id="r1", name="", type="A", value="9.9.9.9"),
            _rec(id="r2", name="", type="AAAA", value="2001:db8::1"),
            _rec(id="r3", name="www", type="A", value="1.2.3.4"),
        ]
        plans = plan_actions(
            zone=ZONE,
            records=("@", "www"),
            existing=existing,
            new_ipv4="1.2.3.4",
            new_ipv6="2001:db8::1",
        )
        kinds = [p.kind for p in plans]
        assert kinds.count("update") == 1  # apex A changed
        assert kinds.count("noop") == 2  # apex AAAA + www A
        assert kinds.count("create") == 1  # www AAAA
