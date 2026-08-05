"""Ares V4 story contract: sealed upstream authority → fixed multi-beat arc.

V3 proved that a run could carry a beat count.  It did not make the story arc
an authority-bound input.  V4 deliberately accepts only two production
formats, requires every slot in their exact order, and rejects any raw 13Q or
one-beat shortcut before Ares can call a model.

This is a pure value contract.  Janus, Karma, Parzifal, Artemis, and Metis
remain the owners of their respective inputs; Ares consumes their sealed
references and never re-ranks or re-fetches them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)
from .factory import sha256_digest


StoryModeV4 = Literal["ugc_story", "info_short"]
StoryFunctionV4 = Literal[
    "scene",
    "tension",
    "bad_alternative",
    "urgent_moment",
    "proof",
    "objection",
    "transformation",
    "offer_or_cta",
    "offer",
    "cta",
]

UGC_STORY_SLOT_SEQUENCE_V4: tuple[StoryFunctionV4, ...] = (
    "scene",
    "scene",
    "tension",
    "tension",
    "bad_alternative",
    "bad_alternative",
    "urgent_moment",
    "urgent_moment",
    "proof",
    "proof",
    "objection",
    "objection",
    "transformation",
    "transformation",
    "offer_or_cta",
    "offer_or_cta",
)
INFO_SHORT_SLOT_SEQUENCE_V4: tuple[StoryFunctionV4, ...] = (
    "scene",
    "tension",
    "bad_alternative",
    "urgent_moment",
    "proof",
    "proof",
    "objection",
    "objection",
    "transformation",
    "transformation",
    "offer",
    "cta",
)


def story_slot_sequence_v4(mode: StoryModeV4) -> tuple[StoryFunctionV4, ...]:
    """Return the only legal slot sequence for a production story mode."""

    if mode == "ugc_story":
        return UGC_STORY_SLOT_SEQUENCE_V4
    if mode == "info_short":
        return INFO_SHORT_SLOT_SEQUENCE_V4
    raise ValueError("mode must be one of the Ares V4 production story modes")


class AresStoryRequestScopeV4(BaseModel):
    """Caller execution scope shared by all five upstream authority refs."""

    model_config = _FROZEN_STRICT

    workspace_id: NonBlankStr
    run_id: NonBlankStr
    operation_id: NonBlankStr
    idempotency_key: NonBlankStr


def story_authority_ref_receipt_digest_v4(
    *,
    producer: str,
    artifact_type: str,
    artifact_digest: str,
    source_output_digest: str,
    payload_digest: str,
    receipt_id: str,
    workspace_id: str,
    run_id: str,
) -> str:
    """Bind an opaque producer receipt to its V4 authority reference fields."""

    return sha256_digest(
        {
            "contract_version": "AresStoryAuthorityRefReceipt.v4",
            "producer": producer,
            "artifact_type": artifact_type,
            "artifact_digest": artifact_digest,
            "source_output_digest": source_output_digest,
            "payload_digest": payload_digest,
            "receipt_id": receipt_id,
            "workspace_id": workspace_id,
            "run_id": run_id,
        }
    )


class AresStoryAuthorityRefV4(BaseModel):
    """Immutable receipt and digest binding for one producer-owned artifact."""

    model_config = _FROZEN_STRICT

    producer: Literal["janus", "karma", "parzifal", "artemis", "metis"]
    artifact_type: Literal[
        "product_truth",
        "story_brief",
        "identity_lock",
        "evidence_bundle",
        "hook_directive",
    ]
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    payload_digest: DigestStr
    receipt_id: NonBlankStr
    receipt_digest: DigestStr
    workspace_id: NonBlankStr
    run_id: NonBlankStr

    @model_validator(mode="after")
    def _bind_receipt_subject(self) -> "AresStoryAuthorityRefV4":
        expected = story_authority_ref_receipt_digest_v4(
            producer=self.producer,
            artifact_type=self.artifact_type,
            artifact_digest=self.artifact_digest,
            source_output_digest=self.source_output_digest,
            payload_digest=self.payload_digest,
            receipt_id=self.receipt_id,
            workspace_id=self.workspace_id,
            run_id=self.run_id,
        )
        if self.receipt_digest != expected:
            raise ValueError(
                "receipt_digest must bind the canonical V4 authority reference"
            )
        return self


class AresStoryAuthorityBundleV4(BaseModel):
    """The five explicit producers permitted to author a V4 story input."""

    model_config = _FROZEN_STRICT

    janus_product_truth_ref: AresStoryAuthorityRefV4
    karma_story_brief_ref: AresStoryAuthorityRefV4
    parzifal_identity_lock_ref: AresStoryAuthorityRefV4
    artemis_evidence_bundle_ref: AresStoryAuthorityRefV4
    metis_hook_directive_ref: AresStoryAuthorityRefV4

    @model_validator(mode="after")
    def _require_correct_producer_owners(self) -> "AresStoryAuthorityBundleV4":
        expected = {
            "janus_product_truth_ref": ("janus", "product_truth"),
            "karma_story_brief_ref": ("karma", "story_brief"),
            "parzifal_identity_lock_ref": ("parzifal", "identity_lock"),
            "artemis_evidence_bundle_ref": ("artemis", "evidence_bundle"),
            "metis_hook_directive_ref": ("metis", "hook_directive"),
        }
        for field, (producer, artifact_type) in expected.items():
            ref = getattr(self, field)
            if ref.producer != producer or ref.artifact_type != artifact_type:
                raise ValueError(
                    f"{field} must be issued by {producer} as {artifact_type}"
                )
        return self


class AresStoryEvidenceAnchorV4(BaseModel):
    """One Artemis-owned proof anchor and the claim Ares may use with it."""

    model_config = _FROZEN_STRICT

    anchor_id: NonBlankStr
    claim_id: NonBlankStr
    statement: NonBlankStr


class AresStoryEvidenceBundleV4(BaseModel):
    """The exact proof-anchor projection of Artemis evidence for this story."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresStoryEvidenceBundle.v4"]
    evidence_bundle_digest: DigestStr
    anchors: tuple[AresStoryEvidenceAnchorV4, ...] = Field(min_length=1)

    @field_validator("anchors", mode="before")
    @classmethod
    def _anchors_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _require_unique_anchor_and_claim_ids(self) -> "AresStoryEvidenceBundleV4":
        anchor_ids = [anchor.anchor_id for anchor in self.anchors]
        claim_ids = [anchor.claim_id for anchor in self.anchors]
        if len(anchor_ids) != len(set(anchor_ids)):
            raise ValueError("Artemis evidence anchor_id values must be unique")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Artemis evidence claim_id values must be unique")
        return self


