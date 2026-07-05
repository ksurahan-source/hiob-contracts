"""DefectSignal 계약 테스트 (Metis→Artemis per-beat 편집 피드백, 2026-07-05)."""
import pytest

from hiob_contracts import DefectSignal
from hiob_contracts import validate_payload, ensure_valid, ContractViolation, registered_contracts


def _good(**over):
    d = {"run_id": "run_x", "beat_index": 2, "metric": "ctr", "value": 0.012, "confidence": 0.8}
    d.update(over)
    return d


def test_valid_signal_passes():
    s = DefectSignal.from_dict(_good())
    assert s.validate() == []
    assert s.run_id == "run_x" and s.beat_index == 2 and s.metric == "ctr"


def test_actionable_gate_confidence():
    # confidence≥0.75 + 유효해야 actionable(학습 반영). 잡음 방지.
    assert DefectSignal.from_dict(_good(confidence=0.8)).actionable is True
    assert DefectSignal.from_dict(_good(confidence=0.5)).actionable is False


def test_invalid_metric_flagged():
    errs = DefectSignal.from_dict(_good(metric="vibes")).validate()
    assert any("metric" in e for e in errs)


def test_bounds_validation():
    assert any("confidence" in e for e in DefectSignal.from_dict(_good(confidence=1.7)).validate())
    assert any("arc_pct" in e for e in DefectSignal.from_dict(_good(arc_pct=2.0)).validate())
    assert any("beat_index" in e for e in DefectSignal.from_dict(_good(beat_index=-1)).validate())
    assert any("run_id" in e for e in DefectSignal.from_dict(_good(run_id="")).validate())


def test_from_dict_coerces_and_defaults():
    s = DefectSignal.from_dict({"run_id": "r", "beat_index": "3", "metric": "roas", "value": "1.5"})
    assert s.beat_index == 3 and s.value == 1.5 and s.arc_pct == 0.0 and s.confidence == 0.0
    assert s.actionable is False  # confidence 기본 0 → 학습 미반영


def test_registered_in_envelope_and_ensure_valid():
    assert "DefectSignal" in registered_contracts()
    r = validate_payload("DefectSignal", _good())
    assert r.ok and isinstance(r.obj, DefectSignal)
    with pytest.raises(ContractViolation):
        ensure_valid("DefectSignal", _good(metric="bad", confidence=3.0))
