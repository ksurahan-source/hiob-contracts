"""행성 입력/출력 envelope 계약 — 정형화 ✳신규분.

10행성 I/O 감사(wf_70c35104)에서 "신규 필요"로 판정된 입력 봉투 + Hephaestus 응답.
이로써 9행성 전부 In·Out 타입 계약이 코드에 존재한다 (계약층 정형화 완성).
런타임 행성이 이 타입을 받도록 마이그레이션하는 것은 어댑터 점진 작업
(`infra/polyrepo/PLANET_IO_CONTRACTS.md` §3).

규칙: 전부 frozen(불변) · DB 클라이언트(sb) 인자 금지(DSL 순수성) · 상류 계약 합성.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .beat_plan import BeatPlan
from .media_artifact import MediaArtifact
from .audio_clip import AudioClip
from .beat_personas import BeatPersonas


# ── Athena 입력 컨텍스트 (BeatPlan과 함께) ──
@dataclass(frozen=True)
class VisualContext:
    """Athena가 run_id로 DB서 끌어오던 시각 컨텍스트의 정형화."""
    visual_style: str = ""
    ethnicity: str = ""
    listing_environment_lock: str = ""
    vertical_style_lock: str = ""
    axis_gaze_lock: str = ""
    product_present: bool = False


@dataclass(frozen=True)
class VisualRequest:
    """Athena 노드 입력 = BeatPlan + VisualContext + (Ares→Athena seam) BeatPersonas·element_locks.

    beat_personas = Ares 산출 인물·연출 메타(비트별) 정형화. element_locks = D-56 승인 도면
    (status=approved만 소비). 둘 다 부재 허용(byte-identical 폴백) — 기존 소비자 무영향.
    """
    beat_plan: BeatPlan
    context: VisualContext = field(default_factory=VisualContext)
    beat_personas: BeatPersonas = field(default_factory=BeatPersonas)
    element_locks: dict = field(default_factory=dict)


# ── Orpheus 입력 (보이스/음악) — 순수 데이터(DB 0) ──
@dataclass(frozen=True)
class AudioRequest:
    """Orpheus 노드 입력. voice는 beat_index 결박(P1), music은 run-level."""
    # voice
    voice_persona: str = ""
    voice_concept: str = ""
    source_text: str = ""
    beat_index: int | None = None
    # music
    music_vibe: str = ""
    music_bpm: int = 0
    music_pool: tuple[dict, ...] = ()  # [{storage_key, url, name, tags, duration_ms}, ...]
    target_ms: int = 0


# ── Apollo 입력 (SFX) ──
@dataclass(frozen=True)
class SFXRequest:
    """Apollo 노드 입력 — 순수 데이터(DB 0).

    cues: [{beat_index, text, duration_ms}, ...] (비트별 효과음 요청)
    asset_pool: [{storage_key, url, name, tags}, ...] (후보 효과음 자산)
    """
    cues: tuple[dict, ...] = ()
    asset_pool: tuple[dict, ...] = ()


# ── Hephaestus 입출력 (렌더 — 패키지 부재, 계약이 순수 노드 transform을 보유) ──
@dataclass(frozen=True)
class RenderJobRequest:
    """Hephaestus 노드 입력. approved_final_render = 게이트."""
    render_job_id: str
    run_id: str
    composition: str = "timelineV2"
    mode: str = "final"
    approved_final_render: bool = False
    modifications: dict = field(default_factory=dict)

    def to_dispatch(self) -> dict:
        """순수 노드 — 렌더러(Lambda) dispatch 페이로드. final 모드는 승인 게이트 강제."""
        return {
            "renderJobId": self.render_job_id,
            "runId": self.run_id,
            "composition": self.composition,
            "mode": self.mode,
            "approvedFinalRender": bool(self.approved_final_render),
            "modifications": dict(self.modifications),
            "gated": self.mode == "final" and not self.approved_final_render,
        }


@dataclass(frozen=True)
class RenderJobResponse:
    """Hephaestus 노드 출력. output_url = 최종 MP4."""
    render_job_id: str
    snapshot_id: str
    render_status: str
    output_url: str | None = None
    duration_s: float | None = None
    error: dict | None = None

    @classmethod
    def from_render_result(cls, render_job_id: str, result: dict) -> "RenderJobResponse":
        """순수 노드 — 렌더러 응답 dict → 타입 RenderJobResponse."""
        r = result or {}
        ok = bool(r.get("success") or r.get("output_url") or r.get("outputUrl"))
        return cls(
            render_job_id=render_job_id,
            snapshot_id=str(r.get("snapshotId") or r.get("snapshot_id") or ""),
            render_status=str(r.get("status") or ("completed" if ok else "failed")),
            output_url=r.get("output_url") or r.get("outputUrl"),
            duration_s=r.get("duration_s") or r.get("durationS"),
            error=None if ok else ({"reason": r.get("error")} if r.get("error") else None),
        )


# ── Metis 입력 (측정 — 출력은 기존 ReelMetric/FeedbackSignal) ──
@dataclass(frozen=True)
class ProcessInsightsRequest:
    """Metis 노드 입력. sb 인자 없음 = DSL 순수성 (DB fetch는 셸로)."""
    raw_insights: tuple[dict, ...] = ()
    run_brand_map: dict = field(default_factory=dict)
    window_days: int = 30


__all__ = [
    "VisualContext", "VisualRequest",
    "AudioRequest", "SFXRequest",
    "RenderJobRequest", "RenderJobResponse",
    "ProcessInsightsRequest",
    "BeatPersona", "BeatPersonas",
]

# re-export seam contract for convenience (VisualRequest 합성 요소)
from .beat_personas import BeatPersona  # noqa: E402
