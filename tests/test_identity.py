import base64
import json

from app import identity, main
from app.config import settings


def _jwt(claims: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJFUzI1NiJ9.{body}.sig"


def test_claims_from_alb_headers():
    # Email comes from the userinfo claims (x-amzn-oidc-data); groups only exist in the
    # access token (x-amzn-oidc-accesstoken), exactly as the ALB forwards them.
    ident = identity.identity_from_request(
        {
            "x-amzn-oidc-identity": "sub-123",
            "x-amzn-oidc-data": _jwt({"sub": "sub-123", "email": "priya@demo.local"}),
            "x-amzn-oidc-accesstoken": _jwt(
                {"sub": "sub-123", "cognito:groups": ["finance", "procurement"]}
            ),
        },
        "fallback@demo.local",
    )
    assert ident.email == "priya@demo.local"
    assert ident.subject == "sub-123"
    assert ident.groups == ("finance", "procurement")


def test_signed_in_without_groups_has_none():
    ident = identity.identity_from_request(
        {
            "x-amzn-oidc-data": _jwt({"email": "nobody@demo.local"}),
            "x-amzn-oidc-accesstoken": _jwt({"sub": "s"}),
        },
        "x",
    )
    assert ident.groups == ()


def test_local_headers_and_fallback():
    ident = identity.identity_from_request(
        {"x-demo-user": "me@demo.local", "x-demo-groups": "finance"}, "x"
    )
    assert (ident.email, ident.groups) == ("me@demo.local", ("finance",))
    anon = identity.identity_from_request({}, "fallback@demo.local")
    assert anon.email == "fallback@demo.local"
    assert anon.groups == ("*",)


def test_garbage_jwt_is_ignored():
    ident = identity.identity_from_request(
        {"x-amzn-oidc-data": "not-a-jwt", "x-amzn-oidc-identity": "s"}, "x"
    )
    assert ident.email == "s"


def test_group_scope_enforced(web, monkeypatch):
    monkeypatch.setattr(settings, "allowed_groups_raw", "procurement,finance")
    ok = web.get(
        "/",
        headers={
            "x-amzn-oidc-data": _jwt({"email": "p@demo.local"}),
            "x-amzn-oidc-accesstoken": _jwt({"cognito:groups": ["finance"]}),
        },
    )
    assert ok.status_code == 200 and "p@demo.local" in ok.text
    denied = web.get(
        "/",
        headers={
            "x-amzn-oidc-data": _jwt({"email": "e@demo.local"}),
            "x-amzn-oidc-accesstoken": _jwt({"cognito:groups": ["engineering"]}),
        },
    )
    assert denied.status_code == 403
    assert "not available to you" in denied.text
    assert web.get("/healthz").status_code == 200  # health checks are exempt


def test_no_restriction_when_unset(web, monkeypatch):
    monkeypatch.setattr(settings, "allowed_groups_raw", "")
    r = web.get(
        "/",
        headers={
            "x-amzn-oidc-data": _jwt({"email": "x@demo.local"}),
            "x-amzn-oidc-accesstoken": _jwt({"cognito:groups": []}),
        },
    )
    assert r.status_code == 200
    assert main.current_user  # module import sanity
