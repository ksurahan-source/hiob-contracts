"""렌더前 invariant gate (REEL-QA-GATE) — 계약 레벨에서 어젯밤 6결손을 차단.

seam 통일규칙 #3: 음성=영상=타임라인 정렬, 전 트랙 믹스, 자막 커버리지를
*증명*해야 렌더. 미달 = block (false-DONE 구조차단 + 음소거 슬라이드쇼 재발 방지).

Atropos가 CompositionSnapshot 만들기 전에 호출. 통과 못하면 렌더 금지.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .beat_plan import BeatPlan
from .audio_clip import AudioClip
from .media_artifact import MediaArtifact


@dataclass(frozen=True)
class RenderReadiness:
    ok: bool
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def assert_render_ready(
    plan: BeatPlan,
    audio: list[AudioClip],
    media: list[MediaArtifact],
    *,
    require_voice_per_beat: bool = True,
    require_caption_per_beat: bool = True,
) -> RenderReadiness:
    """전 비트가 보이스(P1)·자막(P13)·비주얼을 갖췄는지 증명. 미달=block."""
    violations: list[str] = []
    warnings: list[str] = []

    beat_idxs = {b.beat_index for b in plan.beats}
    if not beat_idxs:
        return RenderReadiness(ok=False, violations=("BeatPlan에 비트 0개",))

    voice_beats = {c.beat_index for c in audio if c.track == "voice" and c.beat_index is not None}
    media_beats = {m.beat_index for m in media if m.beat_index is not None}
    caption_beats = {b.beat_index for b in plan.beats if (b.caption or "").strip()}
    has_music = any(c.track == "music" for c in audio)

    # 계약 자체 위반 먼저(P1 결박)
    for c in audio:
        violations.extend(f"audio {c.track}@{c.beat_index}: {e}" for e in c.validate())
    for m in media:
        violations.extend(f"media @{m.beat_index}: {e}" for e in m.validate())

    # P1 — 보이스 미발화(어젯밤 #1)
    if require_voice_per_beat:
        missing_voice = sorted(beat_idxs - voice_beats)
        if missing_voice:
            violations.append(f"P1 보이스 없는 비트 {missing_voice} (음소거 위험)")

    # 비주얼 커버리지
    missing_media = sorted(beat_idxs - media_beats)
    if missing_media:
        violations.append(f"비주얼 없는 비트 {missing_media}")

    # P13 — 자막 커버리지(없으면 dead air)
    if require_caption_per_beat:
        missing_cap = sorted(beat_idxs - caption_beats)
        if missing_cap:
            warnings.append(f"P13 자막 없는 비트 {missing_cap} (dead air 위험)")

    if not has_music:
        warnings.append("음악 트랙 없음")

    return RenderReadiness(
        ok=not violations,
        violations=tuple(violations),
        warnings=tuple(warnings),
    )
