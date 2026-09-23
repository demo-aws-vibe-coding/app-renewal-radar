"""The only module that touches data.

Two implementations of the same small interface:

* ``FixtureDataClient`` reads JSON files from ``fixtures/``. Used locally and in tests.
* ``PlatformDataClient`` calls the platform data API on behalf of the signed-in user.
  The API enforces the app's data scopes (SEC-8); this client just forwards identity.

Add new read methods here, one per kind of data the app shows, and mirror them in
both clients so tests keep working offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Vendor:
    id: str
    name: str
    category: str
    contact: str


@dataclass(frozen=True)
class Contract:
    id: str
    vendor_id: str
    name: str
    owner_team: str
    owner_email: str
    renewal_date: date
    notice_period_days: int
    auto_renews: bool
    status: str
    annual_value: float | None = None  # requires contracts:value:read

    def days_until_renewal(self, today: date) -> int:
        return (self.renewal_date - today).days

    def notice_deadline(self) -> date:
        from datetime import timedelta

        return self.renewal_date - timedelta(days=self.notice_period_days)


@dataclass(frozen=True)
class Caller:
    """Who the request is for. ``token`` is the user's access token as forwarded by the
    platform load balancer; the data API verifies it itself. Empty locally."""

    email: str
    token: str = ""


class DataClient(Protocol):
    def vendors(self, user: Caller) -> list[Vendor]: ...
    def contracts(self, user: Caller) -> list[Contract]: ...
    def flagged(self, user: Caller) -> set[str]: ...
    def set_flag(self, user: Caller, contract_id: str, flagged: bool) -> None: ...
    def whoami(self, user: Caller) -> dict: ...


class DataAccessDenied(Exception):
    """The platform data API refused the request: the app lacks a scope, or the token failed."""

    def __init__(self, status: int, detail: dict | str):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail = status, detail


def _parse_contract(raw: dict) -> Contract:
    return Contract(
        id=raw["id"],
        vendor_id=raw["vendor_id"],
        name=raw["name"],
        owner_team=raw["owner_team"],
        owner_email=raw["owner_email"],
        renewal_date=date.fromisoformat(raw["renewal_date"]),
        notice_period_days=int(raw.get("notice_period_days", 30)),
        auto_renews=bool(raw.get("auto_renews", False)),
        status=raw.get("status", "active"),
        annual_value=raw.get("annual_value"),
    )


class FixtureDataClient:
    """Reads fixtures/*.json. Flags are kept in memory for the life of the process."""

    def __init__(self, fixtures_dir: Path):
        self._dir = fixtures_dir
        self._flags: set[str] = set()

    def _load(self, name: str) -> list[dict]:
        path = self._dir / f"{name}.json"
        if not path.exists():
            return []
        return json.loads(path.read_text())

    def vendors(self, user: Caller) -> list[Vendor]:
        return [Vendor(**v) for v in self._load("vendors")]

    def contracts(self, user: Caller) -> list[Contract]:
        return [_parse_contract(c) for c in self._load("contracts")]

    def flagged(self, user: Caller) -> set[str]:
        return set(self._flags)

    def set_flag(self, user: Caller, contract_id: str, flagged: bool) -> None:
        if flagged:
            self._flags.add(contract_id)
        else:
            self._flags.discard(contract_id)

    def whoami(self, user: Caller) -> dict:
        return {
            "user": {"email": user.email, "groups": ["(local fixtures)"], "verified": False},
            "app": {"name": "local", "owner": "you"},
            "scopes": {},
            "row_scope": "all fixture rows (local development)",
        }


class PlatformDataClient:
    """Calls the platform data API. Identity is forwarded, never a credential."""

    def __init__(self, base_url: str, app_name: str, timeout: float = 5.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._app = app_name

    def _headers(self, user: Caller) -> dict[str, str]:
        return {"X-On-Behalf-Of": user.email, "X-App-Name": self._app, "X-User-Token": user.token}

    @staticmethod
    def _check(r: httpx.Response):
        if r.status_code in (401, 403, 404):
            try:
                detail = r.json()
            except ValueError:
                detail = r.text
            raise DataAccessDenied(r.status_code, detail)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str, user: Caller):
        return self._check(self._client.get(path, headers=self._headers(user)))

    def vendors(self, user: Caller) -> list[Vendor]:
        return [Vendor(**v) for v in self._get("/v1/vendors", user)]

    def contracts(self, user: Caller) -> list[Contract]:
        return [_parse_contract(c) for c in self._get("/v1/contracts", user)]

    def flagged(self, user: Caller) -> set[str]:
        return {f["contract_id"] for f in self._get("/v1/contracts/flags", user)}

    def set_flag(self, user: Caller, contract_id: str, flagged: bool) -> None:
        self._check(
            self._client.put(
                f"/v1/contracts/{contract_id}/flag",
                json={"flagged": flagged},
                headers=self._headers(user),
            )
        )

    def whoami(self, user: Caller) -> dict:
        return self._get("/v1/whoami", user)


def build_client(data_api_url: str, fixtures_dir: Path, app_name: str) -> DataClient:
    if data_api_url:
        return PlatformDataClient(data_api_url, app_name)
    return FixtureDataClient(fixtures_dir)
