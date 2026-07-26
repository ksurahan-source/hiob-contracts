"""Service JWT claims for planet node-mesh (PRD MESH-PERFECT Phase 0/PR1).

Short-lived HS256 or EdDSA tokens issued by Star/control plane. Planets validate
before body parsing / handler execution (fail closed). HS256 remains available
for compatibility; verifier-only services can receive only an Ed25519 public
key and never need signing material.

Claims (required):
  iss, sub, aud, scope, workspace_id, exp, iat, jti
Optional:
  run_id, kid, node_id, operation_id, idempotency_key, request_digest,
  execution_digest, dispatch_capability

Lifetime: HIOB_SERVICE_JWT_SECRET or MODAL_DISPATCH_SECRET or HIOB_WORKER_DISPATCH_SECRET
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Sequence


_HS256_ALGORITHM = "HS256"
_HS256_KID = "hs256-v1"
_EDDSA_ALGORITHM = "EdDSA"
_EDDSA_KID = "eddsa-v1"


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
    operation_id: str = ""
    idempotency_key: str = ""
    request_digest: str = ""
    execution_digest: str = ""
    dispatch_capability: str = ""
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
    operation_id: str = "",
    idempotency_key: str = "",
    request_digest: str = "",
    execution_digest: str = "",
    dispatch_capability: str = "",
    jti: str = "",
    ttl_s: int = 300,
    secret: Optional[str] = None,
    private_key: Optional[str] = None,
) -> str:
    """Mint a service JWT. ``private_key`` selects EdDSA; otherwise HS256."""
    import jwt  # PyJWT

    if private_key is not None:
        signing_key = private_key.strip()
        algorithm = _EDDSA_ALGORITHM
        kid = _EDDSA_KID
        if not signing_key:
            raise ServiceJwtError(
                "service JWT private key not configured",
                code="PLANET_UNAUTHORIZED",
            )
    else:
        signing_key = (secret if secret is not None else signing_secret()).strip()
        algorithm = _HS256_ALGORITHM
        kid = _HS256_KID
        if not signing_key:
            raise ServiceJwtError(
                "service JWT secret not configured",
                code="PLANET_UNAUTHORIZED",
            )
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
        "operation_id": str(operation_id or ""),
        "idempotency_key": str(idempotency_key or ""),
        "request_digest": str(request_digest or ""),
        "execution_digest": str(execution_digest or ""),
        "dispatch_capability": str(dispatch_capability or ""),
        "jti": str(jti or uuid.uuid4()),
        "iat": now,
        "exp": now + ttl,
        "kid": kid,
    }
    try:
        return jwt.encode(
            payload,
            signing_key,
            algorithm=algorithm,
            headers={"kid": kid, "typ": "JWT"},
        )
    except jwt.PyJWTError as exc:
        raise ServiceJwtError(
            f"invalid service JWT {algorithm} signing key",
            code="PLANET_UNAUTHORIZED",
        ) from exc


def verify_service_token(
    token: str,
    *,
    expected_audience: str,
    required_scope: Optional[str] = None,
    workspace_id: Optional[str] = None,
    secret: Optional[str] = None,
    public_key: Optional[str] = None,
    leeway_s: int = 30,
) -> ServiceClaims:
    """Verify JWT using EdDSA when ``public_key`` is supplied, else HS256."""
    import jwt  # PyJWT

    if not token or token.count(".") != 2:
        raise ServiceJwtError(
            "missing or malformed service JWT", code="PLANET_UNAUTHORIZED"
        )
    if public_key is not None:
        verification_key = public_key.strip()
        algorithm = _EDDSA_ALGORITHM
        expected_kid = _EDDSA_KID
        if not verification_key:
            raise ServiceJwtError(
                "service JWT public key not configured",
                code="PLANET_UNAUTHORIZED",
            )
    else:
        verification_key = (secret if secret is not None else signing_secret()).strip()
        algorithm = _HS256_ALGORITHM
        expected_kid = _HS256_KID
        if not verification_key:
            raise ServiceJwtError(
                "service JWT secret not configured",
                code="PLANET_UNAUTHORIZED",
            )

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise ServiceJwtError(
            "invalid service JWT header",
            code="PLANET_UNAUTHORIZED",
        ) from exc
    if header.get("alg") != algorithm:
        raise ServiceJwtError(
            "service JWT algorithm mismatch",
            code="PLANET_UNAUTHORIZED",
        )
    header_kid = str(header.get("kid") or "")
    if algorithm == _EDDSA_ALGORITHM:
        if header_kid != expected_kid:
            raise ServiceJwtError(
                "service JWT key id mismatch",
                code="PLANET_UNAUTHORIZED",
            )
    elif header_kid and header_kid != expected_kid:
        raise ServiceJwtError(
            "service JWT key id mismatch",
            code="PLANET_UNAUTHORIZED",
        )

    try:
        data = jwt.decode(
            token,
            verification_key,
            algorithms=[algorithm],
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
            "invalid service JWT", code="PLANET_UNAUTHORIZED"
        ) from exc

    payload_kid = str(data.get("kid") or "")
    if algorithm == _EDDSA_ALGORITHM:
        if payload_kid != expected_kid:
            raise ServiceJwtError(
                "service JWT key id mismatch",
                code="PLANET_UNAUTHORIZED",
            )
    elif payload_kid and payload_kid != expected_kid:
        raise ServiceJwtError(
            "service JWT key id mismatch",
            code="PLANET_UNAUTHORIZED",
        )

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
        operation_id=str(data.get("operation_id") or ""),
        idempotency_key=str(data.get("idempotency_key") or ""),
        request_digest=str(data.get("request_digest") or ""),
        execution_digest=str(data.get("execution_digest") or ""),
        dispatch_capability=str(data.get("dispatch_capability") or ""),
        kid=payload_kid or expected_kid,
    )

    if required_scope and not claims.has_scope(required_scope):
        raise ServiceJwtError(
            f"missing scope {required_scope}",
            code="PLANET_FORBIDDEN",
        )
    if (
        workspace_id is not None
        and claims.workspace_id
        and claims.workspace_id != str(workspace_id)
    ):
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
        "operation_id": c.operation_id,
        "idempotency_key": c.idempotency_key,
        "request_digest": c.request_digest,
        "execution_digest": c.execution_digest,
        "dispatch_capability": c.dispatch_capability,
        "kid": c.kid,
    }