class AresKarmaObjectionAnchorV4(BaseModel):
    """A Karma-reconciled customer objection Ares must address, not invent."""

    model_config = _FROZEN_STRICT

    anchor_id: NonBlankStr
    objection: NonBlankStr


class AresStoryBeatV4(BaseModel):
    """One semantic story slot; Athena still owns camera and render grammar."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    arc_stage: StoryFunctionV4
    story_function: StoryFunctionV4
    scene_intent: NonBlankStr
    used_claim_ids: tuple[NonBlankStr, ...] = ()
    addresses_anchor_ids: tuple[NonBlankStr, ...] = ()

    @field_validator("used_claim_ids", "addresses_anchor_ids", mode="before")
    @classmethod
    def _ids_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _require_unique_ids(self) -> "AresStoryBeatV4":
        if len(self.used_claim_ids) != len(set(self.used_claim_ids)):
            raise ValueError("used_claim_ids must not repeat a claim")
        if len(self.addresses_anchor_ids) != len(set(self.addresses_anchor_ids)):
            raise ValueError("addresses_anchor_ids must not repeat an anchor")
        return self


class AresStoryNarrativeBriefV4(BaseModel):
    """Karma-sealed story arc that Ares may turn into a script, never re-plan."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresStoryNarrativeBrief.v4"]
    mode: StoryModeV4
    beats: tuple[AresStoryBeatV4, ...]
    karma_objection_anchors: tuple[AresKarmaObjectionAnchorV4, ...] = Field(
        min_length=1
    )
    story_brief_digest: DigestStr

    @field_validator("beats", "karma_objection_anchors", mode="before")
    @classmethod
    def _to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_fixed_slots_and_digest(self) -> "AresStoryNarrativeBriefV4":
        expected_slots = story_slot_sequence_v4(self.mode)
        if len(self.beats) != len(expected_slots):
            raise ValueError(
                f"{self.mode} requires exactly {len(expected_slots)} story beats"
            )
        for index, (beat, expected_stage) in enumerate(
            zip(self.beats, expected_slots, strict=True)
        ):
            if beat.beat_index != index:
                raise ValueError("story beat indices must be exactly 0..N-1")
            if beat.arc_stage != expected_stage:
                raise ValueError(
                    f"beat {index} arc_stage must be {expected_stage} for {self.mode}"
                )
            if beat.story_function != expected_stage:
                raise ValueError(
                    f"beat {index} story_function must be {expected_stage} for {self.mode}"
                )
        objection_ids = [anchor.anchor_id for anchor in self.karma_objection_anchors]
        if len(objection_ids) != len(set(objection_ids)):
            raise ValueError("Karma objection anchor_id values must be unique")
        if self.story_brief_digest != canonical_contract_digest_v1(
            self, exclude={"story_brief_digest"}
        ):
            raise ValueError(
                "story_brief_digest must bind the canonical Ares V4 narrative brief"
            )
        return self


