"""Service JWT claims for planet node-mesh (PRD MESH-PERFECT Phase 0/PR1).

Short-lived HS256 tokens issued by Star/control plane. Planets validate before
body parsing / handler execution (fail closed).

Claims (required):
  iss, sub, aud, scope, workspace_id, exp, iat, jti
Optional:
  run_id, kid, node_id
Operation-bound node dispatch (both required together):
  idempotency_key, request_digest

Signing key: dedicated HIOB_SERVICE_JWT_SECRET only.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


class ServiceJwtError(ValueError):
    def __init__(self, message: str, *, code: str = "PLANET_UNAUTHORIZED") -> None:
        super().__init__(message)
        self.code = code


def signing_secret() -> str:
    return (os.environ.get("HIOB_SERVICE_JWT_SECRET") or "").strip()


def canonical_request_digest(payload: Mapping[str, Any]) -> str:
    """Digest the exact request body using the Modal verifier's JSON rules."""
    raw = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _validate_operation_claims(
    idempotency_key: object,
    request_digest: object,
    *,
    code: str,
) -> tuple[str, str]:
    if (
        not isinstance(idempotency_key, str)
        or not idempotency_key
        or idempotency_key != idempotency_key.strip()
    ):
        raise ServiceJwtError(
            "canonical idempotency_key is required",
            code=code,
        )
    if (
        not isinstance(request_digest, str)
        or len(request_digest) != 71
        or not request_digest.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in request_digest[7:])
    ):
        raise ServiceJwtError(
            "canonical request_digest is required",
            code=code,
        )
    return idempotency_key, request_digest


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
    idempotency_key: str = ""
    request_digest: str = ""

    def has_scope(self, required: str) -> bool:
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
    idempotency_key: Optional[str] = None,
    request_digest: Optional[str] = None,
    ttl_s: int = 300,
    secret: Optional[str] = None,
) -> str:
    """Mint HS256 service JWT; operation claims remain optional as a pair."""
    import jwt  # PyJWT

    sec = (secret if secret is not None else signing_secret()).strip()
    if not sec:
        raise ServiceJwtError(
            "service JWT secret not configured", code="PLANET_UNAUTHORIZED"
        )
    has_idempotency_key = idempotency_key is not None
    has_request_digest = request_digest is not None
    if has_idempotency_key != has_request_digest:
        raise ServiceJwtError(
            "idempotency_key and request_digest must be provided together",
            code="PLANET_UNAUTHORIZED",
        )
    operation_claims: dict[str, str] = {}
    if has_idempotency_key:
        exact_key, exact_digest = _validate_operation_claims(
            idempotency_key,
            request_digest,
            code="PLANET_UNAUTHORIZED",
        )
        operation_claims = {
            "idempotency_key": exact_key,
            "request_digest": exact_digest,
        }
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
    payload.update(operation_claims)
    return jwt.encode(payload, sec, algorithm="HS256")


def verify_service_token(
    token: str,
    *,
    expected_audience: str,
    required_scope: Optional[str] = None,
    workspace_id: Optional[str] = None,
    expected_run_id: Optional[str] = None,
    expected_node_id: Optional[str] = None,
    expected_idempotency_key: Optional[str] = None,
    expected_request_digest: Optional[str] = None,
    secret: Optional[str] = None,
    leeway_s: int = 30,
) -> ServiceClaims:
    """Verify JWT. Raises ServiceJwtError with PLANET_UNAUTHORIZED or PLANET_FORBIDDEN."""
    import jwt  # PyJWT

    sec = (secret if secret is not None else signing_secret()).strip()
    if not sec:
        raise ServiceJwtError(
            "service JWT secret not configured", code="PLANET_UNAUTHORIZED"
        )
    if not token or token.count(".") != 2:
        raise ServiceJwtError(
            "missing or malformed service JWT", code="PLANET_UNAUTHORIZED"
        )
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
        raise ServiceJwtError(
            "service JWT expired", code="PLANET_UNAUTHORIZED"
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise ServiceJwtError(
            "service JWT audience mismatch", code="PLANET_FORBIDDEN"
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise ServiceJwtError(
            "service JWT issuer mismatch", code="PLANET_UNAUTHORIZED"
        ) from exc
    except jwt.PyJWTError as exc:
        raise ServiceJwtError(
            f"invalid service JWT: {exc}", code="PLANET_UNAUTHORIZED"
        ) from exc

    scope_raw = data.get("scope") or []
    if isinstance(scope_raw, str):
        scopes = tuple(s.strip() for s in scope_raw.split() if s.strip())
    else:
        scopes = tuple(str(s) for s in scope_raw)

    has_idempotency_key = "idempotency_key" in data
    has_request_digest = "request_digest" in data
    if has_idempotency_key != has_request_digest:
        raise ServiceJwtError(
            "service JWT operation claims must be provided together",
            code="PLANET_FORBIDDEN",
        )
    signed_idempotency_key = ""
    signed_request_digest = ""
    if has_idempotency_key:
        signed_idempotency_key, signed_request_digest = _validate_operation_claims(
            data.get("idempotency_key"),
            data.get("request_digest"),
            code="PLANET_FORBIDDEN",
        )

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
        idempotency_key=signed_idempotency_key,
        request_digest=signed_request_digest,
    )

    if required_scope:
        if {"*", "node:*:execute"}.intersection(claims.scope):
            raise ServiceJwtError(
                "wildcard node scope is forbidden",
                code="PLANET_FORBIDDEN",
            )
        if not claims.has_scope(required_scope):
            raise ServiceJwtError(
                f"missing scope {required_scope}",
                code="PLANET_FORBIDDEN",
            )
    if workspace_id is not None and claims.workspace_id != str(workspace_id):
        raise ServiceJwtError(
            "workspace_id claim mismatch",
            code="PLANET_FORBIDDEN",
        )
    if expected_run_id is not None and claims.run_id != str(expected_run_id):
        raise ServiceJwtError(
            "run_id claim mismatch",
            code="PLANET_FORBIDDEN",
        )
    if expected_node_id is not None and claims.node_id != str(expected_node_id):
        raise ServiceJwtError(
            "node_id claim mismatch",
            code="PLANET_FORBIDDEN",
        )
    expects_idempotency_key = expected_idempotency_key is not None
    expects_request_digest = expected_request_digest is not None
    if expects_idempotency_key != expects_request_digest:
        raise ServiceJwtError(
            "expected operation claims must be provided together",
            code="PLANET_UNAUTHORIZED",
        )
    if expects_idempotency_key:
        exact_key, exact_digest = _validate_operation_claims(
            expected_idempotency_key,
            expected_request_digest,
            code="PLANET_FORBIDDEN",
        )
        if claims.idempotency_key != exact_key:
            raise ServiceJwtError(
                "idempotency_key claim mismatch",
                code="PLANET_FORBIDDEN",
            )
        if claims.request_digest != exact_digest:
            raise ServiceJwtError(
                "request_digest claim mismatch",
                code="PLANET_FORBIDDEN",
            )
        if not claims.jti:
            raise ServiceJwtError(
                "operation-bound service JWT requires jti",
                code="PLANET_UNAUTHORIZED",
            )
    return claims


def claims_to_dict(c: ServiceClaims) -> dict[str, Any]:
    result = {
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
    if c.idempotency_key or c.request_digest:
        result.update(
            {
                "idempotency_key": c.idempotency_key,
                "request_digest": c.request_digest,
            }
        )
    return result
