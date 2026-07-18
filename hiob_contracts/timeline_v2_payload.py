"""timelineV2 render POST body — shared Atropos compose ↔ Hephaestus bloodline.

Pure (stdlib only). Field names must match the Hephaestus JS `/v1/render`
timelineV2 branch and Atropos `compose_and_render_v2` dispatch.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


# Keys that must appear on every live timelineV2 dispatch.
TIMELINE_V2_PAYLOAD_KEYS = frozenset({
    "snapshot_id",
    "run_id",
    "input_props",
    "composition",
    "mode",
    "approvedFinalRender",
    "_gatesApproved",
})


def normalize_render_dispatch_url(url: str | None) -> str | None:
    """Normalize RENDERER_DISPATCH_URL / RENDER_TRIGGER_URL to …/v1/render."""
    if not url or not str(url).strip():
        return None
    u = str(url).strip()
    # Keep query/fragment if full URL; force path to /v1/render when host given
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(u)
        if parts.scheme and parts.netloc:
            path = parts.path.rstrip("/")
            if path != "/v1/render":
                return urlunsplit((parts.scheme, parts.netloc, "/v1/render", parts.query, parts.fragment))
            return u
    except Exception:  # noqa: BLE001
        pass
    u = u.rstrip("/")
    if u.endswith("/v1/render"):
        return u
    return f"{u}/v1/render"


def stable_snapshot_id(*, run_id: str, snapshot: dict[str, Any] | None = None, render_job_id: str = "") -> str:
    """Deterministic snapshot id when DB row id is absent (mesh path)."""
    if render_job_id and str(render_job_id).strip():
        return str(render_job_id).strip()
    snap = snapshot if isinstance(snapshot, dict) else {}
    existing = snap.get("id") or snap.get("snapshot_id")
    if existing and str(existing).strip():
        return str(existing).strip()
    material = {
        "run_id": run_id,
        "selection": snap.get("selection") or {},
        "render_status": snap.get("render_status") or "pending",
        "gate_passed": bool(snap.get("gate_passed", False)),
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:24]
    return f"snap-{digest}"


def build_timeline_v2_payload(
    *,
    run_id: str,
    snapshot_id: str,
    input_props: dict[str, Any],
    mode: str = "final",
    approved_final_render: bool = False,
    gates_approved: bool = False,
    callback_url: str | None = None,
) -> dict[str, Any]:
    """Build the exact POST body for Hephaestus JS `/v1/render` (timelineV2).

    Identical contract for:
      - Atropos compose_and_render_v2 (direct Remotion URL)
      - hephaestus.render mesh node (then posts to Remotion)
    """
    props = dict(input_props or {})
    props["_gatesApproved"] = bool(gates_approved)
    if snapshot_id and not props.get("snapshotId"):
        props["snapshotId"] = snapshot_id

    payload: dict[str, Any] = {
        "snapshot_id": str(snapshot_id),
        "run_id": str(run_id),
        "input_props": props,
        "composition": "timelineV2",
        "mode": str(mode or "final"),
        "approvedFinalRender": bool(approved_final_render),
        "_gatesApproved": bool(gates_approved),
    }
    if callback_url and str(callback_url).strip():
        payload["callback_url"] = str(callback_url).strip()
    return payload


def hephaestus_render_node_input(
    *,
    run_id: str,
    snapshot_id: str,
    input_props: dict[str, Any],
    gates_approved: bool,
    approved_final_render: bool,
    callback_url: str | None = None,
    approval_receipt_ref: str | None = None,
    snapshot: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Mesh input for POST …/v1/nodes/hephaestus.render/runs ``input`` field.

    FR-8: ``mode=final`` only when ``approval_receipt_ref`` is set.
    Legacy production may still set ``approved_final_render=True`` without G3 —
    that flag is carried separately so Remotion body stays compatible.

    Hephaestus enforces G3 at dispatch: always for ``mode=final``; under
    ``ATROPOS_APPROVAL_SOURCE=strict`` / ``HIOB_REQUIRE_G3_FOR_FINAL=1`` also for
    ``approved_final_render=True``. Callers should pass the digest as
    ``approval_receipt_ref`` when available.
    """
    has_g3 = bool(approval_receipt_ref and str(approval_receipt_ref).strip())
    mode = "final" if has_g3 else "preview"

    snap = dict(snapshot or {})
    snap.setdefault("run_id", run_id)
    snap.setdefault("id", snapshot_id)
    snap.setdefault("gate_passed", bool(gates_approved))

    out: dict[str, Any] = {
        "run_id": run_id,
        "snapshot": snap,
        "render_job_id": snapshot_id,
        "mode": mode,
        "input_props": dict(input_props or {}),
        "gates_approved": bool(gates_approved),
        "approved_final_render": bool(approved_final_render),
    }
    if has_g3:
        out["approval_receipt_ref"] = str(approval_receipt_ref).strip()
    if callback_url:
        out["callback_url"] = callback_url
    return out


__all__ = [
    "TIMELINE_V2_PAYLOAD_KEYS",
    "normalize_render_dispatch_url",
    "stable_snapshot_id",
    "build_timeline_v2_payload",
    "hephaestus_render_node_input",
]
