"""ShotList — Athena director.plan 산출 (PRD_BIG_FOOTSTEP §4 Athena director node).

비트별 타입 지정 샷 — render_mode, camera_move, duration, continuity 등 모든 렌더 방향을
beat_index로 결박해 Athena.visual.plan이 downstream 계산 0으로 소비 가능하게 한다.

producer: Athena director.plan (SOLE producer)
consumer: Athena visual.plan (render_mode/camera/duration 선택 시 ShotList.shot_for_beat 참조)

Immutable: 모든 필드는 beat_index, beat_character(emotion/narrative role),
render_mode(still|video|avatar|carousel), camera_move(정규 명칭), duration_ms,
continuity_cue(이전 샷과의 시각적 계속성), social_proof_style 등으로 구성.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Literal


ShotKind = Literal["still", "video", "avatar", "carousel", "social_proof"]
CameraMove = Literal[
    "static", "pan_right", "pan_left", "whip_pan_right", "whip_pan_left",
    "tilt_up", "tilt_down", "slow_zoom_in", "slow_zoom_out", "fast_zoom_in", "fast_zoom_out",
    "crash_zoom_in", "crash_zoom_out", "dolly_in", "dolly_out", "tracking", "follow",
    "reverse_tracking", "side_tracking", "low_tracking", "chase",
    "truck_right", "truck_left", "pedestal_up", "pedestal_down",
    "slider_right", "slider_left", "arc_right", "arc_left", "orbit_cw", "orbit_ccw",
    "handheld", "snorricam", "crane_up", "crane_down", "drone_push_in", "drone_pull_back",
]

ShotSize = Literal["ecu", "cu", "mcu", "ms", "wide", "insert"]
ShotAngle = Literal["eye", "low", "high", "three_quarter", "over_shoulder"]
ShotLens = Literal["35", "50", "85", "macro"]
ShotLighting = Literal["soft", "rembrandt", "rim", "golden", "split", "clinical"]
ShotComposition = Literal["thirds", "center", "negative", "layered"]


@dataclass(frozen=True)
class ShotMetadata:
    """단일 비트의 촬영 메타 — 렌더링 방향을 beat_index로 결박."""
    beat_index: int
    beat_character: Optional[str] = None  # hook|problem|pain|product|demo|relief|activity|social_proof|cta
    emotion: Optional[str] = None         # 六道 감정 → 무드 오버라이드
    render_mode: Optional[str] = None     # still|video|avatar|carousel|social_proof
    kind: Optional[ShotKind] = None       # 정규 kind (visual.plan이 처리)

    # Cinematic grammar (직교 축 — 인물락과 무관하게 변주)
    shot_size: Optional[ShotSize] = None  # ecu|cu|mcu|ms|wide|insert
    angle: Optional[ShotAngle] = None     # eye|low|high|three_quarter|over_shoulder
    lens: Optional[ShotLens] = None       # 35|50|85|macro
    lighting: Optional[ShotLighting] = None  # soft|rembrandt|rim|golden|split|clinical
    composition: Optional[ShotComposition] = None  # thirds|center|negative|layered

    # Movement (Seedance/Kling i2v 입력)
    camera_move: Optional[CameraMove] = None  # static|pan_right|dolly_in|... (정규화 필수)
    camera_clause: Optional[str] = None   # 풀 i2v 카메라 명령어 (camera_moves.py에서 파생)

    # Continuity (이전 샷과의 시각적 연결)
    continuity_cue: Optional[str] = None  # "same_subject_from_left" 등 (시각적 설명)

    # Duration (이 샷이 얼마나 오래 화면에 있나)
    duration_ms: Optional[int] = None     # 비트 본 기간 + 서브비트 합산

    # Social proof 특화
    social_proof_style: Optional[str] = None

    # 정책 제약
    policy_flags: tuple[str, ...] = ()    # child_reel_safe|vegan_only|... 렌더 전제 조건


@dataclass(frozen=True)
class ShotList:
    """비트별 타입 샷 시퀀스 — BeatPlan과 beat_index로 1:1 정렬.

    Athena director.plan의 유일한 산출. 모든 downstream이 여기서 render_mode/camera/duration을 읽는다.
    """
    shots: tuple[ShotMetadata, ...] = ()

    def __len__(self) -> int:
        return len(self.shots)

    def __iter__(self):
        return iter(self.shots)

    def shot_for_beat(self, beat_index: int) -> Optional[ShotMetadata]:
        """beat_index에 해당하는 샷 조회."""
        for shot in self.shots:
            if shot.beat_index == beat_index:
                return shot
        return None

    def validate(self) -> list[str]:
        """완정성 검증."""
        errs: list[str] = []
        for shot in self.shots:
            if shot.beat_index is None:
                errs.append("shot.beat_index 없음 (정렬 결박 필수)")
            elif not isinstance(shot.beat_index, int):
                errs.append(f"shot.beat_index 정수 아님: {shot.beat_index!r}")

        idxs = [s.beat_index for s in self.shots if s.beat_index is not None]
        if len(idxs) != len(set(idxs)):
            errs.append("beat_index 중복 (정렬 붕괴)")

        return errs

    @classmethod
    def from_list(cls, shots_list: Optional[list]) -> "ShotList":
        """list[dict] → ShotList 구성."""
        out: list[ShotMetadata] = []
        for d in (shots_list or []):
            if isinstance(d, ShotMetadata):
                out.append(d)
            elif isinstance(d, dict):
                out.append(ShotMetadata(
                    beat_index=int(d.get("beat_index") or 0),
                    beat_character=d.get("beat_character"),
                    emotion=d.get("emotion"),
                    render_mode=d.get("render_mode"),
                    kind=d.get("kind"),
                    shot_size=d.get("shot_size"),
                    angle=d.get("angle"),
                    lens=d.get("lens"),
                    lighting=d.get("lighting"),
                    composition=d.get("composition"),
                    camera_move=d.get("camera_move"),
                    camera_clause=d.get("camera_clause"),
                    continuity_cue=d.get("continuity_cue"),
                    duration_ms=d.get("duration_ms"),
                    social_proof_style=d.get("social_proof_style"),
                    policy_flags=tuple(d.get("policy_flags") or []),
                ))
        return cls(shots=tuple(out))

    def to_dict(self) -> dict:
        return {
            "shots": [asdict(s) for s in self.shots],
        }
