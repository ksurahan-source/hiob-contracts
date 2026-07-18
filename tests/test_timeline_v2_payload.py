"""Shared timelineV2 bloodline payload (Atropos ↔ Hephaestus)."""
from hiob_contracts.timeline_v2_payload import (
    TIMELINE_V2_PAYLOAD_KEYS,
    build_timeline_v2_payload,
    hephaestus_render_node_input,
    normalize_render_dispatch_url,
    stable_snapshot_id,
)


def test_build_payload_keys_and_gates():
    p = build_timeline_v2_payload(
        run_id="r1",
        snapshot_id="s1",
        input_props={"clips": [{"id": "c0"}], "fps": 30},
        mode="final",
        approved_final_render=True,
        gates_approved=True,
        callback_url="https://studio.example/cb",
    )
    assert TIMELINE_V2_PAYLOAD_KEYS <= set(p.keys())
    assert p["composition"] == "timelineV2"
    assert p["_gatesApproved"] is True
    assert p["input_props"]["_gatesApproved"] is True
    assert p["input_props"]["snapshotId"] == "s1"
    assert p["callback_url"].startswith("https://")


def test_normalize_render_url():
    assert normalize_render_dispatch_url("https://x.example") == "https://x.example/v1/render"
    assert normalize_render_dispatch_url("https://x.example/v1/render") == "https://x.example/v1/render"
    assert normalize_render_dispatch_url(None) is None


def test_stable_snapshot_id():
    a = stable_snapshot_id(run_id="r", snapshot={"selection": {"a": 1}})
    b = stable_snapshot_id(run_id="r", snapshot={"selection": {"a": 1}})
    assert a == b
    assert stable_snapshot_id(run_id="r", snapshot={}, render_job_id="job-1") == "job-1"


def test_hephaestus_render_node_input_preview_without_g3():
    inp = hephaestus_render_node_input(
        run_id="r1",
        snapshot_id="s1",
        input_props={"clips": []},
        gates_approved=True,
        approved_final_render=True,  # legacy True without digest
        approval_receipt_ref=None,
    )
    # Without G3 ref, mesh mode is preview (FR-8); gates still true
    assert inp["mode"] == "preview"
    assert inp["gates_approved"] is True
    assert inp["approved_final_render"] is True
    assert inp["render_job_id"] == "s1"


def test_hephaestus_render_node_input_final_with_g3():
    inp = hephaestus_render_node_input(
        run_id="r1",
        snapshot_id="s1",
        input_props={"clips": [{"id": "c"}]},
        gates_approved=True,
        approved_final_render=True,
        approval_receipt_ref="g3-abc",
    )
    assert inp["mode"] == "final"
    assert inp["approval_receipt_ref"] == "g3-abc"


def test_hephaestus_render_node_input_omits_empty_g3_ref():
    """Empty/whitespace receipt must not flip mode to final (strict G3 consumers)."""
    inp = hephaestus_render_node_input(
        run_id="r1",
        snapshot_id="s1",
        input_props={},
        gates_approved=True,
        approved_final_render=True,
        approval_receipt_ref="   ",
    )
    assert inp["mode"] == "preview"
    assert "approval_receipt_ref" not in inp
    assert inp["approved_final_render"] is True
