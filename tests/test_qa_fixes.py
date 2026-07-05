"""QA 감사(2026-07-05) 확정 버그 회귀 테스트 — 계약층."""
from __future__ import annotations

from hiob_contracts.beat_personas import BeatPersona, BeatPersonas
from hiob_contracts.element_locks import ElementLocks
from hiob_contracts.planet_envelopes import RenderJobResponse


# ── QA#8: BeatPersona.from_dict 비정수 beat_index 크래시 금지 ──
def test_beat_persona_non_int_beat_index_no_crash():
    p = BeatPersona.from_dict({"beat_index": "abc", "id": "x"}, beat_index=3)
    assert p.beat_index == 3                       # 위치 폴백(크래시 아님)
    p2 = BeatPersona.from_dict({"beat_index": "5"}, beat_index=0)
    assert p2.beat_index == 5                       # 숫자 문자열은 파싱
    p3 = BeatPersona.from_dict({"beat_index": 2.0})
    assert p3.beat_index == 2
    # from_list도 견딤
    bps = BeatPersonas.from_list([{"beat_index": "bad", "id": "a"}, {"id": "b"}])
    assert [x.beat_index for x in bps] == [0, 1]    # 전부 위치 폴백


# ── QA#9/#2: ElementLocks.from_dict 비정수 version 크래시 금지 ──
def test_element_locks_non_int_version_no_crash():
    assert ElementLocks.from_dict({"version": "2.5"}).version == 2
    assert ElementLocks.from_dict({"version": "not_an_int"}).version == 0
    assert ElementLocks.from_dict({"version": None}).version == 0
    assert ElementLocks.from_dict({"version": 3}).version == 3
    assert ElementLocks.from_dict({"version": True}).version == 0   # bool은 int 아님


# ── QA#1: RenderJobResponse.from_render_result 0.0초 유실 금지 ──
def test_render_response_preserves_zero_duration():
    r = RenderJobResponse.from_render_result(
        "j1", {"success": True, "outputUrl": "u", "duration_s": 0.0, "durationS": 5.0})
    assert r.duration_s == 0.0                       # 0.0을 falsy로 잃지 않음
    r2 = RenderJobResponse.from_render_result("j2", {"success": True, "durationS": 5.0})
    assert r2.duration_s == 5.0                      # duration_s 부재 시 camelCase 폴백
