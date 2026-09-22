from datetime import date

from app import data

TODAY = date(2026, 9, 21)


def test_window_filters_and_sorts(fixture_client):
    rows = data.renewals(fixture_client, "u", today=TODAY, within_days=30)
    ids = [r.contract.id for r in rows]
    assert ids == ["c-1007", "c-1001", "c-1002"]
    assert [r.days_left for r in rows] == sorted(r.days_left for r in rows)


def test_terminated_contracts_are_hidden(fixture_client):
    rows = data.renewals(fixture_client, "u", today=TODAY, within_days=365)
    assert "c-1009" not in {r.contract.id for r in rows}


def test_team_filter(fixture_client):
    rows = data.renewals(fixture_client, "u", today=TODAY, within_days=365, team="finance")
    assert {r.contract.owner_team for r in rows} == {"finance"}


def test_tags_flag_risk(fixture_client):
    rows = {
        r.contract.id: r for r in data.renewals(fixture_client, "u", today=TODAY, within_days=90)
    }
    # Legal retainer renews 2026-09-28 with 30 days notice: the window closed 2026-08-29.
    assert rows["c-1007"].tags == ["auto-renews", "notice-passed"]
    # Cloud hosting: no auto-renew, notice deadline still ahead.
    assert rows["c-1003"].tags == []


def test_flags_round_trip(fixture_client):
    assert fixture_client.flagged("u") == set()
    fixture_client.set_flag("u", "c-1001", True)
    assert "c-1001" in fixture_client.flagged("u")
    fixture_client.set_flag("u", "c-1001", False)
    assert fixture_client.flagged("u") == set()


def test_teams_listed(fixture_client):
    assert data.teams(fixture_client, "u") == [
        "engineering",
        "finance",
        "legal",
        "operations",
        "people-ops",
    ]


def test_notice_deadline():
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
    assert client.contracts("u") == []
    assert client.vendors("u") == []


def test_build_client_picks_platform_when_url_set(tmp_path):
    assert isinstance(data.build_client("", tmp_path, "app"), data.FixtureDataClient)
    assert isinstance(
        data.build_client("http://data-api", tmp_path, "app"), data.PlatformDataClient
    )
