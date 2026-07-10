"""TargetSheet — Parzifal 타겟생성 단일권위자 (2026-07-07).

4층 고분해능 계약 + Element Locks 브릿지 (Athena) + TargetProfile 카드 (Studio UX).

Parzifal에서 CharacterMasterSheet를 분해하는 4층 구조.
Janus(L1+L2 facts)·Ares(L3 protagonist)·Athena(L4 visual)·Studio(TargetProfile card) 흐름 명시화.

4층 설계:
- L1 Identity (Soul): 고정된 기본정체성(name, age, gender, region, background, language, confidence)
- L2 Grounding (Motivation): 동기·배경 설정(pain_points, blocker, jtbd, activity_context, interest, children, demographics, voc_evidence)
- L3 Persona (Speak): 인물상·발화방식(protagonist_role, voice_persona, voice_concept, speaking_style, narrative_arc, gaze_mode, ...)
- L4 Visual (Element+Cinema): 시각 요소(CharacterMasterSheet 재사용: angles[]·expressions[]·wardrobe)

데이터흐름:
- L1+L2: Janus NarrowPersona → identity_from_narrow(), narrow_settings()로 추출(변경 0)
- L3: Ares protagonist_axis resolved + Character → persona_to_L3() 맵 (계산 0)
- L4: Parzifal SheetPanel[] + wardrobe → CharacterMasterSheet 래핑
- Athena: TargetSheet.element_locks_profile() → ElementLocksProfile → parzifal_adapter 소비
- Studio: TargetSheet.as_target_profile() → TargetProfile 카드 (vivid persona + sources)

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
        # gender_axis는 IdentityLayer 필드가 아니다(L3 PersonaLayer 소속) — 잘못 전달돼
        # from_dict가 TypeError로 즉사하던 좀비 계약 (2026-07-11 QA 전수에서 발견·제거).
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
class ElementLocksProfile:
    """Athena 전용 Element Locks 브릿지 — L3 Persona + L4 Visual 필드로 구성.

    TargetSheet에서 parzifal_adapter.element_locks_from_parzifal()가 소비.
    Athena가 beat_personas 직접 의존성 제거, TargetSheet 단일 진실로 통합.

    필드:
    - persona_id: 고유 ID (L1 Identity)
    - gender_axis: female_led | hero | neutral (L3 Persona)
    - gaze_mode: female_gaze | neutral (L3 Persona)
    - voice_persona: male1-3 | female1-3 (L3 Persona voice lane lock)
    - protagonist_role: narrator | hero | heroine | opponent (L3 Persona)
    - angles: [SheetPanel] (L4 Visual)
    - expressions: [SheetPanel] (L4 Visual)
    - wardrobe: [dict] (L4 Visual)
    - narrative_context: str (L3 Persona narrative_arc + backstory merged for element decision)
    """

    persona_id: str = ""
    gender_axis: str = ""             # female_led | hero | neutral
    gaze_mode: str = ""               # female_gaze | neutral
    voice_persona: str = ""           # male1-3 | female1-3
    protagonist_role: str = ""        # narrator | hero | heroine | opponent
    narrative_context: str = ""       # narrative_arc + backstory (element selection driver)
    angles: list = field(default_factory=list)  # [SheetPanel]
    expressions: list = field(default_factory=list)  # [SheetPanel]
    wardrobe: list = field(default_factory=list)  # [dict]

    def validate(self) -> list[str]:
        """ElementLocksProfile 계약 검증 — gender_axis, gaze_mode, protagonist_role vocab."""
        errs: list[str] = []
        if self.protagonist_role and self.protagonist_role not in ("narrator", "hero", "heroine", "opponent"):
            errs.append(f"ElementLocksProfile.protagonist_role 미지원: {self.protagonist_role}")
        if self.gender_axis and self.gender_axis not in ("female_led", "hero", "neutral"):
            errs.append(f"ElementLocksProfile.gender_axis 미지원: {self.gender_axis}")
        if self.gaze_mode and self.gaze_mode not in ("female_gaze", "neutral"):
            errs.append(f"ElementLocksProfile.gaze_mode 미지원: {self.gaze_mode}")
        return errs

    def to_dict(self) -> dict:
        """JSON 직렬화 (Athena adapter 소비용)."""
        return {
            "persona_id": self.persona_id,
            "gender_axis": self.gender_axis, "gaze_mode": self.gaze_mode,
            "voice_persona": self.voice_persona, "protagonist_role": self.protagonist_role,
            "narrative_context": self.narrative_context,
            "angles": [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.angles],
            "expressions": [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.expressions],
            "wardrobe": self.wardrobe
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ElementLocksProfile":
        """JSON 역직렬화."""
        d = d or {}
        return cls(
            persona_id=str(d.get("persona_id") or ""),
            gender_axis=str(d.get("gender_axis") or ""),
            gaze_mode=str(d.get("gaze_mode") or ""),
            voice_persona=str(d.get("voice_persona") or ""),
            protagonist_role=str(d.get("protagonist_role") or ""),
            narrative_context=str(d.get("narrative_context") or ""),
            angles=d.get("angles") or [],
            expressions=d.get("expressions") or [],
            wardrobe=d.get("wardrobe") or []
        )


@dataclass(frozen=True)
class SourceTag:
    """TargetProfile 카드의 필드 소스 태그 — [설정] | [naver_review] | [catalog] | [설정/invented]."""

    field_name: str = ""              # pain_points | blocker | jtbd | etc
    source_type: str = ""             # naver_review | catalog | invented
    evidence: str = ""                # 직접 인용 또는 설명

    def to_dict(self) -> dict:
        return {"field_name": self.field_name, "source_type": self.source_type, "evidence": self.evidence}

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "SourceTag":
        d = d or {}
        return cls(
            field_name=str(d.get("field_name") or ""),
            source_type=str(d.get("source_type") or ""),
            evidence=str(d.get("evidence") or "")
        )


@dataclass(frozen=True)
class TargetProfile:
    """Studio UX용 생생한 타겟 카드 — Parzifal TargetProfile 산출물.

    BrandUnderstanding 화면에서 유저가 브랜드 이해한 타겟을 시각적으로 보기.
    TargetSheet 4층을 압축 + 출처 태그 추가하여 신뢰성 신호 전달.

    필드:
    - persona_id: 고유 ID
    - name: "정수진" (L1 Identity.name)
    - age: 36 (L1 Identity.age)
    - age_band: "30-40" (L1 Identity.age_band)
    - gender: "female" (L1 Identity.gender)
    - region: "서울" (L1 Identity.region)
    - profile_image_placeholder: str (placeholder URI for avatar thumbnail)
    - pain_points: str (L2 Grounding.pain_points + source)
    - blocker: str (L2 Grounding.blocker + source)
    - jtbd: str (L2 Grounding.jtbd + source, 진정한 욕구)
    - narrative_arc: str (L3 Persona.narrative_arc, "여성주연 호영" 등)
    - voice_persona: str (L3 Persona.voice_persona, 성별·배우 lane)
    - speaking_style: str (L3 Persona.speaking_style)
    - source_tags: [SourceTag] (각 필드의 출처)
    - approval_status: str (ear_test_pending | approved)
    """

    persona_id: str = ""
    name: str = ""
    age: Optional[int] = None
    age_band: str = ""
    gender: str = ""                  # female | male | neutral
    region: str = ""
    profile_image_placeholder: str = ""  # e.g. "avatar/female/36-40/cute"

    pain_points: str = ""
    blocker: str = ""
    jtbd: str = ""

    narrative_arc: str = ""
    voice_persona: str = ""
    speaking_style: str = ""
    gender_axis: str = ""  # additive(2026-07-08): ares protagonist_axis 어댑터 소비 — female_led/male_led

    source_tags: list = field(default_factory=list)  # [SourceTag]
    approval_status: str = "approved"  # ear_test_pending | approved

    def vivid_summary(self) -> str:
        """카드 텍스트 표현 (Studio UI용).

        예: "정수진, 36세, 서울 / 수영 강습 8개월 / 수경이 뿌예져서 진도를 못 따라감 / 안전하고 자극 없이 수영을 즐기고 싶다"
        """
        parts = []
        if self.name:
            parts.append(f"{self.name}, {self.age}세" if self.age else f"{self.name}, {self.age_band}")
        if self.region:
            parts.append(self.region)

        summary = " / ".join(parts) if parts else ""

        if self.pain_points:
            summary = (summary + " / " if summary else "") + self.pain_points
        if self.blocker:
            summary += f" ({self.blocker})"
        if self.jtbd:
            summary += f" → {self.jtbd}"

        return summary

    def to_dict(self) -> dict:
        """JSON 직렬화."""
        return {
            "persona_id": self.persona_id,
            "name": self.name, "age": self.age, "age_band": self.age_band,
            "gender": self.gender, "region": self.region,
            "profile_image_placeholder": self.profile_image_placeholder,
            "pain_points": self.pain_points, "blocker": self.blocker, "jtbd": self.jtbd,
            "narrative_arc": self.narrative_arc, "voice_persona": self.voice_persona,
            "speaking_style": self.speaking_style,
            "gender_axis": self.gender_axis,
            "source_tags": [st.to_dict() for st in self.source_tags],
            "approval_status": self.approval_status
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "TargetProfile":
        """JSON 역직렬화."""
        d = d or {}
        return cls(
            persona_id=str(d.get("persona_id") or ""),
            name=str(d.get("name") or ""), age=int(d["age"]) if d.get("age") is not None else None,
            age_band=str(d.get("age_band") or ""),
            gender=str(d.get("gender") or ""), region=str(d.get("region") or ""),
            profile_image_placeholder=str(d.get("profile_image_placeholder") or ""),
            pain_points=str(d.get("pain_points") or ""),
            blocker=str(d.get("blocker") or ""),
            jtbd=str(d.get("jtbd") or ""),
            narrative_arc=str(d.get("narrative_arc") or ""),
            voice_persona=str(d.get("voice_persona") or ""),
            speaking_style=str(d.get("speaking_style") or ""),
            source_tags=[SourceTag.from_dict(st) for st in (d.get("source_tags") or [])],
            approval_status=str(d.get("approval_status") or "approved")
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

    def element_locks_profile(self) -> ElementLocksProfile:
        """Athena Element Locks 브릿지 생성 (L3 Persona + L4 Visual).

        parzifal_adapter.element_locks_from_parzifal() 소비.
        beat_personas 직접 의존성 제거, TargetSheet 단일 진실 확립.

        narrative_context = L3 Persona.narrative_arc + backstory 병합
        (element_lock_consumer.py가 visual element 선택 시 참조)
        """
        narrative_parts = []
        if self.persona.narrative_arc:
            narrative_parts.append(self.persona.narrative_arc)
        if self.persona.backstory:
            narrative_parts.append(self.persona.backstory)

        return ElementLocksProfile(
            persona_id=self.persona_id,
            gender_axis=self.persona.gender_axis,
            gaze_mode=self.persona.gaze_mode,
            voice_persona=self.persona.voice_persona,
            protagonist_role=self.persona.protagonist_role,
            narrative_context=" → ".join(narrative_parts),
            angles=self.visual.angles,
            expressions=self.visual.expressions,
            wardrobe=self.visual.wardrobe
        )

    def as_target_profile(self) -> TargetProfile:
        """Studio UX용 생생한 TargetProfile 카드 생성.

        BrandUnderstanding에서 brand_understanding.jsx 표시용.
        L1 Identity + L2 Grounding (sources) + L3 Persona + 플레이스홀더 이미지.

        TargetProfile은 승인 상태(identity.confidence)를 반영하며,
        source_tags는 L2 Grounding 각 필드의 출처 기록.
        """
        source_tags_list = []

        # L2 Grounding 출처 태그 생성
        if self.grounding.pain_points:
            source_tags_list.append(SourceTag(
                field_name="pain_points",
                source_type=self.grounding.pain_points_source or "invented",
                evidence=self.grounding.pain_points
            ))

        if self.grounding.blocker:
            source_tags_list.append(SourceTag(
                field_name="blocker",
                source_type=self.grounding.blocker_source or "invented",
                evidence=self.grounding.blocker
            ))

        if self.grounding.jtbd:
            source_tags_list.append(SourceTag(
                field_name="jtbd",
                source_type=self.grounding.jtbd_source or "invented",
                evidence=self.grounding.jtbd
            ))

        # 프로필 이미지 플레이스홀더 경로 생성
        # 예: "avatar/female/30-40/cute" (gender + age_band + style)
        gender_folder = self.identity.gender or "neutral"
        age_folder = self.identity.age_band or "unknown"
        profile_image_placeholder = f"avatar/{gender_folder}/{age_folder}/cute"

        return TargetProfile(
            persona_id=self.persona_id,
            gender_axis=(self.persona.gender_axis
                         or ("female_led" if "여" in (self.identity.gender or "") else ("male_led" if "남" in (self.identity.gender or "") else ""))),
            name=self.identity.name,
            age=self.identity.age,
            age_band=self.identity.age_band,
            gender=self.identity.gender,
            region=self.identity.region,
            profile_image_placeholder=profile_image_placeholder,
            pain_points=self.grounding.pain_points,
            blocker=self.grounding.blocker,
            jtbd=self.grounding.jtbd,
            narrative_arc=self.persona.narrative_arc,
            voice_persona=self.persona.voice_persona,
            speaking_style=self.persona.speaking_style,
            source_tags=source_tags_list,
            approval_status=self.identity.confidence
        )

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


# ── 빌더는 Parzifal 소유 (founder 2026-07-07): contracts=순수 타입 + 헬퍼. ──
# 4층 조립(identity/grounding/persona 추출 + build_target_sheet + consolidate_target)은
# hiob_parzifal.consolidate 로 이관. 'Janus·Ares 타겟근거를 Parzifal로 독립' = 로직도 Parzifal.

# ── 헬퍼 함수 ──


def identity_from_janus_narrow(narrow_target: Optional[dict]) -> IdentityLayer:
    """Janus NarrowPersona → L1 Identity 추출 (검증 없이 매핑만).

    narrow_target = {
        "profile_name": "정수진",
        "age": 36,
        "age_band": "30-40",
        "gender": "female",
        "region": "서울",
        "background": "직장인",
        ...
    }

    변경 0, 순수 함수.
    """
    narrow_target = narrow_target or {}
    return IdentityLayer(
        id=str(narrow_target.get("persona_id") or narrow_target.get("id") or ""),
        name=str(narrow_target.get("profile_name") or narrow_target.get("name") or ""),
        age=int(narrow_target["age"]) if narrow_target.get("age") is not None else None,
        age_band=str(narrow_target.get("age_band") or ""),
        gender=str(narrow_target.get("gender") or ""),
        region=str(narrow_target.get("region") or ""),
        background=str(narrow_target.get("background") or ""),
        language=str(narrow_target.get("language") or "ko"),
        confidence=str(narrow_target.get("confidence") or "approved")
    )


def grounding_from_janus_narrow(narrow_target: Optional[dict]) -> GroundingLayer:
    """Janus NarrowPersona → L2 Grounding 추출 (pain_points, blocker, jtbd + sources).

    narrow_target에서 grounding 필드 직접 매핑.
    source 필드 (pain_points_source 등)도 함께 처리.

    변경 0, 순수 함수.
    """
    narrow_target = narrow_target or {}
    return GroundingLayer(
        pain_points=str(narrow_target.get("pain_points") or ""),
        pain_points_source=str(narrow_target.get("pain_points_source") or ""),
        blocker=str(narrow_target.get("blocker") or ""),
        blocker_source=str(narrow_target.get("blocker_source") or ""),
        jtbd=str(narrow_target.get("jtbd") or ""),
        jtbd_source=str(narrow_target.get("jtbd_source") or ""),
        activity_context=str(narrow_target.get("activity_context") or ""),
        interest=str(narrow_target.get("interest") or ""),
        children=str(narrow_target.get("children") or ""),
        demographics=str(narrow_target.get("demographics") or ""),
        voc_evidence=str(narrow_target.get("voc_evidence") or "")
    )


def persona_from_ares_character(
    character_dict: Optional[dict],
    protagonist_gender_axis: Optional[str] = None
) -> PersonaLayer:
    """Ares Character + protagonist_axis 결과 → L3 Persona 추출.

    character_dict = {
        "protagonist_role": "heroine",
        "actor_archetype": "직장인 여성",
        "narrative_arc": "여성주연",
        "voice_persona": "female1",
        "voice_concept": "friendly",
        "speaking_style": "친근",
        "tone_and_manner": "따뜻함",
        "logic_structure": "감정 중심",
        "backstory": "...",
        ...
    }

    protagonist_gender_axis: Brief.protagonist_gender에서 전달 (female_led | hero | neutral).

    변경 0, 순수 함수.
    """
    character_dict = character_dict or {}
    return PersonaLayer(
        protagonist_role=str(character_dict.get("protagonist_role") or ""),
        actor_archetype=str(character_dict.get("actor_archetype") or ""),
        narrative_arc=str(character_dict.get("narrative_arc") or ""),
        voice_persona=str(character_dict.get("voice_persona") or ""),
        voice_concept=str(character_dict.get("voice_concept") or ""),
        speaking_style=str(character_dict.get("speaking_style") or ""),
        logic_structure=str(character_dict.get("logic_structure") or ""),
        tone_and_manner=str(character_dict.get("tone_and_manner") or ""),
        backstory=str(character_dict.get("backstory") or ""),
        gender_axis=str(protagonist_gender_axis or ""),
        gaze_mode=str(character_dict.get("gaze_mode") or "")
    )


def build_target_sheet(
    persona_id: str,
    identity: IdentityLayer,
    grounding: GroundingLayer,
    persona: PersonaLayer,
    visual: Optional[CharacterMasterSheet] = None
) -> TargetSheet:
    """4층 TargetSheet 조립 (순수 조합자).

    Parzifal consolidate.py 또는 target_generator.py에서 호출.
    각 층은 이미 생성된 상태, 조립만 수행.

    변경 0, 입력 4개 결합.
    """
    visual = visual or CharacterMasterSheet()
    return TargetSheet(
        persona_id=persona_id,
        identity=identity,
        grounding=grounding,
        persona=persona,
        visual=visual
    )
