"""service_jwt mint/verify unit tests."""
from __future__ import annotations

import os
import time

import pytest

from hiob_contracts.service_jwt import (
    ServiceJwtError,
    mint_service_token,
    verify_service_token,
)


SECRET = "unit-test-service-jwt-secret-xyz"


def test_mint_and_verify_roundtrip():
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws-1",
        scopes=["node:karma.reconcile:execute"],
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


@pytest.mark.parametrize(
    "scopes",
    [
        ["*"],
        ["node:*:execute"],
        ["node:karma.reconcile:execute", "*"],
        ["node:karma.reconcile:execute", "node:*:execute"],
    ],
)
def test_wildcard_scope_never_authorizes_formal_node_execution(
    scopes: list[str],
):
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws-1",
        scopes=scopes,
        run_id="run-1",
        node_id="karma.reconcile",
        secret=SECRET,
    )

    with pytest.raises(
        ServiceJwtError,
        match="wildcard node scope is forbidden",
    ) as exc_info:
        verify_service_token(
            tok,
            expected_audience="hiob-karma",
            required_scope="node:karma.reconcile:execute",
            workspace_id="ws-1",
            expected_run_id="run-1",
            expected_node_id="karma.reconcile",
            secret=SECRET,
        )

    assert exc_info.value.code == "PLANET_FORBIDDEN"


@pytest.mark.parametrize(
    "scope_claim",
    [
        "*",
        "node:*:execute",
        "node:karma.reconcile:execute node:*:execute",
    ],
)
def test_space_delimited_wildcard_scope_is_forbidden(scope_claim: str):
    import jwt

    now = int(time.time())
    tok = jwt.encode(
        {
            "iss": "hiob-control-plane",
            "sub": "hiob-star",
            "aud": "hiob-karma",
            "scope": scope_claim,
            "workspace_id": "ws-1",
            "run_id": "run-1",
            "node_id": "karma.reconcile",
            "jti": "wildcard-test",
            "iat": now,
            "exp": now + 300,
        },
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(
        ServiceJwtError,
        match="wildcard node scope is forbidden",
    ):
        verify_service_token(
            tok,
            expected_audience="hiob-karma",
            required_scope="node:karma.reconcile:execute",
            workspace_id="ws-1",
            expected_run_id="run-1",
            expected_node_id="karma.reconcile",
            secret=SECRET,
        )


def test_default_signing_secret_ignores_legacy_dispatch_secrets(monkeypatch):
    monkeypatch.delenv("HIOB_SERVICE_JWT_SECRET", raising=False)
    monkeypatch.setenv("HIOB_PLANET_NODE_SECRET", "legacy-node-secret")
    monkeypatch.setenv("MODAL_DISPATCH_SECRET", "legacy-modal-secret")
    monkeypatch.setenv("HIOB_WORKER_DISPATCH_SECRET", "legacy-worker-secret")

    with pytest.raises(
        ServiceJwtError,
        match="service JWT secret not configured",
    ):
        mint_service_token(
            audience="hiob-karma",
            workspace_id="ws-1",
            scopes=["node:karma.reconcile:execute"],
        )

    assert os.environ["MODAL_DISPATCH_SECRET"] == "legacy-modal-secret"


def test_exact_run_and_node_claims_match_when_expected():
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws-1",
        scopes=["node:karma.edge.refine:execute"],
        run_id="run-1",
        node_id="karma.edge.refine",
        secret=SECRET,
    )

    claims = verify_service_token(
        tok,
        expected_audience="hiob-karma",
        expected_run_id="run-1",
        expected_node_id="karma.edge.refine",
        secret=SECRET,
    )

    assert claims.run_id == "run-1"
    assert claims.node_id == "karma.edge.refine"


@pytest.mark.parametrize(
    ("expected_run_id", "expected_node_id", "message"),
    [
        ("run-other", "karma.edge.refine", "run_id claim mismatch"),
        ("run-1", "karma.other", "node_id claim mismatch"),
    ],
)
def test_exact_run_or_node_claim_mismatch_is_forbidden(
    expected_run_id: str,
    expected_node_id: str,
    message: str,
):
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws-1",
        scopes=["node:karma.edge.refine:execute"],
        run_id="run-1",
        node_id="karma.edge.refine",
        secret=SECRET,
    )

    with pytest.raises(ServiceJwtError, match=message) as exc_info:
        verify_service_token(
            tok,
            expected_audience="hiob-karma",
            expected_run_id=expected_run_id,
            expected_node_id=expected_node_id,
            secret=SECRET,
        )

    assert exc_info.value.code == "PLANET_FORBIDDEN"


@pytest.mark.parametrize(
    ("expected_claim", "message"),
    [
        ({"expected_run_id": "run-1"}, "run_id claim mismatch"),
        ({"expected_node_id": "karma.edge.refine"}, "node_id claim mismatch"),
    ],
)
def test_missing_exact_claim_is_forbidden(
    expected_claim: dict[str, str],
    message: str,
):
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="ws-1",
        scopes=["node:karma.edge.refine:execute"],
        secret=SECRET,
    )

    with pytest.raises(ServiceJwtError, match=message) as exc_info:
        verify_service_token(
            tok,
            expected_audience="hiob-karma",
            secret=SECRET,
            **expected_claim,
        )

    assert exc_info.value.code == "PLANET_FORBIDDEN"


def test_missing_workspace_claim_is_forbidden_when_workspace_is_expected():
    tok = mint_service_token(
        audience="hiob-karma",
        workspace_id="",
        scopes=["node:karma.edge.refine:execute"],
        run_id="run-1",
        node_id="karma.edge.refine",
        secret=SECRET,
    )

    with pytest.raises(
        ServiceJwtError,
        match="workspace_id claim mismatch",
    ) as exc_info:
        verify_service_token(
            tok,
            expected_audience="hiob-karma",
            required_scope="node:karma.edge.refine:execute",
            workspace_id="ws-1",
            expected_run_id="run-1",
            expected_node_id="karma.edge.refine",
            secret=SECRET,
        )

    assert exc_info.value.code == "PLANET_FORBIDDEN"


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
