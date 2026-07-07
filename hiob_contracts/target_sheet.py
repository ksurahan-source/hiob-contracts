"""TargetSheet — 4층 계약 (Identity·Grounding·Persona·Visual, 2026-07-07).

Parzifal에서 CharacterMasterSheet를 분해하는 4층 고분해능 계약.
Janus(L1+L2)·Ares(L3)·Parzifal(L4) 흐름 명시화 + 각 층의 의존성 격리.

4층 설계:
- L1 Identity (Soul): 고정된 기본정체성(name, age, gender, region, background, language, confidence)
- L2 Grounding (Motivation): 동기·배경 설정(pain_points, blocker, jtbd, activity_context, interest, children, demographics, voc_evidence)
- L3 Persona (Speak): 인물상·발화방식(protagonist_role, voice_persona, voice_concept, speaking_style, narrative_arc, gaze_mode, ...)
- L4 Visual (Element+Cinema): 시각 요소(CharacterMasterSheet 재사용: angles[]·expressions[]·wardrobe)

데이터흐름:
- L1+L2: Janus NarrowPersona → identity_from_narrow(), narrow_settings()로 추출(변경 0)
- L3: Ares protagonist_axis resolved + Character → persona_to_L3() 맵 (계산 0)
- L4: Parzifal SheetPanel[] + wardrobe → CharacterMasterSheet 래핑

소비 호환: Athena는 기존 CharacterMasterSheet.to_character_lock() 브릿지 유지.
TargetSheet → CharacterMasterSheet 변환(as_master_sheet)로 투명 하위호환.

D-51 준수: 모든 함수는 순수(부수효과 0, 입력만 소비, 원본 무변경).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .parzifal_master_sheet import CharacterMasterSheet, SheetPanel, _panels


# === L1: Identity 표준 필드 ===
IDENTITY_FIELDS = ("id", "name", "age", "age_band", "gender", "region", "background", "language", "confidence")

# === L2: Grounding 표준 필드 ===
GROUNDING_FIELDS = (
    "pain_points", "pain_points_source",
    "blocker", "blocker_source",
    "jtbd", "jtbd_source",
    "activity_context", "interest", "children",
    "demographics", "voc_evidence"
)

# === L3: Persona 표준 필드 ===
PERSONA_FIELDS = (
    "protagonist_role", "actor_archetype", "role_description",
    "narrative_arc", "voice_persona", "voice_concept",
    "speaking_style", "logic_structure",
    "tone_and_manner", "backstory",
    "gender_axis", "gaze_mode"
)

# === L4: Visual은 CharacterMasterSheet에 위임 (angles, expressions, wardrobe) ===


@dataclass(frozen=True)
class IdentityLayer:
    """L1: Identity (Soul) — 고정된 기본정체성. 변경 불가."""

    id: str = ""                      # persona_id / UUID
    name: str = ""
    age: Optional[int] = None
    age_band: str = ""                # "30-40" 등
    gender: str = ""                  # female | male | neutral
    region: str = ""                  # location
    background: str = ""              # actor_archetype / character description
    language: str = "ko"
    confidence: str = "approved"      # ear_test_pending | approved

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.id:
            errs.append("IdentityLayer.id 없음")
        if not self.name:
            errs.append("IdentityLayer.name 없음")
        if self.gender and self.gender not in ("female", "male", "neutral"):
            errs.append(f"IdentityLayer.gender 미지원: {self.gender}")
        if self.confidence and self.confidence not in ("ear_test_pending", "approved"):
            errs.append(f"IdentityLayer.confidence 미지원: {self.confidence}")
        return errs

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "age": self.age, "age_band": self.age_band,
            "gender": self.gender, "region": self.region, "background": self.background,
            "language": self.language, "confidence": self.confidence
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "IdentityLayer":
        d = d or {}
        return cls(
            id=str(d.get("id") or ""), name=str(d.get("name") or ""),
            age=int(d["age"]) if d.get("age") is not None else None,
            age_band=str(d.get("age_band") or ""),
            gender=str(d.get("gender") or ""), region=str(d.get("region") or ""),
            background=str(d.get("background") or ""), language=str(d.get("language") or "ko"),
            confidence=str(d.get("confidence") or "approved")
        )


@dataclass(frozen=True)
class GroundingLayer:
    """L2: Grounding (Motivation) — 동기·배경 설정. Janus NarrowPersona 데이터."""

    pain_points: str = ""             # trigger, 문제 정의
    pain_points_source: str = ""      # naver_review | catalog | invented
    blocker: str = ""                 # 방해요소
    blocker_source: str = ""
    jtbd: str = ""                    # true_want, 진정한 욕구
    jtbd_source: str = ""
    activity_context: str = ""        # 왜 이 활동을 하는가
    interest: str = ""                # 관심사
    children: str = ""                # 가족·자녀 콘텍스트
    demographics: str = ""            # narrow_segment 설명
    voc_evidence: str = ""            # VoC 직접 인용

    def validate(self) -> list[str]:
        errs: list[str] = []
        for field in ("pain_points_source", "blocker_source", "jtbd_source"):
            val = getattr(self, field, "")
            if val and val not in ("naver_review", "catalog", "invented"):
                errs.append(f"GroundingLayer.{field} 미지원: {val}")
        return errs

    def to_dict(self) -> dict:
        return {
            "pain_points": self.pain_points, "pain_points_source": self.pain_points_source,
            "blocker": self.blocker, "blocker_source": self.blocker_source,
            "jtbd": self.jtbd, "jtbd_source": self.jtbd_source,
            "activity_context": self.activity_context, "interest": self.interest,
            "children": self.children, "demographics": self.demographics,
            "voc_evidence": self.voc_evidence
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "GroundingLayer":
        d = d or {}
        return cls(
            pain_points=str(d.get("pain_points") or ""),
            pain_points_source=str(d.get("pain_points_source") or ""),
            blocker=str(d.get("blocker") or ""), blocker_source=str(d.get("blocker_source") or ""),
            jtbd=str(d.get("jtbd") or ""), jtbd_source=str(d.get("jtbd_source") or ""),
            activity_context=str(d.get("activity_context") or ""),
            interest=str(d.get("interest") or ""), children=str(d.get("children") or ""),
            demographics=str(d.get("demographics") or ""), voc_evidence=str(d.get("voc_evidence") or "")
        )


@dataclass(frozen=True)
class PersonaLayer:
    """L3: Persona (Speak) — 인물상·발화방식. Ares protagonist_axis + Character 통합."""

    protagonist_role: str = ""        # narrator | hero | heroine | opponent
    actor_archetype: str = ""         # role_description
    narrative_arc: str = ""           # virgin_promise | hero | heroine
    voice_persona: str = ""           # male1-3 | female1-3 (gender lane lock)
    voice_concept: str = ""           # friendly | urgent | news
    speaking_style: str = ""          # tonality, manner of speech
    logic_structure: str = ""         # how protagonist thinks/acts
    tone_and_manner: str = ""         # character personality
    backstory: str = ""               # character history
    gender_axis: str = ""             # female_led | hero | neutral
    gaze_mode: str = ""               # female_gaze | neutral

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.protagonist_role and self.protagonist_role not in ("narrator", "hero", "heroine", "opponent"):
            errs.append(f"PersonaLayer.protagonist_role 미지원: {self.protagonist_role}")
        if self.gender_axis and self.gender_axis not in ("female_led", "hero", "neutral"):
            errs.append(f"PersonaLayer.gender_axis 미지원: {self.gender_axis}")
        if self.gaze_mode and self.gaze_mode not in ("female_gaze", "neutral"):
            errs.append(f"PersonaLayer.gaze_mode 미지원: {self.gaze_mode}")
        return errs

    def to_dict(self) -> dict:
        return {
            "protagonist_role": self.protagonist_role, "actor_archetype": self.actor_archetype,
            "narrative_arc": self.narrative_arc, "voice_persona": self.voice_persona,
            "voice_concept": self.voice_concept, "speaking_style": self.speaking_style,
            "logic_structure": self.logic_structure, "tone_and_manner": self.tone_and_manner,
            "backstory": self.backstory, "gender_axis": self.gender_axis, "gaze_mode": self.gaze_mode
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "PersonaLayer":
        d = d or {}
        return cls(
            protagonist_role=str(d.get("protagonist_role") or ""),
            actor_archetype=str(d.get("actor_archetype") or ""),
            narrative_arc=str(d.get("narrative_arc") or ""),
            voice_persona=str(d.get("voice_persona") or ""),
            voice_concept=str(d.get("voice_concept") or ""),
            speaking_style=str(d.get("speaking_style") or ""),
            logic_structure=str(d.get("logic_structure") or ""),
            tone_and_manner=str(d.get("tone_and_manner") or ""),
            backstory=str(d.get("backstory") or ""),
            gender_axis=str(d.get("gender_axis") or ""),
            gaze_mode=str(d.get("gaze_mode") or "")
        )


@dataclass(frozen=True)
class TargetSheet:
    """4층 타겟시트 — Identity·Grounding·Persona·Visual 분해.

    CharacterMasterSheet를 4층 고분해능으로 풀어 각 계층의 의존성 명시화.
    Parzifal의 CharacterMasterSheet.identity + narrow_target + 추가필드를
    L1, L2, L3, (L4=CharacterMasterSheet)로 구조화.

    소비: Athena는 as_master_sheet() 브릿지로 기존 CharacterMasterSheet와 동일하게 처리.
    """

    persona_id: str = ""              # 고유 식별자
    identity: IdentityLayer = field(default_factory=IdentityLayer)
    grounding: GroundingLayer = field(default_factory=GroundingLayer)
    persona: PersonaLayer = field(default_factory=PersonaLayer)
    visual: CharacterMasterSheet = field(default_factory=lambda: CharacterMasterSheet())

    def validate(self) -> list[str]:
        """모든 계층 검증."""
        errs: list[str] = []
        if not self.persona_id:
            errs.append("TargetSheet.persona_id 없음")
        errs.extend(self.identity.validate())
        errs.extend(self.grounding.validate())
        errs.extend(self.persona.validate())
        errs.extend(self.visual.validate())
        return errs

    def as_master_sheet(self) -> CharacterMasterSheet:
        """CharacterMasterSheet로 변환(Athena 하위호환).

        visual (L4) 재사용 + identity (L1) + narrow_target (L2) 통합.
        L3 Persona는 visual.wardrobe 등에 간접 영향(직접 저장 0).
        """
        return CharacterMasterSheet(
            persona_id=self.visual.persona_id or self.persona_id,
            identity={**self.identity.to_dict()},
            narrow_target=self.grounding.to_dict(),
            angles=self.visual.angles,
            expressions=self.visual.expressions,
            wardrobe=self.visual.wardrobe
        )

    def to_dict(self) -> dict:
        """JSON 직렬화."""
        return {
            "persona_id": self.persona_id,
            "identity": self.identity.to_dict(),
            "grounding": self.grounding.to_dict(),
            "persona": self.persona.to_dict(),
            "visual": self.visual.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "TargetSheet":
        """JSON 역직렬화."""
        d = d or {}
        return cls(
            persona_id=str(d.get("persona_id") or ""),
            identity=IdentityLayer.from_dict(d.get("identity")),
            grounding=GroundingLayer.from_dict(d.get("grounding")),
            persona=PersonaLayer.from_dict(d.get("persona")),
            visual=CharacterMasterSheet.from_dict(d.get("visual"))
        )

    @classmethod
    def from_master_sheet(cls, ms: CharacterMasterSheet) -> "TargetSheet":
        """CharacterMasterSheet에서 역추출(마이그레이션용).

        identity + narrow_target을 L1, L2로 분해.
        L3 Persona는 기본값(빈 PersonaLayer).
        L4 visual은 CharacterMasterSheet 그대로 재사용.
        """
        identity = IdentityLayer.from_dict(ms.identity or {})
        grounding = GroundingLayer.from_dict(ms.narrow_target or {})
        return cls(
            persona_id=ms.persona_id,
            identity=identity,
            grounding=grounding,
            persona=PersonaLayer(),  # 기본값
            visual=ms
        )


# ── 빌더는 Parzifal 소유 (founder 2026-07-07): contracts=순수 타입. ──
# 4층 조립(identity/grounding/persona 추출 + build_target_sheet + consolidate_target)은
# hiob_parzifal.consolidate 로 이관. 'Janus·Ares 타겟근거를 Parzifal로 독립' = 로직도 Parzifal.
