"""Who is using the app.

Sign-in happens before traffic reaches the app: the platform load balancer runs the
Cognito flow and forwards two headers on every request.

* ``x-amzn-oidc-identity``: the user's stable id (Cognito ``sub``).
* ``x-amzn-oidc-data``: a JWT with the user's profile claims (email). These come from
  Cognito's userinfo endpoint and do NOT include groups.
* ``x-amzn-oidc-accesstoken``: the Cognito access token, whose ``cognito:groups`` claim
  carries the user's groups.

Only the load balancer can reach the app (security group), so the claims are read
without re-verifying the signature here. Locally, ``X-Demo-User`` and
``X-Demo-Groups`` stand in for them.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Identity:
    email: str
    subject: str = ""
    groups: tuple[str, ...] = field(default_factory=tuple)


def _decode_jwt_payload(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return {}


def identity_from_request(headers: Mapping[str, str], default_user: str) -> Identity:
    claims = _decode_jwt_payload(headers.get("x-amzn-oidc-data", ""))
    access = _decode_jwt_payload(headers.get("x-amzn-oidc-accesstoken", ""))
    subject = headers.get("x-amzn-oidc-identity", "") or str(claims.get("sub", ""))
    email = str(claims.get("email") or headers.get("x-demo-user") or subject or default_user)

    raw_groups = access.get("cognito:groups", claims.get("cognito:groups"))
    if raw_groups is None and headers.get("x-amzn-oidc-accesstoken"):
        raw_groups = []  # signed in, but a member of no group
    if raw_groups is None and "x-demo-groups" in headers:
        raw_groups = [g.strip() for g in headers["x-demo-groups"].split(",") if g.strip()]
    if raw_groups is None and not headers.get("x-amzn-oidc-data"):
        # Local development without any platform headers: pretend to be in every group.
        raw_groups = ["*"]
    groups = tuple(raw_groups) if isinstance(raw_groups, list) else ()
    return Identity(email=email, subject=subject, groups=groups)
