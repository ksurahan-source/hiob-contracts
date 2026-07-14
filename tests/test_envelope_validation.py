"""런타임 계약 검증 어댑터 테스트 — 경계 fail-loud (2026-07-05 seam)."""
import pytest

from hiob_contracts import (
    ContractViolation,
    JanusBrief,
    ensure_valid,
    registered_contracts,
    validate_payload,
)


def _good_brief_dict():
    # JanusBrief.from_dict가 받는 최소 형태(brand_slug 필수).
    return {"brand_slug": "viewok", "request_text": "물안경 김서림 릴", "intake": {}}


def test_registry_lists_core_contracts():
    reg = registered_contracts()
    for name in ("JanusBrief", "BeatPlan", "MediaArtifact", "FeedbackSignal"):
        assert name in reg


def test_validate_payload_ok_parses_and_validates():
    r = validate_payload("JanusBrief", _good_brief_dict())
    assert r.ok, r.errors
    assert r.contract == "JanusBrief"
    assert isinstance(r.obj, JanusBrief)


def test_validate_payload_unknown_contract_is_violation_not_silent():
    r = validate_payload("NopeContract", {"x": 1})
    assert not r.ok
    assert any("unknown" in e for e in r.errors)


def test_validate_payload_parse_error_reported():
    # JanusBrief.from_dict에 brand_slug 없으면 validate가 필수필드 강제 → 위반.
    r = validate_payload("JanusBrief", {"request_text": "x"})
    assert not r.ok
    assert r.errors  # 조용한 통과 없음


def test_ensure_valid_raises_on_drift():
    with pytest.raises(ContractViolation) as ei:
        ensure_valid("JanusBrief", {"request_text": "no brand"})
    assert ei.value.contract == "JanusBrief"
    assert ei.value.errors


def test_ensure_valid_returns_parsed_obj_on_success():
    obj = ensure_valid("JanusBrief", _good_brief_dict())
    assert isinstance(obj, JanusBrief)


def test_validate_payload_accepts_instance_passthrough():
    obj = JanusBrief.from_dict(_good_brief_dict())
    r = validate_payload("JanusBrief", obj)  # 이미 인스턴스 → 재파싱 없이 validate
    assert r.ok
    assert r.obj is obj


def test_beatplan_from_list_path():
    # BeatPlan은 from_list(리스트 입력) 경로 — 어댑터가 리스트를 처리.
    r = validate_payload("BeatPlan", [])
    # 빈 비트는 validate가 잡을 수 있음(내용 무관, 파싱 경로가 죽지 않는지 확인)
    assert r.contract == "BeatPlan"
    assert r.obj is not None or r.errors


# ── B3: _parse 타입 우선 분기 (list가 from_dict로 새지 않게, 2026-07-05 버그헌팅) ──
from hiob_contracts.envelope_validation import _parse


class _DictOnly:
    """from_dict만 있고 from_list 없는 계약(대부분의 dict 계약 형태)."""
    def __init__(self, v):
        self.v = v

    @classmethod
    def from_dict(cls, d):
        return cls(d["v"])


class _ListOnly:
    def __init__(self, items):
        self.items = items

    @classmethod
    def from_list(cls, xs):
        return cls(list(xs))


def test_parse_list_payload_does_not_hit_from_dict():
    # B3 회귀: list payload + from_dict-only → from_dict(list) 호출(TypeError)이 아니라
    # 명시적 TypeError('from_list 없음')로 fail-loud.
    with pytest.raises(TypeError) as ei:
        _parse(_DictOnly, [{"v": 1}])
    assert "from_list" in str(ei.value)


def test_parse_dict_payload_uses_from_dict():
    obj = _parse(_DictOnly, {"v": 7})
    assert isinstance(obj, _DictOnly) and obj.v == 7


def test_parse_list_payload_uses_from_list():
    obj = _parse(_ListOnly, [1, 2, 3])
    assert isinstance(obj, _ListOnly) and obj.items == [1, 2, 3]


# ── LP1-7 / UM-1 residual: 9/9 edge targets + orpheus/apollo/metis/hermes ──
from hiob_contracts import (
    EDGES,
    OrpheusPlanInput,
    ApolloPlanInput,
    CAPIEvent,
    edge_target_contracts,
    ensure_edge_target,
    ensure_karma_edge_receipt,
    unvalidated_edge_targets,
    validate_edge_target,
    verify_karma_edge_receipt,
)
from hiob_contracts.factory import (
    ContractRef,
    KarmaEdgeReceipt,
    MapperRef,
    sha256_digest,
)

