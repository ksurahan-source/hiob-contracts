"""CompositionSnapshot — 조립/렌더 계약 (Atropos → Hephaestus).

grounding: composition_snapshot(run_id, selection {slot_id:artifact_id},
preview/final_artifact_id, render_status, share_token, rendered_at).
+ output_url(durable) + gate_passed(렌더前 invariant 증명) = WS06 다리·P1·P10 봉쇄.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class CompositionSnapshot:
    run_id: str
    selection: dict = field(default_factory=dict)   # {slot_id: artifact_id}
    render_status: str = "pending"                   # pending|rendering|completed|failed
    output_url: Optional[str] = None                 # durable(공개버킷/서명갱신)
    preview_artifact_id: Optional[str] = None
    final_artifact_id: Optional[str] = None
    share_token: Optional[str] = None
    gate_passed: bool = False                         # assert_render_ready 통과 증명
    rendered_at: Optional[str] = None

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.run_id:
            errs.append("run_id 없음")
        if self.render_status not in ("pending", "rendering", "completed", "failed"):
            errs.append(f"render_status 미지원: {self.render_status}")
        # 렌더 시작 전 invariant gate 증명 강제(P1/false-DONE 차단)
        if self.render_status in ("rendering", "completed") and not self.gate_passed:
            errs.append("gate_passed=False인데 렌더 진행 (invariant 미증명)")
        if self.render_status == "completed" and not self.output_url:
            errs.append("completed인데 output_url 없음 (WS06 배송 다리 끊김)")
        return errs

    @classmethod
    def from_row(cls, row: dict) -> "CompositionSnapshot":
        attrs = row.get("attributes") or {}
        return cls(
            run_id=row.get("run_id") or row.get("run") or "",
            selection=row.get("selection") or {},
            render_status=row.get("render_status", "pending"),
            output_url=row.get("output_url") or attrs.get("output_url"),
            preview_artifact_id=row.get("preview_artifact_id"),
            final_artifact_id=row.get("final_artifact_id"),
            share_token=row.get("share_token"),
            gate_passed=bool(attrs.get("gate_passed", False)),
            rendered_at=row.get("rendered_at"),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "CompositionSnapshot":
        """dict → CompositionSnapshot (envelope_validation path)."""
        d = d or {}
        return cls(
            run_id=str(d.get("run_id") or ""),
            selection=dict(d.get("selection") or {}),
            render_status=str(d.get("render_status") or "pending"),
            output_url=d.get("output_url"),
            preview_artifact_id=d.get("preview_artifact_id"),
            final_artifact_id=d.get("final_artifact_id"),
            share_token=d.get("share_token"),
            gate_passed=bool(d.get("gate_passed", False)),
            rendered_at=d.get("rendered_at"),
        )
