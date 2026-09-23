"""The platform data client, as the template ships it (before any tool-specific logic)."""

from datetime import date
from pathlib import Path

from app import data

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_fixture_client_reads_seed_data(fixture_client):
    user = data.Caller(email="u@demo.local")
    assert len(fixture_client.vendors(user)) == 8
    contracts = fixture_client.contracts(user)
    assert len(contracts) == 10
    assert {c.status for c in contracts} == {"active", "terminated"}


def test_flags_round_trip(fixture_client):
    user = data.Caller(email="u@demo.local")
    assert fixture_client.flagged(user) == set()
    fixture_client.set_flag(user, "c-1001", True)
    assert "c-1001" in fixture_client.flagged(user)
    fixture_client.set_flag(user, "c-1001", False)
    assert fixture_client.flagged(user) == set()


def test_local_whoami_explains_itself(fixture_client):
    info = fixture_client.whoami(data.Caller(email="u@demo.local"))
    assert info["user"]["verified"] is False
    assert "local" in info["row_scope"]


def test_contract_helpers():
    c = data.Contract(
        id="x",
        vendor_id="v",
        name="n",
        owner_team="t",
        owner_email="e",
        renewal_date=date(2026, 12, 31),
        notice_period_days=31,
        auto_renews=False,
        status="active",
    )
    assert c.notice_deadline() == date(2026, 11, 30)
    assert c.days_until_renewal(date(2026, 12, 1)) == 30


def test_missing_fixture_file_is_empty(tmp_path):
    client = data.FixtureDataClient(tmp_path)
    assert client.contracts(data.Caller(email="u")) == []
    assert client.vendors(data.Caller(email="u")) == []


def test_build_client_picks_platform_when_url_set(tmp_path):
    assert isinstance(data.build_client("", FIXTURES, "app"), data.FixtureDataClient)
    assert isinstance(
        data.build_client("http://data-api", tmp_path, "app"), data.PlatformDataClient
    )
