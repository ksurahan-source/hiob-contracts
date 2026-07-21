"""Remaining edge target_input contracts for envelope runtime validation (LP1-7 / UM-1).

edge_registry declares one target_contract name per SemanticEdge. j2p/p2a already have
dedicated modules (ParzifalTargetInput, AresScriptInput). This module supplies the rest
so envelope_validation can fail-loud on all 9 registry edges.

Shapes track the live F1 chain (star planning_command) and planet node inputs:
  a2athena      → AthenaPlanInput   (athena.visual.plan / PlanVisualsInput)
  a2orpheus     → OrpheusPlanInput  (orpheus.audio.select_music / AudioRequest-ish)
  a2apollo      → ApolloPlanInput   (apollo.sfx.select / SFXRequest-ish)
  media2atropos → AtroposDraftInput (atropos.draft fan-in)
  atropos2artemis → ArtemisReviewInput  (SUNSET — not on F1; Artemis = product/evidence seal)
  artemis2atropos → AtroposApplyInput   (SUNSET — optional historical editorial apply)
  atropos2hephaestus → HephaestusRenderInput (G3 approval ref + snapshot)

Validation is structural completeness only — Karma still owns grounding policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


# ── a2athena ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AthenaPlanInput:
    """Karma-refined visual plan input for Athena (a2athena)."""

    beat_plan: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    beat_personas: Optional[dict] = None
    element_locks: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not isinstance(self.beat_plan, dict):
            errs.append("AthenaPlanInput.beat_plan must be a dict")
            return errs
        beats = self.beat_plan.get("beats")
        if beats is None and not self.beat_plan:
            errs.append("AthenaPlanInput.beat_plan 필수 (beats 또는 비어있지 않은 plan)")
        elif beats is not None and not isinstance(beats, (list, tuple)):
            errs.append("AthenaPlanInput.beat_plan.beats must be a list")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "AthenaPlanInput":
        d = d or {}
        bp = d.get("beat_plan")
        if isinstance(bp, list):
            bp = {"beats": bp}
        elif not isinstance(bp, dict):
            bp = {}
        personas = d.get("beat_personas")
        return cls(
            beat_plan=bp,
            context=_as_dict(d.get("context")),
            beat_personas=personas if isinstance(personas, dict) else None,
            element_locks=_as_dict(d.get("element_locks")),
        )


# ── a2orpheus ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class OrpheusPlanInput:
    """Karma-refined voice/music plan input for Orpheus (a2orpheus)."""

    music_vibe: str = ""
    target_ms: int = 0
    voice_persona: str = ""
    voice_concept: str = ""
    source_text: str = ""
    beat_index: Optional[int] = None
    music_bpm: int = 0
    music_pool: tuple[dict, ...] = ()

    def validate(self) -> list[str]:
        errs: list[str] = []
        has_music = bool(self.music_vibe) or self.target_ms > 0 or bool(self.music_pool)
        has_voice = bool(self.voice_persona or self.voice_concept or self.source_text)
        if not (has_music or has_voice):
            errs.append(
                "OrpheusPlanInput: music (vibe/target_ms/pool) 또는 voice "
                "(persona/concept/text) 중 최소 1개 필요"
            )
        if self.target_ms < 0:
            errs.append("OrpheusPlanInput.target_ms must be >= 0")
        if self.music_bpm < 0:
            errs.append("OrpheusPlanInput.music_bpm must be >= 0")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "OrpheusPlanInput":
        d = d or {}
        pool = d.get("music_pool") or ()
        if isinstance(pool, list):
            pool = tuple(pool)
        beat = d.get("beat_index")
        return cls(
            music_vibe=str(d.get("music_vibe") or ""),
            target_ms=int(d.get("target_ms") or 0),
            voice_persona=str(d.get("voice_persona") or ""),
            voice_concept=str(d.get("voice_concept") or ""),
            source_text=str(d.get("source_text") or ""),
            beat_index=int(beat) if beat is not None else None,
            music_bpm=int(d.get("music_bpm") or 0),
            music_pool=tuple(pool) if isinstance(pool, tuple) else (),
        )


# ── a2apollo ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ApolloPlanInput:
    """Karma-refined SFX plan input for Apollo (a2apollo; optional edge)."""

    cues: tuple[dict, ...] = ()
    asset_pool: tuple[dict, ...] = ()
    shot_list_digest: str = ""

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not isinstance(self.cues, (list, tuple)):
            errs.append("ApolloPlanInput.cues must be a list/tuple")
            return errs
        for i, cue in enumerate(self.cues):
            if not isinstance(cue, dict):
                errs.append(f"ApolloPlanInput.cues[{i}] must be a dict")
                continue
            if "beat_index" not in cue and "text" not in cue and "cue" not in cue:
                errs.append(
                    f"ApolloPlanInput.cues[{i}]: beat_index/text/cue 중 하나 필요"
                )
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ApolloPlanInput":
        d = d or {}
        cues = d.get("cues") or ()
        pool = d.get("asset_pool") or ()
        return cls(
            cues=tuple(cues) if isinstance(cues, (list, tuple)) else (),
            asset_pool=tuple(pool) if isinstance(pool, (list, tuple)) else (),
            shot_list_digest=str(d.get("shot_list_digest") or ""),
        )


# ── media2atropos ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AtroposDraftInput:
    """Karma-refined media fan-in for Atropos draft (media2atropos)."""

    run_id: str
    media: tuple[dict, ...] = ()
    audio: tuple[dict, ...] = ()

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.run_id:
            errs.append("AtroposDraftInput.run_id 필수")
        if not self.media and not self.audio:
            errs.append("AtroposDraftInput: media 또는 audio 중 최소 1개 필요")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "AtroposDraftInput":
        d = d or {}
        return cls(
            run_id=str(d.get("run_id") or ""),
            media=tuple(_as_list(d.get("media"))),
            audio=tuple(_as_list(d.get("audio"))),
        )


# ── atropos2artemis (SUNSET — registry optional; not live F1) ──────────────
@dataclass(frozen=True)
class ArtemisReviewInput:
    """SUNSET: was Karma-refined editorial review input (atropos2artemis).

    Artemis live identity is product/evidence sealing via
    artemis.references.snapshot — not this contract.
    """

    run_id: str
    selection: dict = field(default_factory=dict)
    render_status: str = "pending"
    output_url: Optional[str] = None
    preview_artifact_id: Optional[str] = None
    final_artifact_id: Optional[str] = None
    share_token: Optional[str] = None
    gate_passed: bool = False
    rendered_at: Optional[str] = None
    beat_count: int = 0
    expected_media: dict = field(default_factory=dict)
    defect_signals: list = field(default_factory=list)
    prior_revisions: int = 0
    approval_digest: Optional[str] = None

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.run_id:
            errs.append("ArtemisReviewInput.run_id 필수")
        if self.render_status not in ("pending", "rendering", "completed", "failed"):
            errs.append(f"ArtemisReviewInput.render_status 미지원: {self.render_status}")
        if self.render_status in ("rendering", "completed") and not self.gate_passed:
            errs.append(
                "ArtemisReviewInput: render_status in progress but gate_passed=False"
            )
        if self.render_status == "completed" and not self.output_url:
            errs.append(
                "ArtemisReviewInput: render_status=completed but no output_url"
            )
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ArtemisReviewInput":
        d = d or {}
        return cls(
            run_id=str(d.get("run_id") or ""),
            selection=_as_dict(d.get("selection")),
            render_status=str(d.get("render_status") or "pending"),
            output_url=d.get("output_url"),
            preview_artifact_id=d.get("preview_artifact_id"),
            final_artifact_id=d.get("final_artifact_id"),
            share_token=d.get("share_token"),
            gate_passed=bool(d.get("gate_passed", False)),
            rendered_at=d.get("rendered_at"),
            beat_count=int(d.get("beat_count") or 0),
            expected_media=_as_dict(d.get("expected_media")),
            defect_signals=list(d.get("defect_signals") or []),
            prior_revisions=int(d.get("prior_revisions") or 0),
            approval_digest=d.get("approval_digest"),
        )


# ── artemis2atropos ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class AtroposApplyInput:
    """Karma-refined accepted editorial proposals for Atropos apply (optional)."""

    run_id: str
    accepted_proposals: tuple[dict, ...] = ()
    approval_receipt_ref: Optional[str] = None

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.run_id:
            errs.append("AtroposApplyInput.run_id 필수")
        if not self.accepted_proposals and not self.approval_receipt_ref:
            errs.append(
                "AtroposApplyInput: accepted_proposals 또는 approval_receipt_ref 필요"
            )
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "AtroposApplyInput":
        d = d or {}
        props = d.get("accepted_proposals") or d.get("proposals") or ()
        return cls(
            run_id=str(d.get("run_id") or ""),
            accepted_proposals=tuple(_as_list(props)),
            approval_receipt_ref=d.get("approval_receipt_ref"),
        )


# ── atropos2hephaestus ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class HephaestusRenderInput:
    """Karma-refined render authorization for Hephaestus (atropos2hephaestus).

    Final render requires a G3 approval_receipt_ref (FR-8). Preview/draft may omit it.
    """

    run_id: str = ""
    snapshot: dict = field(default_factory=dict)
    approval_receipt_ref: Optional[str] = None
    render_job_id: str = ""
    mode: str = "final"

    def validate(self) -> list[str]:
        errs: list[str] = []
        snap_run = ""
        if isinstance(self.snapshot, dict):
            snap_run = str(self.snapshot.get("run_id") or "")
        run = self.run_id or snap_run
        if not run:
            errs.append("HephaestusRenderInput.run_id 필수 (top-level 또는 snapshot.run_id)")
        if not isinstance(self.snapshot, dict) or not self.snapshot:
            errs.append("HephaestusRenderInput.snapshot 필수 (CompositionSnapshot-like)")
        if self.mode == "final" and not self.approval_receipt_ref:
            errs.append(
                "HephaestusRenderInput: mode=final 이면 approval_receipt_ref(G3) 필수"
            )
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "HephaestusRenderInput":
        d = d or {}
        snap = d.get("snapshot")
        if not isinstance(snap, dict):
            # Allow flat CompositionSnapshot-shaped payloads
            if any(k in d for k in ("selection", "render_status", "gate_passed")):
                snap = {
                    k: d[k]
                    for k in (
                        "run_id",
                        "selection",
                        "render_status",
                        "output_url",
                        "gate_passed",
                        "preview_artifact_id",
                        "final_artifact_id",
                    )
                    if k in d
                }
            else:
                snap = {}
        return cls(
            run_id=str(d.get("run_id") or snap.get("run_id") or ""),
            snapshot=snap,
            approval_receipt_ref=d.get("approval_receipt_ref"),
            render_job_id=str(d.get("render_job_id") or ""),
            mode=str(d.get("mode") or "final"),
        )


# ── hermes CAPI (planet I/O; not a factory SemanticEdge, but UM-1 residual) ──
@dataclass(frozen=True)
class CAPIEvent:
    """Inbound CAPI Purchase/event envelope (Hermes input)."""

    event_name: str = ""
    event_id: str = ""
    event_time: int = 0
    user_data: dict = field(default_factory=dict)
    custom_data: dict = field(default_factory=dict)
    event_source_url: Optional[str] = None
    action_source: str = "website"

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.event_name:
            errs.append("CAPIEvent.event_name 필수")
        if not self.event_id:
            errs.append("CAPIEvent.event_id 필수 (dedup key)")
        if not isinstance(self.user_data, dict):
            errs.append("CAPIEvent.user_data must be a dict")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "CAPIEvent":
        d = d or {}
        return cls(
            event_name=str(d.get("event_name") or ""),
            event_id=str(d.get("event_id") or d.get("order_id") or ""),
            event_time=int(d.get("event_time") or 0),
            user_data=_as_dict(d.get("user_data")),
            custom_data=_as_dict(d.get("custom_data")),
            event_source_url=d.get("event_source_url"),
            action_source=str(d.get("action_source") or "website"),
        )


@dataclass(frozen=True)
class CAPIPayload:
    """Hermes-prepared CAPI payload ready for owner-gated write (Hermes output)."""

    install_id: str = ""
    event_name: str = ""
    event_id: str = ""
    matched_session: bool = False
    event_source_url: Optional[str] = None
    recovered_via: Optional[str] = None
    params_sent: tuple[str, ...] = ()
    pipa_consent: bool = True

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.install_id:
            errs.append("CAPIPayload.install_id 필수")
        if not self.event_name:
            errs.append("CAPIPayload.event_name 필수")
        if not self.event_id:
            errs.append("CAPIPayload.event_id 필수")
        if not self.pipa_consent:
            errs.append("CAPIPayload.pipa_consent must be True for dispatch")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "CAPIPayload":
        d = d or {}
        params = d.get("params_sent") or ()
        return cls(
            install_id=str(d.get("install_id") or ""),
            event_name=str(d.get("event_name") or ""),
            event_id=str(d.get("event_id") or ""),
            matched_session=bool(d.get("matched_session", False)),
            event_source_url=d.get("event_source_url"),
            recovered_via=d.get("recovered_via"),
            params_sent=tuple(params) if isinstance(params, (list, tuple)) else (),
            pipa_consent=bool(d.get("pipa_consent", True)),
        )


__all__ = [
    "AthenaPlanInput",
    "OrpheusPlanInput",
    "ApolloPlanInput",
    "AtroposDraftInput",
    "ArtemisReviewInput",
    "AtroposApplyInput",
    "HephaestusRenderInput",
    "CAPIEvent",
    "CAPIPayload",
]
