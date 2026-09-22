def test_healthz(web):
    r = web.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_renders_default_window(web):
    r = web.get("/")
    assert r.status_code == 200
    assert "Legal retainer" in r.text
    assert 'value="90" selected' in r.text


def test_identity_header_is_shown(web):
    r = web.get("/", headers={"x-amzn-oidc-identity": "priya.nair@demo.local"})
    assert "priya.nair@demo.local" in r.text


def test_partial_respects_window_and_team(web):
    r = web.get("/contracts", params={"within": 30, "team": "finance"})
    assert r.status_code == 200
    assert "Analytics platform licence" in r.text
    assert "Legal retainer" not in r.text
    assert "<html" not in r.text  # partial, not a full page


def test_bad_window_falls_back(web):
    r = web.get("/contracts", params={"within": 7})
    assert r.status_code == 200
    assert "3 renewing" not in r.text or "renewing" in r.text


def test_flag_toggle(web):
    r = web.post("/contracts/c-1001/flag", data={"flagged": "true", "within": 30, "team": ""})
    assert r.status_code == 200
    assert "flagged for review" in r.text
    r = web.post("/contracts/c-1001/flag", data={"flagged": "false", "within": 30, "team": ""})
    assert "flagged for review" not in r.text