class AresCreateStoryRequestV4(BaseModel):
    """Ares input for a complete, authority-bound UGC or informational story."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresCreateStoryRequest.v4"]
    scope: AresStoryRequestScopeV4
    authority: AresStoryAuthorityBundleV4
    evidence_bundle: AresStoryEvidenceBundleV4
    narrative_brief: AresStoryNarrativeBriefV4

    @model_validator(mode="after")
    def _bind_authority_scope_anchors_and_payloads(
        self,
    ) -> "AresCreateStoryRequestV4":
        refs = (
            self.authority.janus_product_truth_ref,
            self.authority.karma_story_brief_ref,
            self.authority.parzifal_identity_lock_ref,
            self.authority.artemis_evidence_bundle_ref,
            self.authority.metis_hook_directive_ref,
        )
        for ref in refs:
            if ref.workspace_id != self.scope.workspace_id:
                raise ValueError("authority ref workspace_id must match request scope")
            if ref.run_id != self.scope.run_id:
                raise ValueError("authority ref run_id must match request scope")

        evidence_ref = self.authority.artemis_evidence_bundle_ref
        if evidence_ref.artifact_digest != self.evidence_bundle.evidence_bundle_digest:
            raise ValueError(
                "artemis_evidence_bundle_ref.artifact_digest must match evidence bundle"
            )
        if evidence_ref.payload_digest != sha256_digest(
            self.evidence_bundle.model_dump(mode="json")
        ):
            raise ValueError(
                "artemis_evidence_bundle_ref.payload_digest must bind evidence bundle"
            )

        brief_ref = self.authority.karma_story_brief_ref
        if brief_ref.artifact_digest != self.narrative_brief.story_brief_digest:
            raise ValueError(
                "karma_story_brief_ref.artifact_digest must match narrative brief"
            )
        if brief_ref.payload_digest != sha256_digest(
            self.narrative_brief.model_dump(mode="json")
        ):
            raise ValueError(
                "karma_story_brief_ref.payload_digest must bind narrative brief"
            )

        evidence_anchor_ids = {
            anchor.anchor_id for anchor in self.evidence_bundle.anchors
        }
        evidence_claim_ids = {anchor.claim_id for anchor in self.evidence_bundle.anchors}
        objection_anchor_ids = {
            anchor.anchor_id for anchor in self.narrative_brief.karma_objection_anchors
        }
        if evidence_anchor_ids & objection_anchor_ids:
            raise ValueError("Artemis and Karma anchor_id values must not overlap")
        for beat in self.narrative_brief.beats:
            claim_ids = set(beat.used_claim_ids)
            if not claim_ids.issubset(evidence_claim_ids):
                raise ValueError("used_claim_ids must be sealed Artemis claim ids")
            anchor_ids = set(beat.addresses_anchor_ids)
            if beat.story_function == "proof":
                if not beat.used_claim_ids:
                    raise ValueError("proof stage requires at least one used_claim_id")
                if not anchor_ids or not anchor_ids.issubset(evidence_anchor_ids):
                    raise ValueError(
                        "proof stage must address at least one Artemis evidence anchor"
                    )
            elif beat.story_function == "objection":
                if not anchor_ids or not anchor_ids.issubset(objection_anchor_ids):
                    raise ValueError(
                        "objection stage must address at least one Karma objection anchor"
                    )
            elif anchor_ids:
                raise ValueError(
                    "only proof and objection stages may address authority anchors"
                )
        return self


def ares_create_story_request_v4_schema_descriptor() -> dict[str, Any]:
    """Stable structural descriptor for cross-repo V4 compatibility checks."""

    return {
        "contract_version": "AresCreateStoryRequest.v4",
        "modes": {
            "ugc_story": list(UGC_STORY_SLOT_SEQUENCE_V4),
            "info_short": list(INFO_SHORT_SLOT_SEQUENCE_V4),
        },
        "request_fields": sorted(AresCreateStoryRequestV4.model_fields),
        "scope_fields": sorted(AresStoryRequestScopeV4.model_fields),
        "authority_fields": sorted(AresStoryAuthorityBundleV4.model_fields),
        "authority_ref_fields": sorted(AresStoryAuthorityRefV4.model_fields),
        "evidence_bundle_fields": sorted(AresStoryEvidenceBundleV4.model_fields),
        "evidence_anchor_fields": sorted(AresStoryEvidenceAnchorV4.model_fields),
        "narrative_brief_fields": sorted(AresStoryNarrativeBriefV4.model_fields),
        "story_beat_fields": sorted(AresStoryBeatV4.model_fields),
        "objection_anchor_fields": sorted(AresKarmaObjectionAnchorV4.model_fields),
        "invariants": [
            "raw_13q=forbidden",
            "one_beat=forbidden",
            "proof=artemis_evidence_anchor+claim",
            "objection=karma_objection_anchor",
            "all_five_upstream_refs=scope_bound+receipt_bound",
        ],
    }


def ares_create_story_request_v4_schema_digest() -> str:
    return sha256_digest(ares_create_story_request_v4_schema_descriptor())


def request_content_digest_v4(request: AresCreateStoryRequestV4) -> str:
    """Canonical digest of the immutable request passed to Ares."""

    return canonical_contract_digest_v1(request)


__all__ = [
    "StoryModeV4",
    "StoryFunctionV4",
    "UGC_STORY_SLOT_SEQUENCE_V4",
    "INFO_SHORT_SLOT_SEQUENCE_V4",
    "story_slot_sequence_v4",
    "AresStoryRequestScopeV4",
    "story_authority_ref_receipt_digest_v4",
    "AresStoryAuthorityRefV4",
    "AresStoryAuthorityBundleV4",
    "AresStoryEvidenceAnchorV4",
    "AresStoryEvidenceBundleV4",
    "AresKarmaObjectionAnchorV4",
    "AresStoryBeatV4",
    "AresStoryNarrativeBriefV4",
    "AresCreateStoryRequestV4",
    "ares_create_story_request_v4_schema_descriptor",
    "ares_create_story_request_v4_schema_digest",
    "request_content_digest_v4",
]
