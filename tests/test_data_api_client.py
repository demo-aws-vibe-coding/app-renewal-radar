"""The PlatformDataClient against a fake data API (httpx transport), no network."""

import json

import httpx
import pytest

from app import data


def _transport(handler):
    return httpx.MockTransport(handler)


def _client(handler) -> data.PlatformDataClient:
    c = data.PlatformDataClient("http://data-api.test", "renewal-radar")
    c._client = httpx.Client(base_url="http://data-api.test", transport=_transport(handler))
    return c


CALLER = data.Caller(email="priya@demo.local", token="tok.en.x")


def test_forwards_identity_headers_and_parses():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(dict(req.headers))
        if req.url.path == "/v1/vendors":
            return httpx.Response(
                200, json=[{"id": "v", "name": "V", "category": "c", "contact": "x"}]
            )
        if req.url.path == "/v1/contracts/flags":
            return httpx.Response(200, json=[{"contract_id": "c-1"}])
        if req.url.path == "/v1/whoami":
            return httpx.Response(200, json={"user": {"verified": True}})
        return httpx.Response(200, json=[])

    c = _client(handler)
    assert c.vendors(CALLER)[0].name == "V"
    assert c.flagged(CALLER) == {"c-1"}
    assert c.whoami(CALLER)["user"]["verified"] is True
    assert c.contracts(CALLER) == []
    assert seen["x-app-name"] == "renewal-radar"
    assert seen["x-on-behalf-of"] == "priya@demo.local"
    assert seen["x-user-token"] == "tok.en.x"


def test_scope_denial_becomes_data_access_denied():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": "scope_denied",
                "app": "renewal-radar",
                "scope": "x:read",
                "detail": "no",
            },
        )

    with pytest.raises(data.DataAccessDenied) as e:
        _client(handler).vendors(CALLER)
    assert e.value.status == 403 and e.value.detail["scope"] == "x:read"


def test_set_flag_and_non_json_error():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, json.loads(req.content or b"{}")))
        if req.method == "PUT":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(401, text="nope")

    c = _client(handler)
    c.set_flag(CALLER, "c-1", True)
    assert calls[0] == ("PUT", "/v1/contracts/c-1/flag", {"flagged": True})
    with pytest.raises(data.DataAccessDenied) as e:
        c.vendors(CALLER)
    assert e.value.detail == "nope"


def test_denied_page(web, monkeypatch):
    def boom(*a, **k):
        raise data.DataAccessDenied(
            403,
            {
                "error": "scope_denied",
                "app": "renewal-radar",
                "scope": "employees:compensation:read",
                "detail": "ask the platform team",
            },
        )

    from app import main as app_main

    monkeypatch.setattr(app_main.client, "vendors", boom)
    r = web.get("/")
    assert r.status_code == 403
    assert "employees:compensation:read" in r.text and "platform team" in r.text


def test_whoami_page(web):
    r = web.get("/whoami", headers={"x-demo-user": "me@demo.local", "x-demo-groups": "finance"})
    assert r.status_code == 200
    assert "me@demo.local" in r.text and "local development" in r.text