_POLICY = sha256_digest({"policy": "p1"})
_SRC = sha256_digest({"src": "ares"})


def _edge_payloads() -> dict[str, dict]:
    """Minimal valid target_input dicts for each of the 9 registry edges."""
    return {
        "j2p": {
            "brand_slug": "viewok",
            "target_audience": "초등 부모",
        },
        "p2a": {
            "brand_slug": "viewok",
            "protagonist_name": "정원이",
            "target_pain": "수영 공포",
        },
        "a2athena": {
            "beat_plan": {"beats": [{"beat_index": 0, "text": "hook"}]},
            "context": {"brand_slug": "viewok"},
        },
        "a2orpheus": {
            "music_vibe": "bright uplifting",
            "target_ms": 15000,
        },
        "a2apollo": {
            "cues": [{"beat_index": 0, "text": "splash"}],
            "asset_pool": [],
        },
        "media2atropos": {
            "run_id": "run-1",
            "media": [{"kind": "still", "beat_index": 0, "url": "https://x/a.jpg"}],
            "audio": [],
        },
        "atropos2artemis": {
            "run_id": "run-1",
            "render_status": "pending",
            "gate_passed": False,
            "beat_count": 3,
        },
        "artemis2atropos": {
            "run_id": "run-1",
            "accepted_proposals": [{"kind": "pace", "delta_ms": -100}],
        },
        "atropos2hephaestus": {
            "run_id": "run-1",
            "snapshot": {"run_id": "run-1", "render_status": "pending", "gate_passed": False},
            "approval_receipt_ref": "apr:g3-1",
            "mode": "final",
        },
    }


def test_all_nine_edges_have_registered_target_contracts():
    """UM-1: every SemanticEdge target_contract is in the validation registry."""
    mapping = edge_target_contracts()
    assert len(mapping) == 9
    assert set(mapping) == {e.edge_id for e in EDGES}
    missing = unvalidated_edge_targets()
    assert missing == (), f"unvalidated edges: {missing}"


def test_validate_edge_target_ok_for_all_nine():
    payloads = _edge_payloads()
    for edge_id, payload in payloads.items():
        r = validate_edge_target(edge_id, payload)
        assert r.ok, f"{edge_id}: {r.errors}"
        assert edge_id in r.contract


def test_validate_edge_target_unknown_edge_fail_loud():
    r = validate_edge_target("not_an_edge", {"x": 1})
    assert not r.ok
    assert any("unknown edge" in e for e in r.errors)


def test_validate_edge_target_orpheus_incomplete_fail_loud():
    """Previously-unvalidated a2orpheus: empty plan must not silently pass."""
    r = validate_edge_target("a2orpheus", {})
    assert not r.ok
    assert r.errors


def test_validate_edge_target_apollo_bad_cue_fail_loud():
    r = validate_edge_target("a2apollo", {"cues": ["not-a-dict"], "asset_pool": []})
    assert not r.ok


def test_ensure_edge_target_raises_on_forged_orpheus():
    with pytest.raises(ContractViolation) as ei:
        ensure_edge_target("a2orpheus", {"noise": True})
    assert "a2orpheus" in ei.value.contract or "Orpheus" in ei.value.contract


def test_orpheus_apollo_planet_envelopes_registered():
    reg = registered_contracts()
    for name in ("AudioRequest", "SFXRequest", "AudioClip", "OrpheusPlanInput", "ApolloPlanInput"):
        assert name in reg


def test_metis_process_insights_envelope():
    r = validate_payload(
        "ProcessInsightsRequest",
        {"raw_insights": [{"impressions": 1}], "run_brand_map": {"run-1": "viewok"}, "window_days": 7},
    )
    assert r.ok, r.errors
    bad = validate_payload("ProcessInsightsRequest", {"window_days": 0})
    assert not bad.ok


