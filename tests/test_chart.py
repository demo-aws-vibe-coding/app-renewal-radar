"""Tests for the expiry bar chart — data function and web route."""

from datetime import date

from app import renewals

TODAY = date(2026, 9, 21)


def test_expiring_by_month_returns_six_buckets(fixture_client):
    user = _user()
    buckets = renewals.expiring_by_month(fixture_client, user, today=TODAY)
    assert len(buckets) == 6


def test_expiring_by_month_labels_start_from_today(fixture_client):
    user = _user()
    buckets = renewals.expiring_by_month(fixture_client, user, today=TODAY)
    labels = [b.label for b in buckets]
    # TODAY = 2026-09-21, so first month is Sep 2026
    assert labels[0] == "Sep 2026"
    assert labels[5] == "Feb 2027"


def test_expiring_by_month_counts(fixture_client):
    user = _user()
    buckets = renewals.expiring_by_month(fixture_client, user, today=TODAY)
    by_label = {b.label: b.count for b in buckets}
    # Sep 2026: c-1007 (2026-09-28)
    assert by_label["Sep 2026"] == 1
    # Oct 2026: c-1001, c-1002 (c-1009 is terminated, excluded)
    assert by_label["Oct 2026"] == 2
    # Nov 2026: c-1003, c-1005
    assert by_label["Nov 2026"] == 2
    # Dec 2026: c-1004, c-1010
    assert by_label["Dec 2026"] == 2
    # Jan 2027: no contracts
    assert by_label["Jan 2027"] == 0
    # Feb 2027: c-1006
    assert by_label["Feb 2027"] == 1


def test_expiring_by_month_excludes_terminated(fixture_client):
    user = _user()
    buckets = renewals.expiring_by_month(fixture_client, user, today=TODAY)
    # c-1009 (terminated, renewal 2026-10-12) must not be counted
    by_label = {b.label: b.count for b in buckets}
    assert by_label["Oct 2026"] == 2  # not 3


def test_chart_route_ok(web):
    resp = web.get("/chart/expiring")
    assert resp.status_code == 200
    assert "chart-card" in resp.text
    assert "expiry-chart" in resp.text


def test_chart_route_shows_month_labels(web):
    resp = web.get("/chart/expiring")
    assert "Sep 2026" in resp.text
    assert "Feb 2027" in resp.text


def _user():
    from app.data import Caller

    return Caller(email="test@demo.local", token="")
