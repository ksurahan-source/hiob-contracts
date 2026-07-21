"""BeatPlan — 대본 계약 (Ares). 대본이 지휘자: 각 비트가 다운스트림(보이스/
비주얼/자막/효과음)이 소비할 필드를 *모두* 선언한다.

grounding: beat dict 키 = beat_index, text, duration_ms, caption, voice_concept,
sfx(cue), role, emotion, cta, direction/scene_direction. 부재=폴백.

scene_direction (H0): Ares BeatDirection prose — {shot, subject, setting, overlay}.
Athena frame_plan prompt 합성의 SCENE SSOT. ShotMetadata.direction (FrameDirection)
과 이름 충돌을 피하기 위해 필드명은 scene_direction.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

_SCENE_KEYS = ("shot", "subject", "setting", "overlay")
_SCENE_CAPS = {"shot": 300, "subject": 500, "setting": 300, "overlay": 200}


def normalize_scene_direction(raw: Any) -> Optional[dict[str, str]]:
    """Ares direction / scene_direction dict → capped {shot,subject,setting,overlay}.

    None/empty → None. Non-dict ignored. Values coerced to stripped strings with
    production_sheet-compatible hard caps.
    """
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for key in _SCENE_KEYS:
        val = str(raw.get(key) or "").strip()
        if not val:
            continue
        out[key] = val[: _SCENE_CAPS[key]]
    return out or None


@dataclass(frozen=True)
class Beat:
    """단일 비트. beat_index는 전 다운스트림 결박의 앵커(필수)."""
    beat_index: int
    text: str = ""                              # 발화/나레이션 라인
    emotion: Optional[str] = None               # 六道 감정 → voice/visual 선택
    shot_type: Optional[str] = None
    voice_concept: Optional[str] = None         # Orpheus 보이스 선택 입력
    sfx_cue: Optional[str] = None               # Apollo SFX 입력
    caption: Optional[str] = None               # 자막 텍스트(전 비트 권장)
    role: Optional[str] = None                  # 영웅/가이드/목격자
    duration_ms: Optional[int] = None
    beat_duration_ms: Optional[int] = None      # Per-beat grid duration (decouple from _BEAT_MS=1000)
    cta: Optional[dict] = None                  # CTA 비트 = 가치수학 4단
    # Ares visual prose (shot/subject/setting/overlay). Not FrameDirection.
    scene_direction: Optional[dict] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Beat":
        # Prefer explicit scene_direction; accept legacy Ares key "direction".
        scene = normalize_scene_direction(
            d.get("scene_direction") if d.get("scene_direction") is not None
            else d.get("direction")
        )
        # shot_type: top-level only — do not steal direction.shot prose
        shot_type = d.get("shot_type")
        if shot_type is None and not isinstance(d.get("direction"), dict):
            shot_type = d.get("shot")
        return cls(
            beat_index=int(d["beat_index"]),
            text=d.get("text") or d.get("line") or d.get("narration") or "",
            emotion=d.get("emotion") or d.get("realm") or d.get("six_realm"),
            shot_type=shot_type,
            voice_concept=d.get("voice_concept"),
            sfx_cue=d.get("sfx_cue") or d.get("sfx"),
            caption=d.get("caption"),
            role=d.get("role"),
            duration_ms=d.get("duration_ms"),
            beat_duration_ms=d.get("beat_duration_ms"),
            cta=d.get("cta") if isinstance(d.get("cta"), dict) else None,
            scene_direction=scene,
        )

    def to_dict(self) -> dict:
        """Emit both scene_direction and direction for Star/Ares compatibility."""
        d = asdict(self)
        scene = d.get("scene_direction")
        if isinstance(scene, dict) and scene:
            d["direction"] = dict(scene)
        return d


@dataclass(frozen=True)
class BeatPlan:
    """비트 시퀀스. 척추 = 단일 카테고리 재프레임이 훅~CTA 관통."""
    beats: tuple[Beat, ...] = ()
    spine: Optional[str] = None                 # 관통 재프레임 한 줄

    def validate(self) -> list[str]:
        errs: list[str] = []
        idxs = [b.beat_index for b in self.beats]
        if len(idxs) != len(set(idxs)):
            errs.append("beat_index 중복")
        if idxs and sorted(idxs) != list(range(min(idxs), max(idxs) + 1)):
            errs.append("beat_index 연속성 깨짐(구멍)")
        return errs

    def beat_for(self, beat_index: int) -> Optional[Beat]:
        for b in self.beats:
            if b.beat_index == beat_index:
                return b
        return None

    @classmethod
    def from_list(cls, beats: list[dict], spine: Optional[str] = None) -> "BeatPlan":
        return cls(beats=tuple(Beat.from_dict(b) for b in (beats or [])), spine=spine)

    def to_dict(self) -> dict:
        return {"spine": self.spine, "beats": [b.to_dict() for b in self.beats]}
