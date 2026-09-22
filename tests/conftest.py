from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import data, main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TODAY = date(2026, 9, 21)


@pytest.fixture
def fixture_client() -> data.FixtureDataClient:
    return data.FixtureDataClient(FIXTURES)


@pytest.fixture
def web(monkeypatch, fixture_client) -> TestClient:
    """Test client with a fresh fixture data client and a fixed 'today'."""
    monkeypatch.setattr(main, "client", fixture_client)

    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY

    monkeypatch.setattr(main, "date", FixedDate)
    return TestClient(main.app)
