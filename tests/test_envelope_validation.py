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
