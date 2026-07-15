"""Strict C2-C6 v2 contract tests shared by Studio, Star, and Modal.

The v2 seam is intentionally narrower than the database implementation: every
object is immutable, rejects unknown/coerced fields, and binds durable identity
to exact content digests before a caller is allowed to persist it.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    CreativeOrderV2,
    EditorApprovalReceiptV2,
    PaidEffectAttemptV2,
    PaidEffectIntentV2,
    ScriptApprovalReceiptV2,
    VerifiedRenderReceiptV2,
    derive_customer_order_key_v2,
    derive_editor_approval_digest_v2,
    derive_effect_key_v2,
    sha256_digest,
)


PAYLOAD = {"brief_id": "brief-1", "format": "reel"}
ORDER_DIGEST = sha256_digest(PAYLOAD)
ORDER_KEY = derive_customer_order_key_v2("ws-1", "EXT-1")
SCRIPT_DIGEST = "sha256:f713d17db5aba230e0b9226632b19d9ea6c2e3f7d6e1b1a8ae7e16aab0e1e4a4"
TIMELINE_DIGEST = "sha256:94d192b3a326be1f019b71ef13ea5a367ffe939c5e9a88f1b270e53753d9569a"
MEDIA_DIGEST = "sha256:721c9525ade2ea8903d343ef25cf68b9bf4ab0aad56bb7b01fbe48d09bc7fcf4"
POLICY_DIGEST = "sha256:823412d1eacb67956220e532959f0104603057c88704863ca38e7cd188fda812"
REQUEST_DIGEST = sha256_digest({"prompt": "make hero visual"})
QA_DIGEST = sha256_digest({"checker": "qa-v2", "result": "PASS"})
VIDEO_BYTES = b"exact-customer-video-bytes"
VIDEO_SHA256 = hashlib.sha256(VIDEO_BYTES).hexdigest()


def order_data() -> dict:
    return {
        "contract_version": "CreativeOrder.v2",
        "customer_order_key": ORDER_KEY,
        "workspace_id": "ws-1",
        "account_id": "acct-1",
        "brand_id": "brand-1",
        "product_or_listing_id": "listing-1",
        "customer_external_order_id": "EXT-1",
        "canonical_order_payload": deepcopy(PAYLOAD),
        "canonical_order_digest": ORDER_DIGEST,
        "created_at_utc": "2026-07-16T00:00:00Z",
    }


def script_approval_data() -> dict:
    return {
        "contract_version": "ScriptApprovalReceipt.v2",
        "approval_receipt_id": "approval-1",
        "customer_order_key": ORDER_KEY,
        "workspace_id": "ws-1",
        "approval_kind": "script",
        "approver_account_id": "acct-1",
        "order_digest": ORDER_DIGEST,
        "script_digest": SCRIPT_DIGEST,
        "policy_digest": POLICY_DIGEST,
        "approved_at_utc": "2026-07-16T00:01:00Z",
        "transaction_audit_id": "tx-approval-1",
    }


def editor_approval_data() -> dict:
    editor_digest = derive_editor_approval_digest_v2(
        ORDER_KEY,
        SCRIPT_DIGEST,
        TIMELINE_DIGEST,
        MEDIA_DIGEST,
        POLICY_DIGEST,
    )
    return {
        "contract_version": "EditorApprovalReceipt.v2",
        "editor_approval_receipt_id": "editor-approval-1",
        "customer_order_key": ORDER_KEY,
        "workspace_id": "ws-1",
        "editor_account_id": "acct-1",
        "approved_script_digest": SCRIPT_DIGEST,
        "timeline_digest": TIMELINE_DIGEST,
        "media_manifest_digest": MEDIA_DIGEST,
        "render_policy_digest": POLICY_DIGEST,
        "editor_approval_digest": editor_digest,
        "approved_at_utc": "2026-07-16T00:02:00Z",
    }


def effect_intent_data() -> dict:
    effect_key = derive_effect_key_v2(
        ORDER_KEY,
        SCRIPT_DIGEST,
        "visual",
        "hero",
    )
    return {
        "contract_version": "PaidEffectIntent.v2",
        "effect_key": effect_key,
        "customer_order_key": ORDER_KEY,
        "workspace_id": "ws-1",
        "approved_script_digest": SCRIPT_DIGEST,
        "effect_kind": "visual",
        "asset_slot": "hero",
        "request_digest": REQUEST_DIGEST,
        "spend_ceiling": 2.5,
        "currency": "USD",
        "created_at_utc": "2026-07-16T00:03:00Z",
    }


def effect_attempt_data() -> dict:
    intent = effect_intent_data()
    return {
        "contract_version": "PaidEffectAttempt.v2",
        "effect_key": intent["effect_key"],
        "customer_order_key": ORDER_KEY,
        "workspace_id": "ws-1",
        "approved_script_digest": SCRIPT_DIGEST,
        "effect_kind": "visual",
        "asset_slot": "hero",
        "attempt_id": "attempt-1",
        "attempt_number": 1,
        "provider": "fal",
        "provider_idempotency_key": "provider-key-1",
        "provider_job_id": None,
        "state": "CLAIMED",
        "lease_owner": "worker-1",
        "lease_expires_at_utc": "2026-07-16T00:08:00Z",
        "fencing_token": 1,
        "request_digest": REQUEST_DIGEST,
        "spend_ceiling": 2.5,
        "currency": "USD",
        "response_digest": None,
        "cost_currency": None,
        "cost_amount": None,
        "last_reconciled_at_utc": None,
        "created_at_utc": "2026-07-16T00:03:00Z",
        "updated_at_utc": "2026-07-16T00:03:00Z",
    }


def verified_render_data() -> dict:
    editor = editor_approval_data()
    return {
        "contract_version": "VerifiedRenderReceipt.v2",
        "verified_render_receipt_id": "render-receipt-1",
        "customer_order_key": ORDER_KEY,
        "workspace_id": "ws-1",
        "run_id": "run-1",
        "render_job_id": "render-job-1",
        "render_effect_key": derive_effect_key_v2(
            ORDER_KEY, SCRIPT_DIGEST, "render", "final"
        ),
        "editor_approval_digest": editor["editor_approval_digest"],
        "output_url": "https://cdn.hi-ob.com/customer/final.mp4",
        "storage_key": "customer/final.mp4",
        "output_sha256": VIDEO_SHA256,
        "output_bytes": len(VIDEO_BYTES),
        "duration_ms": 15_000,
        "video_codec": "h264",
        "audio_codec": "aac",
        "mechanical_checker_version": "mechanical.v2",
        "qa_checker_version": "qa.v2",
        "qa_verdict": "PASS",
        "qa_evidence_digest": QA_DIGEST,
        "source_revisions": {"hiob-star": "abc123"},
        "deployed_revisions": {"modal": "v616"},
        "created_at_utc": "2026-07-16T00:10:00Z",
        "transaction_audit_id": "tx-render-1",
    }


STRICT_CASES = (
    (CreativeOrderV2, order_data, "workspace_id"),
    (ScriptApprovalReceiptV2, script_approval_data, "workspace_id"),
    (EditorApprovalReceiptV2, editor_approval_data, "workspace_id"),
    (PaidEffectIntentV2, effect_intent_data, "workspace_id"),
    (PaidEffectAttemptV2, effect_attempt_data, "workspace_id"),
    (VerifiedRenderReceiptV2, verified_render_data, "workspace_id"),
)


@pytest.mark.parametrize(("model", "factory", "required_field"), STRICT_CASES)
def test_v2_contracts_accept_exact_valid_objects(model, factory, required_field):
    parsed = model.model_validate(factory())
    assert parsed.contract_version.endswith(".v2")


@pytest.mark.parametrize(("model", "factory", "required_field"), STRICT_CASES)
def test_v2_contracts_reject_missing_fields(model, factory, required_field):
    data = factory()
    del data[required_field]
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(("model", "factory", "required_field"), STRICT_CASES)
def test_v2_contracts_reject_extra_fields(model, factory, required_field):
    data = factory()
    data["unsealed_extra"] = True
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(("model", "factory", "required_field"), STRICT_CASES)
def test_v2_contracts_reject_wrong_types_without_coercion(model, factory, required_field):
    data = factory()
    data[required_field] = 123
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(("model", "factory", "required_field"), STRICT_CASES)
def test_v2_contracts_reject_wrong_schema_version(model, factory, required_field):
    data = factory()
    data["contract_version"] = data["contract_version"].replace(".v2", ".v1")
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_order_key_and_payload_digest_are_stable_and_runtime_identity_free():
    assert ORDER_DIGEST == (
        "sha256:235052d5f6e3ceb0cabdb7144e651c1c548eff5a3d896b9ab1975c4075c2d842"
    )
    assert ORDER_KEY == "de0148e8df681a168f9bccf19c155e6f2f69d092377221cd23e66b8c4b23758a"
    assert ORDER_KEY == derive_customer_order_key_v2("ws-1", "EXT-1")

    changed_payload = {"brief_id": "brief-1", "format": "story"}
    changed_digest = sha256_digest(changed_payload)
    assert changed_digest != ORDER_DIGEST
    assert derive_customer_order_key_v2("ws-1", "EXT-1") == ORDER_KEY
    changed = order_data()
    changed["canonical_order_payload"] = changed_payload
    changed["canonical_order_digest"] = changed_digest
    # The model validates one candidate. The persistence RPC compares this digest
    # with the stored row and returns CONFLICT instead of minting a second key.
    assert CreativeOrderV2.model_validate(changed).customer_order_key == ORDER_KEY

    for forbidden in ("run_id", "attempt_id"):
        data = order_data()
        data["canonical_order_payload"][forbidden] = "ephemeral"
        data["canonical_order_digest"] = sha256_digest(data["canonical_order_payload"])
        data["customer_order_key"] = derive_customer_order_key_v2(
            data["workspace_id"], data["customer_external_order_id"]
        )
        with pytest.raises(ValidationError):
            CreativeOrderV2.model_validate(data)


def test_creative_order_rejects_tampered_payload_digest_and_key():
    bad_digest = order_data()
    bad_digest["canonical_order_digest"] = SCRIPT_DIGEST
    with pytest.raises(ValidationError):
        CreativeOrderV2.model_validate(bad_digest)

    bad_key = order_data()
    bad_key["customer_order_key"] = "0" * 64
    with pytest.raises(ValidationError):
        CreativeOrderV2.model_validate(bad_key)


def test_script_receipt_binds_exact_order_script_policy_and_kind():
    order = CreativeOrderV2.model_validate(order_data())
    receipt = ScriptApprovalReceiptV2.model_validate(script_approval_data())
    assert receipt.binds(order, SCRIPT_DIGEST, POLICY_DIGEST)
    assert not receipt.binds(order, TIMELINE_DIGEST, POLICY_DIGEST)

    wrong_kind = script_approval_data()
    wrong_kind["approval_kind"] = "editor"
    with pytest.raises(ValidationError):
        ScriptApprovalReceiptV2.model_validate(wrong_kind)


def test_editor_receipt_digest_is_exact_and_has_no_future_output():
    script_receipt = ScriptApprovalReceiptV2.model_validate(script_approval_data())
    receipt = EditorApprovalReceiptV2.model_validate(editor_approval_data())
    assert receipt.binds(script_receipt)
    assert receipt.editor_approval_digest == (
        "sha256:fbb0a245357cbcd3cbccaec9d513a0b202bf07f5814b2f1bcf86cc48fbd440d0"
    )

    tampered = editor_approval_data()
    tampered["timeline_digest"] = ORDER_DIGEST
    with pytest.raises(ValidationError):
        EditorApprovalReceiptV2.model_validate(tampered)

    future_output = editor_approval_data()
    future_output["output_sha256"] = VIDEO_SHA256
    with pytest.raises(ValidationError):
        EditorApprovalReceiptV2.model_validate(future_output)


def test_effect_identity_is_stable_across_attempts_and_attempt_binds_intent():
    intent = PaidEffectIntentV2.model_validate(effect_intent_data())
    attempt = PaidEffectAttemptV2.model_validate(effect_attempt_data())
    assert intent.effect_key == (
        "49f64ea6899239360a7b8b5e92d6c12fd40e3519d34c7d38e080a414d3675968"
    )
    assert attempt.binds(intent)

    retry = effect_attempt_data()
    retry.update(
        attempt_id="attempt-2",
        attempt_number=2,
        provider="piapi",
        provider_idempotency_key="provider-key-2",
        fencing_token=2,
    )
    assert PaidEffectAttemptV2.model_validate(retry).effect_key == intent.effect_key


def test_effect_contracts_reject_wrong_identity_enum_and_terminal_shape():
    wrong_key = effect_intent_data()
    wrong_key["effect_key"] = "0" * 64
    with pytest.raises(ValidationError):
        PaidEffectIntentV2.model_validate(wrong_key)

    wrong_kind = effect_intent_data()
    wrong_kind["effect_kind"] = "unknown_paid_thing"
    with pytest.raises(ValidationError):
        PaidEffectIntentV2.model_validate(wrong_kind)

    for bad_cap in (0, -0.01):
        bad_spend = effect_intent_data()
        bad_spend["spend_ceiling"] = bad_cap
        with pytest.raises(ValidationError):
            PaidEffectIntentV2.model_validate(bad_spend)

    bad_currency = effect_intent_data()
    bad_currency["currency"] = "usd"
    with pytest.raises(ValidationError):
        PaidEffectIntentV2.model_validate(bad_currency)

    wrong_state = effect_attempt_data()
    wrong_state["state"] = "UNKNOWN"
    with pytest.raises(ValidationError):
        PaidEffectAttemptV2.model_validate(wrong_state)

    started_without_job = effect_attempt_data()
    started_without_job["state"] = "PROVIDER_STARTED"
    with pytest.raises(ValidationError):
        PaidEffectAttemptV2.model_validate(started_without_job)

    succeeded_without_response = effect_attempt_data()
    succeeded_without_response.update(state="SUCCEEDED", provider_job_id="job-1")
    with pytest.raises(ValidationError):
        PaidEffectAttemptV2.model_validate(succeeded_without_response)

    overspend = effect_attempt_data()
    overspend.update(cost_currency="USD", cost_amount=3.0)
    with pytest.raises(ValidationError):
        PaidEffectAttemptV2.model_validate(overspend)


def test_verified_receipt_requires_pass_exact_sha_and_exact_editor_binding():
    editor = EditorApprovalReceiptV2.model_validate(editor_approval_data())
    receipt = VerifiedRenderReceiptV2.model_validate(verified_render_data())
    assert receipt.binds(editor)
    assert receipt.matches_output_bytes(VIDEO_BYTES)
    assert not receipt.matches_output_bytes(b"different-bytes")

    for bad_sha in ("A" * 64, "a" * 63, f"sha256:{'a' * 64}"):
        data = verified_render_data()
        data["output_sha256"] = bad_sha
        with pytest.raises(ValidationError):
            VerifiedRenderReceiptV2.model_validate(data)

    failed = verified_render_data()
    failed["qa_verdict"] = "FAIL"
    with pytest.raises(ValidationError):
        VerifiedRenderReceiptV2.model_validate(failed)

    mismatched_editor = verified_render_data()
    mismatched_editor["editor_approval_digest"] = ORDER_DIGEST
    parsed = VerifiedRenderReceiptV2.model_validate(mismatched_editor)
    assert not parsed.binds(editor)
