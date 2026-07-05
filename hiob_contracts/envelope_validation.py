"""런타임 계약 검증 어댑터 — 타입 DSL을 '열망'에서 '경계 강제'로 (2026-07-05 seam).

planet_io.PLANET_IO가 선언한 계약을 실제 런타임 경계에서 검증한다. 그동안 star DSL
registry는 `from_dict`로 파싱만 하고 `validate()`를 걸지 않아, 필드 드리프트가 조용히
통과했다(노드맵 감사: "타입 DSL=열망, god-file가 우회"). 이 어댑터는 각 계약의
파싱(from_dict/from_list/ctor) + validate()를 한 데 묶어 경계에서 fail-loud로 만든다.

부재 계약·파싱불가는 조용히 통과가 아니라 명확한 위반으로 보고한다(조용한 스왈로우 금지).
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

# 계약명 → (모듈, 클래스). 런타임 경계에서 검증할 핵심 계약(파싱·validate 보유).
_REGISTRY: dict[str, tuple[str, str]] = {
    "JanusBrief": ("hiob_contracts.janus_brief", "JanusBrief"),
    "Intake13Q": ("hiob_contracts.janus_brief", "Intake13Q"),
    "BeatPlan": ("hiob_contracts.beat_plan", "BeatPlan"),
    "Beat": ("hiob_contracts.beat_plan", "Beat"),
    "MediaArtifact": ("hiob_contracts.media_artifact", "MediaArtifact"),
    "AudioClip": ("hiob_contracts.audio_clip", "AudioClip"),
    "KlingVideo": ("hiob_contracts.klingvideo", "KlingVideo"),
    "Heroine": ("hiob_contracts.heroine", "Heroine"),
    "FeedbackSignal": ("hiob_contracts.feedback_signal", "FeedbackSignal"),
    "DefectSignal": ("hiob_contracts.defect_signal", "DefectSignal"),
    "ReelMetric": ("hiob_contracts.reel_metric", "ReelMetric"),
    "CompositionSnapshot": ("hiob_contracts.composition_snapshot", "CompositionSnapshot"),
    "EditDecisionList": ("hiob_contracts.edit_decision_list", "EditDecisionList"),
    "BeatPersona": ("hiob_contracts.beat_personas", "BeatPersona"),
    "BeatPersonas": ("hiob_contracts.beat_personas", "BeatPersonas"),
    "ElementLocks": ("hiob_contracts.element_locks", "ElementLocks"),
}


class ContractViolation(ValueError):
    """계약 검증 실패 — 경계에서 드리프트 발견. contract/errors에 사유."""

    def __init__(self, contract: str, errors: list[str]):
        self.contract = contract
        self.errors = list(errors)
        super().__init__(f"{contract} 계약 위반: {'; '.join(self.errors) or 'unknown'}")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    contract: str
    errors: tuple[str, ...] = ()
    obj: Any = None


def _resolve(name: str):
    ref = _REGISTRY.get(name)
    if not ref:
        return None
    mod, cls = ref
    try:
        return getattr(import_module(mod), cls)
    except Exception:  # noqa: BLE001 — 행성 패키지 미설치 등, 조용히 None(호출자가 unknown 보고)
        return None


def _parse(cls: Any, payload: Any) -> Any:
    """dict/list/인스턴스 → 계약 인스턴스. 타입 우선(B3): list→from_list, dict→from_dict/ctor.

    from_dict를 만능 폴백으로 쓰면 list payload가 from_dict(list)로 새서 TypeError → 타입을 먼저 본다.
    """
    if isinstance(payload, cls):
        return payload
    if isinstance(payload, list):
        if hasattr(cls, "from_list"):
            return cls.from_list(payload)
        raise TypeError(f"{cls.__name__}: list payload인데 from_list 없음")
    if isinstance(payload, dict):
        return cls.from_dict(payload) if hasattr(cls, "from_dict") else cls(**payload)
    if hasattr(cls, "from_dict"):
        return cls.from_dict(payload)
    raise TypeError(f"{cls.__name__}: dict/list/from_dict 없이 파싱 불가 (payload type={type(payload).__name__})")


def validate_payload(contract: str, payload: Any) -> ValidationResult:
    """계약명 + payload(dict/list/인스턴스) → ValidationResult(ok, errors, obj).

    파싱(from_dict/from_list/ctor) 실패 or validate() 오류 → ok=False + errors.
    파싱 성공 + validate() 없음 → ok=True(구조적으로 유효). 조용한 통과 없음.
    """
    cls = _resolve(contract)
    if cls is None:
        return ValidationResult(False, contract, (f"unknown/unavailable contract: {contract}",))
    try:
        obj = _parse(cls, payload)
    except Exception as e:  # noqa: BLE001 — 파싱 실패는 위반으로 보고(fail-loud)
        return ValidationResult(False, contract, (f"parse error: {e}",))
    errs: list[str] = []
    v = getattr(obj, "validate", None)
    if callable(v):
        try:
            errs = list(v() or [])
        except Exception as e:  # noqa: BLE001
            errs = [f"validate() raised: {e}"]
    return ValidationResult(not errs, contract, tuple(errs), obj)


def ensure_valid(contract: str, payload: Any) -> Any:
    """경계 강제 — 위반이면 ContractViolation raise, 통과면 파싱된 계약 obj 반환.

    DSL 노드/워커 경계에서 `obj = ensure_valid("JanusBrief", raw)`로 쓴다. 드리프트가
    깊은 곳에서 이상한 크래시로 번지는 대신 경계에서 명확히 멈춘다.
    """
    r = validate_payload(contract, payload)
    if not r.ok:
        raise ContractViolation(contract, list(r.errors))
    return r.obj


def registered_contracts() -> tuple[str, ...]:
    """검증 어댑터가 아는 계약명(정렬)."""
    return tuple(sorted(_REGISTRY))
