"""service_jwt mint/verify unit tests."""
from __future__ import annotations

import pytest

from hiob_contracts.service_jwt import (
    ServiceJwtError,
    claims_to_dict,
    mint_service_token,
    verify_service_token,
)


SECRET = "unit-test-service-jwt-secret-xyz"


def test_mint_and_verify_roundtrip():
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws-1",
        scopes=["node:karma.reconcile:execute", "node:*:execute"],
        run_id="run-1",
        node_id="karma.reconcile",
        secret=SECRET,
    )
    claims = verify_service_token(
        tok,
        expected_audience="hiob-karma",
        required_scope="node:karma.reconcile:execute",
        workspace_id="ws-1",
        secret=SECRET,
    )
    assert claims.sub == "hiob-star"
    assert claims.workspace_id == "ws-1"
    assert claims.has_scope("node:karma.reconcile:execute")


def test_v3_request_binding_claims_roundtrip():
    tok = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws-v3",
        scopes=["node:ares.scripts.generate:execute"],
        run_id="run-v3",
        node_id="ares.scripts.generate",
        operation_id="op-v3",
        idempotency_key="ares-v3:op-v3",
        request_digest="sha256:" + "1" * 64,
        execution_digest="sha256:" + "2" * 64,
        secret=SECRET,
    )

    claims = verify_service_token(
        tok,
        expected_audience="hiob-ares",
        required_scope="node:ares.scripts.generate:execute",
        workspace_id="ws-v3",
        secret=SECRET,
    )

    assert claims.operation_id == "op-v3"
    assert claims.idempotency_key == "ares-v3:op-v3"
    assert claims.request_digest == "sha256:" + "1" * 64
    assert claims.execution_digest == "sha256:" + "2" * 64
    assert claims_to_dict(claims) == {
        "iss": claims.iss,
        "sub": claims.sub,
        "aud": claims.aud,
        "scope": list(claims.scope),
        "workspace_id": "ws-v3",
        "exp": claims.exp,
        "iat": claims.iat,
        "jti": claims.jti,
        "run_id": "run-v3",
        "node_id": "ares.scripts.generate",
        "operation_id": "op-v3",
        "idempotency_key": "ares-v3:op-v3",
        "request_digest": "sha256:" + "1" * 64,
        "execution_digest": "sha256:" + "2" * 64,
        "kid": "hs256-v1",
    }


def test_legacy_token_without_v3_binding_claims_defaults_to_empty_strings():
    import jwt

    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws-legacy",
        scopes=["node:*:execute"],
        run_id="run-legacy",
        secret=SECRET,
    )
    payload = jwt.decode(token, options={"verify_signature": False})
    for field in (
        "operation_id",
        "idempotency_key",
        "request_digest",
        "execution_digest",
    ):
        payload.pop(field, None)
    legacy_token = jwt.encode(payload, SECRET, algorithm="HS256")

    claims = verify_service_token(
        legacy_token,
        expected_audience="hiob-ares",
        secret=SECRET,
    )

    assert claims.operation_id == ""
    assert claims.idempotency_key == ""
    assert claims.request_digest == ""
    assert claims.execution_digest == ""
    serialized = claims_to_dict(claims)
    assert serialized["operation_id"] == ""
    assert serialized["idempotency_key"] == ""
    assert serialized["request_digest"] == ""
    assert serialized["execution_digest"] == ""


def test_wrong_audience_forbidden():
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws",
        scopes=["node:*:execute"],
        secret=SECRET,
    )
    with pytest.raises(ServiceJwtError) as ei:
        verify_service_token(tok, expected_audience="hiob-janus", secret=SECRET)
    assert ei.value.code in {"PLANET_FORBIDDEN", "PLANET_UNAUTHORIZED"}


def test_missing_scope_forbidden():
    tok = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws",
        scopes=["node:other:execute"],
        secret=SECRET,
    )
    with pytest.raises(ServiceJwtError) as ei:
        verify_service_token(
            tok,
            expected_audience="hiob-ares",
            required_scope="node:ares.script.build_kit:execute",
            secret=SECRET,
        )
    assert ei.value.code == "PLANET_FORBIDDEN"
