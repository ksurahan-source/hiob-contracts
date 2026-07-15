"""Overnight first-customer contracts C2–C7 (Giant Foot Overnight)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CONTRACT_VERSIONS = {
    "CreativeOrder": "CreativeOrder.v1",
    "ApprovalReceipt": "ApprovalReceipt.v1",
    "EditorApprovalReceipt": "EditorApprovalReceipt.v1",
    "PaidEffectAttempt": "PaidEffectAttempt.v1",
    "VerifiedRenderReceipt": "VerifiedRenderReceipt.v1",
    "DeliveryOutboxEvent": "DeliveryOutboxEvent.v1",
}


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def customer_order_key(
    workspace_id: str,
    customer_external_order_id: str,
    canonical_order_digest: str,
) -> str:
    material = f"{workspace_id}|{customer_external_order_id}|{canonical_order_digest}"
    return sha256_hex(material)


def effect_key(
    customer_order_key_value: str,
    approved_script_digest: str,
    effect_kind: str,
    asset_slot: str,
) -> str:
    # Must NOT include run_id, attempt_id, lease_id, provider job id, or timestamp.
    material = (
        f"{customer_order_key_value}|{approved_script_digest}|{effect_kind}|{asset_slot}"
    )
    return sha256_hex(material)


def editor_approval_digest(
    customer_order_key_value: str,
    approved_script_digest: str,
    timeline_digest: str,
    media_manifest_digest: str,
    render_policy_digest: str,
) -> str:
    material = "|".join(
        [
            customer_order_key_value,
            approved_script_digest,
            timeline_digest,
            media_manifest_digest,
            render_policy_digest,
        ]
    )
    return sha256_hex(material)


def validate_no_extra(obj: Mapping[str, Any], required: set[str], allowed: set[str]) -> None:
    keys = set(obj.keys())
    missing = required - keys
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    extra = keys - allowed
    if extra:
        raise ValueError(f"extra fields: {sorted(extra)}")


def validate_creative_order(obj: Mapping[str, Any]) -> None:
    required = {
        "contract_version",
        "customer_order_key",
        "workspace_id",
        "account_id",
        "brand_id",
        "product_or_listing_id",
        "customer_external_order_id",
        "canonical_order_payload",
        "canonical_order_digest",
        "created_at_utc",
    }
    validate_no_extra(obj, required, required)
    if obj["contract_version"] != CONTRACT_VERSIONS["CreativeOrder"]:
        raise ValueError("bad contract_version")
    if not obj["workspace_id"]:
        raise ValueError("workspace_id required")
    expected = customer_order_key(
        obj["workspace_id"],
        obj["customer_external_order_id"],
        obj["canonical_order_digest"],
    )
    if obj["customer_order_key"] != expected:
        raise ValueError("customer_order_key mismatch")


def validate_verified_render_receipt(obj: Mapping[str, Any]) -> None:
    required = {
        "verified_render_receipt_id",
        "customer_order_key",
        "workspace_id",
        "run_id",
        "render_job_id",
        "render_effect_key",
        "editor_approval_digest",
        "output_url",
        "storage_key",
        "output_sha256",
        "output_bytes",
        "duration_ms",
        "video_codec",
        "audio_codec",
        "mechanical_checker_version",
        "qa_checker_version",
        "qa_verdict",
        "qa_evidence_digest",
        "source_revisions",
        "deployed_revisions",
        "created_at_utc",
        "transaction_audit_id",
    }
    validate_no_extra(obj, required, required)
    if obj["qa_verdict"] != "PASS":
        raise ValueError("qa_verdict must be PASS")
    if not obj.get("output_sha256") or len(str(obj["output_sha256"])) != 64:
        raise ValueError("output_sha256 required")


def serialize_equal(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return _canon(a) == _canon(b)
