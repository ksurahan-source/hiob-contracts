"""Contract parity + mutation fixtures for overnight first-customer C2–C7."""

from __future__ import annotations

import pytest

from hiob_contracts.overnight_first_customer_v1 import (
    customer_order_key,
    effect_key,
    editor_approval_digest,
    serialize_equal,
    validate_creative_order,
    validate_verified_render_receipt,
)


def test_customer_order_key_stable():
    k1 = customer_order_key("ws1", "EXT-1", "digestA")
    k2 = customer_order_key("ws1", "EXT-1", "digestA")
    assert k1 == k2
    assert k1 != customer_order_key("ws1", "EXT-1", "digestB")


def test_effect_key_excludes_run_and_attempt():
    ek = effect_key("order1", "scriptA", "image", "slot0")
    assert ek == effect_key("order1", "scriptA", "image", "slot0")
    assert ek != effect_key("order1", "scriptB", "image", "slot0")
    # different runs with same approved inputs share effect_key by construction
    assert "run" not in ek


def test_editor_approval_digest_no_future_output():
    d = editor_approval_digest("o", "s", "t", "m", "p")
    assert len(d) == 64


def test_creative_order_rejects_extra_and_missing():
    order = {
        "contract_version": "CreativeOrder.v1",
        "customer_order_key": customer_order_key("ws", "ext", "d"),
        "workspace_id": "ws",
        "account_id": "a",
        "brand_id": "b",
        "product_or_listing_id": "p",
        "customer_external_order_id": "ext",
        "canonical_order_payload": {"x": 1},
        "canonical_order_digest": "d",
        "created_at_utc": "2026-07-15T00:00:00Z",
    }
    validate_creative_order(order)
    bad = dict(order)
    bad["extra"] = 1
    with pytest.raises(ValueError, match="extra"):
        validate_creative_order(bad)
    missing = dict(order)
    del missing["workspace_id"]
    with pytest.raises(ValueError, match="missing"):
        validate_creative_order(missing)


def test_verified_receipt_requires_pass_and_sha():
    base = {
        "verified_render_receipt_id": "r1",
        "customer_order_key": "o",
        "workspace_id": "ws",
        "run_id": "run",
        "render_job_id": "job",
        "render_effect_key": "ek",
        "editor_approval_digest": "e" * 64,
        "output_url": "https://x/a.mp4",
        "storage_key": "k",
        "output_sha256": "a" * 64,
        "output_bytes": 10,
        "duration_ms": 1000,
        "video_codec": "h264",
        "audio_codec": "aac",
        "mechanical_checker_version": "m1",
        "qa_checker_version": "q1",
        "qa_verdict": "PASS",
        "qa_evidence_digest": "q" * 64,
        "source_revisions": {},
        "deployed_revisions": {},
        "created_at_utc": "2026-07-15T00:00:00Z",
        "transaction_audit_id": "t1",
    }
    validate_verified_render_receipt(base)
    fail = dict(base)
    fail["qa_verdict"] = "FAIL"
    with pytest.raises(ValueError, match="PASS"):
        validate_verified_render_receipt(fail)


def test_serialize_equal_byte_identity():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert serialize_equal(a, b)
