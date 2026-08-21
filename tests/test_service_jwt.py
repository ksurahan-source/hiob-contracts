"""service_jwt mint/verify unit tests."""

from __future__ import annotations

import pytest
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hiob_contracts.service_jwt import (
    ServiceJwtError,
    claims_to_dict,
    mint_service_token,
    verify_service_token,
)
import hiob_contracts.service_jwt as service_jwt


SECRET = "unit-test-service-jwt-secret-xyz"


@pytest.fixture(scope="module")
def ed25519_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_pem, public_pem


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
    assert jwt.get_unverified_header(tok) == {
        "alg": "HS256",
        "kid": "hs256-v1",
        "typ": "JWT",
    }


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
        dispatch_capability="one-time-capability",
        jti="dispatch-once-v3",
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
    assert claims.jti == "dispatch-once-v3"
    assert claims.dispatch_capability == "one-time-capability"
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
        "dispatch_capability": "one-time-capability",
        "kid": "hs256-v1",
    }


def test_legacy_token_without_v3_binding_claims_defaults_to_empty_strings():
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
        "dispatch_capability",
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
    assert claims.dispatch_capability == ""
    serialized = claims_to_dict(claims)
    assert serialized["operation_id"] == ""
    assert serialized["idempotency_key"] == ""
    assert serialized["request_digest"] == ""
    assert serialized["execution_digest"] == ""
    assert serialized["dispatch_capability"] == ""


def test_eddsa_roundtrip_with_verifier_only_public_key(ed25519_keypair):
    private_key, public_key = ed25519_keypair
    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws-eddsa",
        scopes=["node:ares.scripts.generate:execute"],
        run_id="run-eddsa",
        node_id="ares.scripts.generate",
        private_key=private_key,
        secret="ignored-hs-secret",
    )

    assert jwt.get_unverified_header(token) == {
        "alg": "EdDSA",
        "kid": "eddsa-v1",
        "typ": "JWT",
    }
    claims = verify_service_token(
        token,
        expected_audience="hiob-ares",
        required_scope="node:ares.scripts.generate:execute",
        workspace_id="ws-eddsa",
        public_key=public_key,
        secret="ignored-hs-secret",
    )

    assert claims.run_id == "run-eddsa"
    assert claims.kid == "eddsa-v1"


def test_public_key_verifier_rejects_hs256_algorithm_confusion(ed25519_keypair):
    _, public_key = ed25519_keypair
    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws",
        scopes=["node:*:execute"],
        secret=SECRET,
    )

    with pytest.raises(ServiceJwtError, match="algorithm mismatch") as exc_info:
        verify_service_token(
            token,
            expected_audience="hiob-ares",
            public_key=public_key,
        )
    assert exc_info.value.code == "PLANET_UNAUTHORIZED"


def test_hs256_verifier_rejects_eddsa_algorithm_confusion(ed25519_keypair):
    private_key, _ = ed25519_keypair
    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws",
        scopes=["node:*:execute"],
        private_key=private_key,
    )

    with pytest.raises(ServiceJwtError, match="algorithm mismatch") as exc_info:
        verify_service_token(
            token,
            expected_audience="hiob-ares",
            secret=SECRET,
        )
    assert exc_info.value.code == "PLANET_UNAUTHORIZED"


def test_eddsa_verifier_rejects_wrong_header_kid(ed25519_keypair):
    private_key, public_key = ed25519_keypair
    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws",
        scopes=["node:*:execute"],
        private_key=private_key,
    )
    payload = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": "attacker-key"},
    )

    with pytest.raises(ServiceJwtError, match="key id mismatch"):
        verify_service_token(
            forged,
            expected_audience="hiob-ares",
            public_key=public_key,
        )


def test_eddsa_verifier_rejects_payload_kid_mismatch(ed25519_keypair):
    private_key, public_key = ed25519_keypair
    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws",
        scopes=["node:*:execute"],
        private_key=private_key,
    )
    payload = jwt.decode(token, options={"verify_signature": False})
    payload["kid"] = "hs256-v1"
    forged = jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": "eddsa-v1"},
    )

    with pytest.raises(ServiceJwtError, match="key id mismatch"):
        verify_service_token(
            forged,
            expected_audience="hiob-ares",
            public_key=public_key,
        )


