"""DecisionContext / resolve_decision — 사람↔Fable5 대칭 결정 표면 (Goal D)."""
from __future__ import annotations

from hiob_contracts import DecisionContext, resolve_decision


def _ctx(**over):
    base = dict(stage="artemis", decision="cut_timing", beat_index=2,
                brief={"request_interpretation": {"target_persona_narrow": "수영 즐기는 34세 워킹맘"}},
                persona={"persona_id": "heroine", "gender": "여성"})
    base.update(over)
    return DecisionContext(**base)


def test_validate_ok():
    assert _ctx().validate() == []


def test_validate_catches_missing_stage_decision():
    errs = DecisionContext(stage="", decision="").validate()
    assert any("stage" in e for e in errs) and any("decision" in e for e in errs)


def test_reel_global_flag():
    assert DecisionContext(stage="athena", decision="visual_blueprint", beat_index=-1).is_reel_global
    assert not _ctx(beat_index=0).is_reel_global


def test_prompt_context_includes_persona_and_narrow():
    p = _ctx().to_prompt_context()
    assert "artemis" in p and "cut_timing" in p
    assert "heroine" in p and "워킹맘" in p       # persona + 세부타겟 맥락


def test_resolve_falls_back_to_heuristic_when_no_llm():
    # llm=None → 사람 값과 동치(byte-identical). heuristic 결정론적.
    out = resolve_decision(_ctx(), None, heuristic=lambda c: {"snap": c.beat_index})
    assert out == {"snap": 2}


def test_resolve_uses_llm_then_parses():
    out = resolve_decision(_ctx(), llm=lambda p: "fast", heuristic=lambda c: "slow",
                           parse=lambda raw: raw.upper())
    assert out == "FAST"


def test_resolve_llm_failure_falls_back():
    def boom(_p):
        raise RuntimeError("fable5 down")
    out = resolve_decision(_ctx(), llm=boom, heuristic=lambda c: "safe")
    assert out == "safe"                            # fail-soft → heuristic


def test_resolve_empty_llm_output_falls_back():
    out = resolve_decision(_ctx(), llm=lambda p: "", heuristic=lambda c: "heur")
    assert out == "heur"                            # 빈 응답 → heuristic
