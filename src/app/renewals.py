"""Renewal Radar's logic: which contracts renew soon and which need attention.

Kept apart from ``data.py`` (the platform's data client) so the tool's own rules are
easy to read, test and change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.data import Caller, Contract, DataClient, Vendor


@dataclass
class ContractView:
    contract: Contract
    vendor: Vendor | None
    days_left: int
    flagged: bool = False
    tags: list[str] = field(default_factory=list)


def renewals(
    client: DataClient,
    user: Caller,
    *,
    today: date,
    within_days: int,
    team: str | None = None,
    auto_renew: bool = False,
) -> list[ContractView]:
    """Contracts renewing within ``within_days`` of ``today``, soonest first.

    Rows are tagged so the page can highlight what needs attention:
    ``notice-passed`` when the cancellation window has closed, ``auto-renews`` when
    doing nothing means paying again.
    """
    vendors = {v.id: v for v in client.vendors(user)}
    flagged = client.flagged(user)
    rows: list[ContractView] = []
    for c in client.contracts(user):
        if c.status != "active":
            continue
        if team and c.owner_team != team:
            continue
        if auto_renew and not c.auto_renews:
            continue
        days = c.days_until_renewal(today)
        if days < 0 or days > within_days:
            continue
        tags = []
        if c.auto_renews:
            tags.append("auto-renews")
        if c.notice_deadline() < today:
            tags.append("notice-passed")
        rows.append(
            ContractView(
                contract=c,
                vendor=vendors.get(c.vendor_id),
                days_left=days,
                flagged=c.id in flagged,
                tags=tags,
            )
        )
    rows.sort(key=lambda r: r.days_left)
    return rows


def teams(client: DataClient, user: Caller) -> list[str]:
    return sorted({c.owner_team for c in client.contracts(user)})
