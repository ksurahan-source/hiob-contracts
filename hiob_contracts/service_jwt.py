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
_KEY_ID_MISMATCH = "service JWT key id mismatch"


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


def _signing_context(
    *,
    secret: Optional[str],
    private_key: Optional[str],
) -> tuple[str, str, str]:
    if private_key is not None:
        key = private_key.strip()
        if not key:
            raise ServiceJwtError(
                "service JWT private key not configured",
                code="PLANET_UNAUTHORIZED",
            )
        return key, _EDDSA_ALGORITHM, _EDDSA_KID
    key = (secret if secret is not None else signing_secret()).strip()
    if not key:
        raise ServiceJwtError(
            "service JWT secret not configured",
            code="PLANET_UNAUTHORIZED",
        )
    return key, _HS256_ALGORITHM, _HS256_KID


def _encode_service_payload(
    jwt: Any,
    payload: dict[str, Any],
    *,
    signing_key: str,
    algorithm: str,
    kid: str,
) -> str:
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

    signing_key, algorithm, kid = _signing_context(
        secret=secret,
        private_key=private_key,
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
    return _encode_service_payload(
        jwt,
        payload,
        signing_key=signing_key,
        algorithm=algorithm,
        kid=kid,
    )


def _verification_context(
    *,
    secret: Optional[str],
    public_key: Optional[str],
) -> tuple[str, str, str]:
    if public_key is not None:
        key = public_key.strip()
        if not key:
            raise ServiceJwtError(
                "service JWT public key not configured",
                code="PLANET_UNAUTHORIZED",
            )
        return key, _EDDSA_ALGORITHM, _EDDSA_KID
    key = (secret if secret is not None else signing_secret()).strip()
    if not key:
        raise ServiceJwtError(
            "service JWT secret not configured",
            code="PLANET_UNAUTHORIZED",
        )
    return key, _HS256_ALGORITHM, _HS256_KID


def _assert_expected_kid(kid: str, *, algorithm: str, expected_kid: str) -> None:
    required = algorithm == _EDDSA_ALGORITHM
    if (required and kid != expected_kid) or (not required and kid and kid != expected_kid):
        raise ServiceJwtError(_KEY_ID_MISMATCH, code="PLANET_UNAUTHORIZED")


def _verified_header(jwt: Any, token: str, *, algorithm: str, expected_kid: str) -> None:
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
    _assert_expected_kid(
        str(header.get("kid") or ""),
        algorithm=algorithm,
        expected_kid=expected_kid,
    )


def _decode_service_payload(
    jwt: Any,
    token: str,
    *,
    verification_key: str,
    algorithm: str,
    expected_audience: str,
    leeway_s: int,
) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            verification_key,
            algorithms=[algorithm],
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
        raise ServiceJwtError("invalid service JWT", code="PLANET_UNAUTHORIZED") from exc


def _service_scopes(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(scope.strip() for scope in value.split() if scope.strip())
    return tuple(str(scope) for scope in (value or []))


def _text_claim(data: dict[str, Any], name: str, default: str = "") -> str:
    return str(data.get(name) or default)


def _integer_claim(data: dict[str, Any], name: str) -> int:
    return int(data.get(name) or 0)


def _service_claims(
    data: dict[str, Any],
    *,
    expected_audience: str,
    expected_kid: str,
) -> ServiceClaims:
    payload_kid = _text_claim(data, "kid")
    return ServiceClaims(
        iss=_text_claim(data, "iss"),
        sub=_text_claim(data, "sub"),
        aud=_text_claim(data, "aud", expected_audience),
        scope=_service_scopes(data.get("scope")),
        workspace_id=_text_claim(data, "workspace_id"),
        exp=_integer_claim(data, "exp"),
        iat=_integer_claim(data, "iat"),
        jti=_text_claim(data, "jti"),
        run_id=_text_claim(data, "run_id"),
        node_id=_text_claim(data, "node_id"),
        operation_id=_text_claim(data, "operation_id"),
        idempotency_key=_text_claim(data, "idempotency_key"),
        request_digest=_text_claim(data, "request_digest"),
        execution_digest=_text_claim(data, "execution_digest"),
        dispatch_capability=_text_claim(data, "dispatch_capability"),
        kid=payload_kid or expected_kid,
    )


def _assert_service_claim_requirements(
    claims: ServiceClaims,
    *,
    required_scope: Optional[str],
    workspace_id: Optional[str],
) -> None:
    if required_scope and not claims.has_scope(required_scope):
        raise ServiceJwtError(f"missing scope {required_scope}", code="PLANET_FORBIDDEN")
    if workspace_id is not None and claims.workspace_id and claims.workspace_id != str(workspace_id):
        raise ServiceJwtError("workspace_id claim mismatch", code="PLANET_FORBIDDEN")


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
    verification_key, algorithm, expected_kid = _verification_context(
        secret=secret,
        public_key=public_key,
    )
    _verified_header(jwt, token, algorithm=algorithm, expected_kid=expected_kid)
    data = _decode_service_payload(
        jwt,
        token,
        verification_key=verification_key,
        algorithm=algorithm,
        expected_audience=expected_audience,
        leeway_s=leeway_s,
    )
    payload_kid = str(data.get("kid") or "")
    _assert_expected_kid(payload_kid, algorithm=algorithm, expected_kid=expected_kid)
    claims = _service_claims(
        data,
        expected_audience=expected_audience,
        expected_kid=expected_kid,
    )
    _assert_service_claim_requirements(
        claims,
        required_scope=required_scope,
        workspace_id=workspace_id,
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
