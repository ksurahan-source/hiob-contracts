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

    def validate(self) -> list[str]:
        return []

    def to_dict(self) -> dict:
        return {
            "visual_style": self.visual_style,
            "ethnicity": self.ethnicity,
            "listing_environment_lock": self.listing_environment_lock,
            "vertical_style_lock": self.vertical_style_lock,
            "axis_gaze_lock": self.axis_gaze_lock,
            "product_present": self.product_present,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "VisualContext":
        d = d or {}
        return cls(
            visual_style=str(d.get("visual_style") or ""),
            ethnicity=str(d.get("ethnicity") or ""),
            listing_environment_lock=str(d.get("listing_environment_lock") or ""),
            vertical_style_lock=str(d.get("vertical_style_lock") or ""),
            axis_gaze_lock=str(d.get("axis_gaze_lock") or ""),
            product_present=bool(d.get("product_present", False)),
        )


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

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.beat_plan is None:
            errs.append("VisualRequest.beat_plan 필수")
        elif hasattr(self.beat_plan, "validate"):
            errs.extend(self.beat_plan.validate() or [])
        return errs

    @classmethod
    def from_dict(cls, d: dict | None) -> "VisualRequest":
        d = d or {}
        bp = d.get("beat_plan")
        if isinstance(bp, BeatPlan):
            beat_plan = bp
        elif isinstance(bp, list):
            beat_plan = BeatPlan.from_list(bp)
        elif isinstance(bp, dict):
            beats = bp.get("beats") or []
            beat_plan = BeatPlan.from_list(beats, spine=bp.get("spine"))
        else:
            beat_plan = BeatPlan.from_list([])
        ctx = d.get("context")
        if isinstance(ctx, VisualContext):
            context = ctx
        else:
            context = VisualContext.from_dict(ctx if isinstance(ctx, dict) else {})
        personas = d.get("beat_personas")
        if isinstance(personas, BeatPersonas):
            beat_personas = personas
        elif isinstance(personas, list):
            beat_personas = BeatPersonas.from_list(personas)
        elif isinstance(personas, dict) and "items" in personas:
            beat_personas = BeatPersonas.from_list(personas.get("items") or [])
        else:
            beat_personas = BeatPersonas()
        return cls(
            beat_plan=beat_plan,
            context=context,
            beat_personas=beat_personas,
            element_locks=dict(d.get("element_locks") or {}),
        )


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

    def validate(self) -> list[str]:
        errs: list[str] = []
        has_music = bool(self.music_vibe) or self.target_ms > 0 or bool(self.music_pool)
        has_voice = bool(self.voice_persona or self.voice_concept or self.source_text)
        if not (has_music or has_voice):
            errs.append("AudioRequest: voice 또는 music 필드 최소 1개 필요")
        return errs

    def to_dict(self) -> dict:
        return {
            "voice_persona": self.voice_persona,
            "voice_concept": self.voice_concept,
            "source_text": self.source_text,
            "beat_index": self.beat_index,
            "music_vibe": self.music_vibe,
            "music_bpm": self.music_bpm,
            "music_pool": list(self.music_pool),
            "target_ms": self.target_ms,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "AudioRequest":
        d = d or {}
        pool = d.get("music_pool") or ()
        beat = d.get("beat_index")
        return cls(
            voice_persona=str(d.get("voice_persona") or ""),
            voice_concept=str(d.get("voice_concept") or ""),
            source_text=str(d.get("source_text") or ""),
            beat_index=int(beat) if beat is not None else None,
            music_vibe=str(d.get("music_vibe") or ""),
            music_bpm=int(d.get("music_bpm") or 0),
            music_pool=tuple(pool) if isinstance(pool, (list, tuple)) else (),
            target_ms=int(d.get("target_ms") or 0),
        )


# ── Apollo 입력 (SFX) ──
@dataclass(frozen=True)
class SFXRequest:
    """Apollo 노드 입력 — 순수 데이터(DB 0).

    cues: [{beat_index, text, duration_ms}, ...] (비트별 효과음 요청)
    asset_pool: [{storage_key, url, name, tags}, ...] (후보 효과음 자산)
    shot_list_digest: 선택사항 Athena ShotList 다이제스트 (음정 정렬 시 필수)
    """
    cues: tuple[dict, ...] = ()
    asset_pool: tuple[dict, ...] = ()
    shot_list_digest: str = ""

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not isinstance(self.cues, (list, tuple)):
            errs.append("SFXRequest.cues must be a list/tuple")
            return errs
        for i, cue in enumerate(self.cues):
            if not isinstance(cue, dict):
                errs.append(f"SFXRequest.cues[{i}] must be a dict")
                continue
            if cue.get("beat_index") is None and not (cue.get("text") or cue.get("cue")):
                errs.append(f"SFXRequest.cues[{i}]: beat_index 또는 text/cue 필요")
        return errs

    def to_dict(self) -> dict:
        return {
            "cues": list(self.cues),
            "asset_pool": list(self.asset_pool),
            "shot_list_digest": self.shot_list_digest,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "SFXRequest":
        d = d or {}
        cues = d.get("cues") or ()
        pool = d.get("asset_pool") or ()
        return cls(
            cues=tuple(cues) if isinstance(cues, (list, tuple)) else (),
            asset_pool=tuple(pool) if isinstance(pool, (list, tuple)) else (),
            shot_list_digest=str(d.get("shot_list_digest") or ""),
        )


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

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.render_job_id:
            errs.append("RenderJobRequest.render_job_id 필수")
        if not self.run_id:
            errs.append("RenderJobRequest.run_id 필수")
        if self.mode == "final" and not self.approved_final_render:
            errs.append("RenderJobRequest: mode=final 이면 approved_final_render 필수")
        return errs

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

    def to_dict(self) -> dict:
        return {
            "render_job_id": self.render_job_id,
            "run_id": self.run_id,
            "composition": self.composition,
            "mode": self.mode,
            "approved_final_render": self.approved_final_render,
            "modifications": dict(self.modifications),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "RenderJobRequest":
        d = d or {}
        return cls(
            render_job_id=str(d.get("render_job_id") or d.get("renderJobId") or ""),
            run_id=str(d.get("run_id") or d.get("runId") or ""),
            composition=str(d.get("composition") or "timelineV2"),
            mode=str(d.get("mode") or "final"),
            approved_final_render=bool(
                d.get("approved_final_render", d.get("approvedFinalRender", False))
            ),
            modifications=dict(d.get("modifications") or {}),
        )


@dataclass(frozen=True)
class RenderJobResponse:
    """Hephaestus 노드 출력. output_url = 최종 MP4."""
    render_job_id: str
    snapshot_id: str
    render_status: str
    output_url: str | None = None
    duration_s: float | None = None
    error: dict | None = None

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.render_job_id:
            errs.append("RenderJobResponse.render_job_id 필수")
        if self.render_status == "completed" and not self.output_url:
            errs.append("RenderJobResponse: completed인데 output_url 없음")
        return errs

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
            # 0.0초(프레임 렌더 등)를 falsy로 잃지 않게 명시 None 체크.
            duration_s=(r.get("duration_s") if r.get("duration_s") is not None else r.get("durationS")),
            error=None if ok else ({"reason": r.get("error")} if r.get("error") else None),
        )

    def to_dict(self) -> dict:
        return {
            "render_job_id": self.render_job_id,
            "snapshot_id": self.snapshot_id,
            "render_status": self.render_status,
            "output_url": self.output_url,
            "duration_s": self.duration_s,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "RenderJobResponse":
        d = d or {}
        return cls(
            render_job_id=str(d.get("render_job_id") or ""),
            snapshot_id=str(d.get("snapshot_id") or ""),
            render_status=str(d.get("render_status") or ""),
            output_url=d.get("output_url"),
            duration_s=d.get("duration_s"),
            error=d.get("error"),
        )


# ── Metis 입력 (측정 — 출력은 기존 ReelMetric/FeedbackSignal) ──
@dataclass(frozen=True)
class ProcessInsightsRequest:
    """Metis 노드 입력. sb 인자 없음 = DSL 순수성 (DB fetch는 셸로)."""
    raw_insights: tuple[dict, ...] = ()
    run_brand_map: dict = field(default_factory=dict)
    window_days: int = 30

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.window_days <= 0:
            errs.append("ProcessInsightsRequest.window_days must be > 0")
        if not isinstance(self.raw_insights, (list, tuple)):
            errs.append("ProcessInsightsRequest.raw_insights must be a list/tuple")
        if not isinstance(self.run_brand_map, dict):
            errs.append("ProcessInsightsRequest.run_brand_map must be a dict")
        return errs

    def to_dict(self) -> dict:
        return {
            "raw_insights": list(self.raw_insights),
            "run_brand_map": dict(self.run_brand_map),
            "window_days": self.window_days,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "ProcessInsightsRequest":
        d = d or {}
        insights = d.get("raw_insights") or ()
        wd = d.get("window_days")
        return cls(
            raw_insights=tuple(insights) if isinstance(insights, (list, tuple)) else (),
            run_brand_map=dict(d.get("run_brand_map") or {}),
            window_days=int(wd) if wd is not None else 30,
        )


__all__ = [
    "VisualContext", "VisualRequest",
    "AudioRequest", "SFXRequest",
    "RenderJobRequest", "RenderJobResponse",
    "ProcessInsightsRequest",
    "BeatPersona", "BeatPersonas",
]

# re-export seam contract for convenience (VisualRequest 합성 요소)
from .beat_personas import BeatPersona  # noqa: E402
