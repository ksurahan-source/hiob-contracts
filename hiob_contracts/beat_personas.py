"""BeatPersonas — Ares→Athena seam 계약 (2026-07-05, 재감사 v2 수리).

노드맵 재감사: Ares→Athena 실 데이터는 계약 없는 `beat_personas: list[dict[str,Any]]`로
흘렀다(타입 붕괴점). 이 계약은 그 payload를 정형화한다 — Ares 코드는 손대지 않고(그 산출을
read-only로 받아), Athena 소비 경계에서 타입·검증을 강제한다(founder: 소비측 배선·산출 read-only).

grounding: apps/modal/workers/visual.py 실측 필드 —
  persona_id/id, render_mode, emotion, scene_type, social_proof_style,
  gender, role, body, image, wardrobe, setting, locks_accessories,
  voice_persona, face_lock_id.
각 비트는 beat_index 결박(전 다운스트림 정렬 앵커) — BeatPlan.beats와 1:1.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

# render_mode 정규 어휘(관대 — 미지값도 보존하되 정규 별칭 매핑). visual.py 분기 기준.
RENDER_MODES = ("still", "video", "avatar", "carousel", "social_proof")
_RENDER_ALIASES = {
    "image": "still", "photo": "still", "still": "still",
    "video": "video", "motion": "video", "clip": "video",
    "avatar": "avatar", "kling": "avatar", "lipsync": "avatar",
    "carousel": "carousel",
    "social_proof": "social_proof", "socialproof": "social_proof", "proof": "social_proof",
}


def _s(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


@dataclass(frozen=True)
class BeatPersona:
    """단일 비트의 인물·연출 메타 (Ares 산출 → Athena 소비). beat_index=결박 앵커(필수)."""
    beat_index: int
    persona_id: Optional[str] = None
    render_mode: Optional[str] = None            # still|video|avatar|carousel|social_proof
    emotion: Optional[str] = None                # 六道 감정 → 비주얼 무드
    scene_type: Optional[str] = None
    social_proof_style: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    body: Optional[str] = None
    image: Optional[str] = None                  # 히어로컷 참조/이미지 힌트
    wardrobe: Optional[str] = None
    setting: Optional[str] = None
    face_lock_id: Optional[str] = None
    voice_persona: Optional[str] = None
    locks_accessories: tuple[str, ...] = ()

    @property
    def is_social_proof(self) -> bool:
        rm = (self.render_mode or "").lower()
        return rm == "social_proof" or bool(self.social_proof_style)

    def normalized_render_mode(self) -> Optional[str]:
        """render_mode를 정규 어휘로(미지값은 원문 보존)."""
        if not self.render_mode:
            return None
        return _RENDER_ALIASES.get(self.render_mode.strip().lower(), self.render_mode.strip().lower())

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.beat_index is None:
            errs.append("beat_index 없음 (Athena 정렬 결박 필수)")
        elif not isinstance(self.beat_index, int):
            errs.append(f"beat_index 정수 아님: {self.beat_index!r}")
        return errs

    @classmethod
    def from_dict(cls, d: Optional[dict], *, beat_index: Optional[int] = None) -> "BeatPersona":
        d = d or {}
        acc = d.get("locks_accessories") or ()
        if isinstance(acc, (str, bytes)):
            acc = (acc,)
        bi = d.get("beat_index")
        if bi is None:
            bi = beat_index
        return cls(
            beat_index=int(bi) if bi is not None else None,  # type: ignore[arg-type]
            persona_id=_s(d.get("persona_id") or d.get("id")),
            render_mode=_s(d.get("render_mode")),
            emotion=_s(d.get("emotion") or d.get("realm") or d.get("six_realm")),
            scene_type=_s(d.get("scene_type")),
            social_proof_style=_s(d.get("social_proof_style")),
            gender=_s(d.get("gender")),
            role=_s(d.get("role")),
            body=_s(d.get("body")),
            image=_s(d.get("image")),
            wardrobe=_s(d.get("wardrobe")),
            setting=_s(d.get("setting")),
            face_lock_id=_s(d.get("face_lock_id") or d.get("voice_face_lock")),
            voice_persona=_s(d.get("voice_persona")),
            locks_accessories=tuple(x for x in (_s(a) for a in acc) if x),
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items()}


@dataclass(frozen=True)
class BeatPersonas:
    """비트별 인물·연출 시퀀스. BeatPlan.beats와 beat_index로 1:1 정렬."""
    personas: tuple[BeatPersona, ...] = ()

    def __len__(self) -> int:
        return len(self.personas)

    def __iter__(self):
        return iter(self.personas)

    def by_beat(self, beat_index: int) -> Optional[BeatPersona]:
        for p in self.personas:
            if p.beat_index == beat_index:
                return p
        return None

    def validate(self) -> list[str]:
        errs: list[str] = []
        for p in self.personas:
            errs.extend(p.validate())
        idxs = [p.beat_index for p in self.personas if p.beat_index is not None]
        if len(idxs) != len(set(idxs)):
            errs.append("beat_index 중복 (persona 정렬 붕괴)")
        return errs

    @classmethod
    def from_list(cls, items: Optional[list]) -> "BeatPersonas":
        """Ares 산출 beat_personas(list[dict]) → 타입 시퀀스. 인덱스=beat_index 폴백."""
        out: list[BeatPersona] = []
        for i, d in enumerate(items or []):
            if isinstance(d, BeatPersona):
                out.append(d)
            elif isinstance(d, dict):
                out.append(BeatPersona.from_dict(d, beat_index=i))
        return cls(personas=tuple(out))

    def to_list(self) -> list[dict]:
        return [p.to_dict() for p in self.personas]
