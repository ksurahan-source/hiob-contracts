"""Service JWT claims for planet node-mesh (PRD MESH-PERFECT Phase 0/PR1).

Short-lived HS256 tokens issued by Star/control plane. Planets validate before
body parsing / handler execution (fail closed).

Claims (required):
  iss, sub, aud, scope, workspace_id, exp, iat, jti
Optional:
  run_id, kid, node_id

Lifetime: HIOB_SERVICE_JWT_SECRET or MODAL_DISPATCH_SECRET or HIOB_WORKER_DISPATCH_SECRET
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Sequence


class ServiceJwtError(ValueError):
    def __init__(self, message: str, *, code: str = "PLANET_UNAUTHORIZED") -> None:
        super().__init__(message)
        self.code = code


def signing_secret() -> str:
    return (
        os.environ.get("HIOB_SERVICE_JWT_SECRET")
        or os.environ.get("HIOB_PLANET_NODE_SECRET")
        or os.environ.get("MODAL_DISPATCH_SECRET")
        or os.environ.get("HIOB_WORKER_DISPATCH_SECRET")
        or ""
    ).strip()


@dataclass(frozen=True)
class ServiceClaims:
    iss: str
    sub: str
    aud: str
    scope: tuple[str, ...]
    workspace_id: str
    exp: int
    iat: int
    jti: str
    run_id: str = ""
    node_id: str = ""
    kid: str = "hs256-v1"

    def has_scope(self, required: str) -> bool:
        if "*" in self.scope or "node:*:execute" in self.scope:
            return True
        return required in self.scope


def mint_service_token(
    *,
    audience: str,
    workspace_id: str,
    scopes: Sequence[str],
    subject: str = "hiob-star",
    issuer: str = "hiob-control-plane",
    run_id: str = "",
    node_id: str = "",
    ttl_s: int = 300,
    secret: Optional[str] = None,
) -> str:
    """Mint HS256 service JWT. ttl_s max 300 (5m) per PRD."""
    import jwt  # PyJWT

    sec = (secret if secret is not None else signing_secret()).strip()
    if not sec:
        raise ServiceJwtError("service JWT secret not configured", code="PLANET_UNAUTHORIZED")
    ttl = max(30, min(int(ttl_s), 300))
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "scope": list(scopes),
        "workspace_id": str(workspace_id or "default"),
        "run_id": str(run_id or ""),
        "node_id": str(node_id or ""),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl,
        "kid": "hs256-v1",
    }
    return jwt.encode(payload, sec, algorithm="HS256")


def verify_service_token(
    token: str,
    *,
    expected_audience: str,
    required_scope: Optional[str] = None,
    workspace_id: Optional[str] = None,
    secret: Optional[str] = None,
    leeway_s: int = 30,
) -> ServiceClaims:
    """Verify JWT. Raises ServiceJwtError with PLANET_UNAUTHORIZED or PLANET_FORBIDDEN."""
    import jwt  # PyJWT

    sec = (secret if secret is not None else signing_secret()).strip()
    if not sec:
        raise ServiceJwtError("service JWT secret not configured", code="PLANET_UNAUTHORIZED")
    if not token or token.count(".") != 2:
        raise ServiceJwtError("missing or malformed service JWT", code="PLANET_UNAUTHORIZED")
    try:
        data = jwt.decode(
            token,
            sec,
            algorithms=["HS256"],
            audience=expected_audience,
            issuer="hiob-control-plane",
            leeway=leeway_s,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ServiceJwtError("service JWT expired", code="PLANET_UNAUTHORIZED") from exc
    except jwt.InvalidAudienceError as exc:
        raise ServiceJwtError("service JWT audience mismatch", code="PLANET_FORBIDDEN") from exc
    except jwt.InvalidIssuerError as exc:
        raise ServiceJwtError("service JWT issuer mismatch", code="PLANET_UNAUTHORIZED") from exc
    except jwt.PyJWTError as exc:
        raise ServiceJwtError(f"invalid service JWT: {exc}", code="PLANET_UNAUTHORIZED") from exc

    scope_raw = data.get("scope") or []
    if isinstance(scope_raw, str):
        scopes = tuple(s.strip() for s in scope_raw.split() if s.strip())
    else:
        scopes = tuple(str(s) for s in scope_raw)

    claims = ServiceClaims(
        iss=str(data.get("iss") or ""),
        sub=str(data.get("sub") or ""),
        aud=str(data.get("aud") or expected_audience),
        scope=scopes,
        workspace_id=str(data.get("workspace_id") or ""),
        exp=int(data.get("exp") or 0),
        iat=int(data.get("iat") or 0),
        jti=str(data.get("jti") or ""),
        run_id=str(data.get("run_id") or ""),
        node_id=str(data.get("node_id") or ""),
        kid=str(data.get("kid") or "hs256-v1"),
    )

    if required_scope and not claims.has_scope(required_scope):
        raise ServiceJwtError(
            f"missing scope {required_scope}",
            code="PLANET_FORBIDDEN",
        )
    if workspace_id is not None and claims.workspace_id and claims.workspace_id != str(workspace_id):
        raise ServiceJwtError(
            "workspace_id claim mismatch",
            code="PLANET_FORBIDDEN",
        )
    return claims


def claims_to_dict(c: ServiceClaims) -> dict[str, Any]:
    return {
        "iss": c.iss,
        "sub": c.sub,
        "aud": c.aud,
        "scope": list(c.scope),
        "workspace_id": c.workspace_id,
        "exp": c.exp,
        "iat": c.iat,
        "jti": c.jti,
        "run_id": c.run_id,
        "node_id": c.node_id,
        "kid": c.kid,
    }