def test_hermes_capi_event_and_payload():
    ok = validate_payload(
        "CAPIEvent",
        {
            "event_name": "Purchase",
            "event_id": "ord-1",
            "event_time": 1_700_000_000,
            "user_data": {"em": "hash"},
            "custom_data": {"value": 1000},
        },
    )
    assert ok.ok, ok.errors
    assert isinstance(ok.obj, CAPIEvent)

    missing = validate_payload("CAPIEvent", {"event_name": "Purchase"})
    assert not missing.ok

    payload = validate_payload(
        "CAPIPayload",
        {
            "install_id": "inst-1",
            "event_name": "Purchase",
            "event_id": "ord-1",
            "matched_session": True,
            "params_sent": ["em", "ph"],
            "pipa_consent": True,
        },
    )
    assert payload.ok, payload.errors


def test_hephaestus_final_requires_g3_approval():
    r = validate_edge_target(
        "atropos2hephaestus",
        {
            "run_id": "run-1",
            "snapshot": {"run_id": "run-1"},
            "approval_receipt_ref": None,
            "mode": "final",
        },
    )
    assert not r.ok
    assert any("approval_receipt_ref" in e for e in r.errors)


def _accepted_receipt(*, edge_id: str, target_input: dict, created_at: str) -> KarmaEdgeReceipt:
    from hiob_contracts.factory.edge_registry import get_edge

    edge = get_edge(edge_id)
    assert edge is not None
    digest = sha256_digest(target_input)
    return KarmaEdgeReceipt(
        receipt_id="rcpt-1",
        edge_id=edge_id,
        run_id="run-1",
        factory_revision=0,
        source_output_digests=(_SRC,),
        target_contract=ContractRef(
            name=edge.target_contract, version="v1", schema_digest=_POLICY
        ),
        decision="accepted",
        target_input=target_input,
        target_input_digest=digest,
        mapper=MapperRef(
            node_id="karma.edge.refine", revision="r1", policy_digest=_POLICY
        ),
        created_at=created_at,
    )


def test_verify_karma_edge_receipt_origin_ok():
    ti = _edge_payloads()["a2orpheus"]
    receipt = _accepted_receipt(
        edge_id="a2orpheus",
        target_input=ti,
        created_at="2026-07-15T00:00:00+00:00",
    )
    r = verify_karma_edge_receipt(
        receipt,
        expected_edge_id="a2orpheus",
        expected_source_digests=(_SRC,),
        max_age_seconds=86_400,
        now="2026-07-15T01:00:00+00:00",
    )
    assert r.ok, r.errors


def test_verify_karma_edge_receipt_stale_fail_loud():
    ti = _edge_payloads()["a2apollo"]
    receipt = _accepted_receipt(
        edge_id="a2apollo",
        target_input=ti,
        created_at="2026-07-01T00:00:00+00:00",
    )
    r = verify_karma_edge_receipt(
        receipt,
        max_age_seconds=3600,
        now="2026-07-15T00:00:00+00:00",
    )
    assert not r.ok
    assert any("stale" in e for e in r.errors)


def test_verify_karma_edge_receipt_bad_mapper_fail_loud():
    ti = _edge_payloads()["a2orpheus"]
    digest = sha256_digest(ti)
    receipt = KarmaEdgeReceipt(
        receipt_id="rcpt-x",
        edge_id="a2orpheus",
        run_id="run-1",
        factory_revision=0,
        source_output_digests=(_SRC,),
        target_contract=ContractRef(
            name="OrpheusPlanInput", version="v1", schema_digest=_POLICY
        ),
        decision="accepted",
        target_input=ti,
        target_input_digest=digest,
        mapper=MapperRef(
            node_id="evil.forge", revision="r1", policy_digest=_POLICY
        ),
        created_at="2026-07-15T00:00:00+00:00",
    )
    r = verify_karma_edge_receipt(receipt, max_age_seconds=None)
    assert not r.ok
    assert any("karma.edge.refine" in e for e in r.errors)


def test_ensure_karma_edge_receipt_raises():
    with pytest.raises(ContractViolation):
        ensure_karma_edge_receipt({"not": "a receipt"})


def test_orpheus_plan_input_roundtrip():
    obj = OrpheusPlanInput.from_dict({"music_vibe": "warm", "target_ms": 1000})
    assert obj.validate() == []
    again = OrpheusPlanInput.from_dict(obj.to_dict())
    assert again.music_vibe == "warm"


def test_apollo_plan_input_roundtrip():
    obj = ApolloPlanInput.from_dict({"cues": [{"beat_index": 1, "text": "boom"}]})
    assert obj.validate() == []
    assert ApolloPlanInput.from_dict(obj.to_dict()).cues[0]["text"] == "boom"
