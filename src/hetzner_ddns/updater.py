"""Reconciliation logic — pure, easily testable."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from hetzner_ddns.config import Config
from hetzner_ddns.errors import APIError, IPLookupError
from hetzner_ddns.hetzner import HetznerDNSClient, Record, Zone
from hetzner_ddns.ip import discover_ipv4, discover_ipv6
from hetzner_ddns.state import IPState, StateStore

log = logging.getLogger(__name__)

RecordType = Literal["A", "AAAA"]


@dataclass(frozen=True, slots=True)
class PlannedAction:
    """A single intended mutation to the zone."""

    kind: Literal["create", "update", "noop"]
    type: RecordType
    name: str
    value: str
    existing_id: str | None = None


def _api_name(record: str) -> str:
    """Hetzner API uses an empty string for the apex record."""
    return "" if record == "@" else record


def plan_actions(
    *,
    zone: Zone,
    records: tuple[str, ...],
    existing: list[Record],
    new_ipv4: str | None,
    new_ipv6: str | None,
) -> list[PlannedAction]:
    """Compute the minimal set of mutations to bring Hetzner in sync with the public IPs."""
    plans: list[PlannedAction] = []

    for rec in records:
        api_n = _api_name(rec)
        if new_ipv4 is not None:
            plans.append(_diff_single(existing, api_n, "A", new_ipv4))
        if new_ipv6 is not None:
            plans.append(_diff_single(existing, api_n, "AAAA", new_ipv6))
    return plans


def _diff_single(
    existing: list[Record],
    api_name: str,
    rec_type: RecordType,
    new_value: str,
) -> PlannedAction:
    for r in existing:
        if r.name == api_name and r.type == rec_type:
            if r.value == new_value:
                return PlannedAction("noop", rec_type, api_name, new_value, r.id)
            return PlannedAction("update", rec_type, api_name, new_value, r.id)
    return PlannedAction("create", rec_type, api_name, new_value, None)


@dataclass(frozen=True, slots=True)
class RunResult:
    """Summary of one update pass."""

    ipv4: str | None
    ipv6: str | None
    ip_changed: bool
    planned: int
    created: int
    updated: int
    skipped: int
    dry_run: bool


def run_once(  # noqa: PLR0912 — branches mirror the discover/plan/apply pipeline
    config: Config,
    *,
    client: HetznerDNSClient,
    store: StateStore,
    dry_run: bool = False,
) -> RunResult:
    """Execute a single reconciliation pass. Never sleeps or loops."""
    prev = store.load()

    new_v4 = None
    new_v6 = None
    if config.ipv4_enabled:
        try:
            new_v4 = discover_ipv4()
        except IPLookupError as exc:
            log.warning("ipv4 discovery failed: %s", exc)
    if config.ipv6_enabled:
        try:
            new_v6 = discover_ipv6()
        except IPLookupError as exc:
            log.info("ipv6 discovery failed: %s", exc)

    ip_changed = (new_v4 != prev.ipv4) or (new_v6 != prev.ipv6)

    if not ip_changed and (new_v4 or new_v6):
        log.info("public IPs unchanged — skipping Hetzner sync (v4=%s v6=%s)", new_v4, new_v6)
        return RunResult(new_v4, new_v6, False, 0, 0, 0, 0, dry_run)

    zone = client.find_zone(config.zone)
    if zone is None:
        raise APIError(f"zone {config.zone!r} not found in Hetzner account")

    existing = client.list_records(zone.id)
    plans = plan_actions(
        zone=zone,
        records=config.records,
        existing=existing,
        new_ipv4=new_v4,
        new_ipv6=new_v6,
    )

    created = updated = skipped = 0
    for plan in plans:
        if plan.kind == "noop":
            skipped += 1
            log.debug("noop %s %s = %s", plan.type, plan.name or "@", plan.value)
            continue
        if dry_run:
            log.info(
                "[dry-run] would %s %s %s -> %s", plan.kind, plan.type, plan.name or "@", plan.value
            )
            continue
        if plan.kind == "create":
            client.create_record(
                zone_id=zone.id,
                name=plan.name,
                type=plan.type,
                value=plan.value,
                ttl=config.ttl,
            )
            created += 1
            log.info("created %s %s = %s", plan.type, plan.name or "@", plan.value)
        elif plan.kind == "update":
            if plan.existing_id is None:  # invariant from plan_actions — defensive
                raise APIError(f"update plan for {plan.name!r} has no existing_id")
            client.update_record(
                plan.existing_id,
                zone_id=zone.id,
                name=plan.name,
                type=plan.type,
                value=plan.value,
                ttl=config.ttl,
            )
            updated += 1
            log.info("updated %s %s = %s", plan.type, plan.name or "@", plan.value)

    if not dry_run:
        store.save(IPState(ipv4=new_v4, ipv6=new_v6))

    return RunResult(
        ipv4=new_v4,
        ipv6=new_v6,
        ip_changed=True,
        planned=len(plans),
        created=created,
        updated=updated,
        skipped=skipped,
        dry_run=dry_run,
    )