def test_hs256_verifier_rejects_wrong_header_kid():
    token = mint_service_token(
        audience="hiob-ares",
        workspace_id="ws",
        scopes=["node:*:execute"],
        secret=SECRET,
    )
    payload = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(
        payload,
        SECRET,
        algorithm="HS256",
        headers={"kid": "eddsa-v1"},
    )

    with pytest.raises(ServiceJwtError, match="key id mismatch"):
        verify_service_token(
            forged,
            expected_audience="hiob-ares",
            secret=SECRET,
        )


def test_eddsa_mode_requires_nonempty_keys():
    with pytest.raises(ServiceJwtError, match="private key not configured"):
        mint_service_token(
            audience="hiob-ares",
            workspace_id="ws",
            scopes=["node:*:execute"],
            private_key="",
            secret=SECRET,
        )
    with pytest.raises(ServiceJwtError, match="public key not configured"):
        verify_service_token(
            "header.payload.signature",
            expected_audience="hiob-ares",
            public_key="",
            secret=SECRET,
        )


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


def test_environment_secret_lookup_and_empty_secret_fail_closed(monkeypatch):
    for name in (
        "HIOB_SERVICE_JWT_SECRET",
        "HIOB_PLANET_NODE_SECRET",
        "MODAL_DISPATCH_SECRET",
        "HIOB_WORKER_DISPATCH_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HIOB_PLANET_NODE_SECRET", SECRET)
    assert service_jwt.signing_secret() == SECRET
    monkeypatch.delenv("HIOB_PLANET_NODE_SECRET")

    with pytest.raises(ServiceJwtError, match="secret not configured"):
        mint_service_token(
            audience="hiob-ares",
            workspace_id="ws",
            scopes=["node:*:execute"],
            secret="",
        )
    with pytest.raises(ServiceJwtError, match="secret not configured"):
        verify_service_token(
            "header.payload.signature",
            expected_audience="hiob-ares",
            secret="",
        )


def test_signing_error_is_wrapped_without_key_material() -> None:
    class FailingJwt:
        PyJWTError = jwt.PyJWTError

        @staticmethod
        def encode(*_args, **_kwargs):
            raise jwt.PyJWTError("simulated")

    with pytest.raises(ServiceJwtError, match="invalid service JWT HS256 signing key"):
        service_jwt._encode_service_payload(
            FailingJwt,
            {"sub": "service"},
            signing_key="not-reported",
            algorithm="HS256",
            kid="hs256-v1",
        )


def test_malformed_expired_issuer_signature_and_workspace_failures() -> None:
    with pytest.raises(ServiceJwtError, match="missing or malformed"):
        verify_service_token("not-a-token", expected_audience="hiob-ares", secret=SECRET)
    with pytest.raises(ServiceJwtError, match="invalid service JWT header"):
        verify_service_token("a.b.c", expected_audience="hiob-ares", secret=SECRET)

    now = int(service_jwt.time.time())
    base = {
        "iss": "hiob-control-plane",
        "sub": "hiob-star",
        "aud": "hiob-ares",
        "scope": "node:*:execute node:ares:execute",
        "workspace_id": "ws-1",
        "iat": now - 120,
        "exp": now - 60,
        "jti": "expired",
        "kid": "hs256-v1",
    }
    expired = jwt.encode(
        base,
        SECRET,
        algorithm="HS256",
        headers={"kid": "hs256-v1"},
    )
    with pytest.raises(ServiceJwtError, match="expired"):
        verify_service_token(expired, expected_audience="hiob-ares", secret=SECRET, leeway_s=0)

    wrong_issuer = jwt.encode(
        {**base, "iss": "other", "exp": now + 60},
        SECRET,
        algorithm="HS256",
        headers={"kid": "hs256-v1"},
    )
    with pytest.raises(ServiceJwtError, match="issuer mismatch"):
        verify_service_token(wrong_issuer, expected_audience="hiob-ares", secret=SECRET)

    valid = jwt.encode(
        {**base, "exp": now + 60},
        SECRET,
        algorithm="HS256",
        headers={"kid": "hs256-v1"},
    )
    claims = verify_service_token(valid, expected_audience="hiob-ares", secret=SECRET)
    assert claims.scope == ("node:*:execute", "node:ares:execute")
    with pytest.raises(ServiceJwtError, match="workspace_id claim mismatch"):
        verify_service_token(
            valid,
            expected_audience="hiob-ares",
            workspace_id="ws-2",
            secret=SECRET,
        )
    with pytest.raises(ServiceJwtError, match="invalid service JWT"):
        verify_service_token(
            valid,
            expected_audience="hiob-ares",
            secret="wrong-unit-test-service-jwt-secret-xyz",
        )
