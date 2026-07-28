"""Ares pure generate contract V2 — sealed input → ScriptPackage + BeatPlan.

Public business shape for:

    POST /v2/scripts:generate

Ares is a pure writer node. Callers (Star) must supply all authority and
sealed facts; Ares must not re-query DB, re-cast, re-select evidence, or
dispatch downstream planets.

Forbidden in this envelope (enforced by field set + extra=forbid):
- DB candidate / job / approval state
- event publish results
- visual reference seals (Star bridge owns those)
- shot / camera / render mode (Athena owns those)
- next-planet dispatch info
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .ares_script_revision_v1 import (
    AresBeatV1,
    AresScriptSegmentV1,
    DigestStr,
    NonBlankStr,
    NonEmptyStr,
    NonNegativeInt,
    UtcTimestamp,
    _FROZEN_STRICT,
    _FrozenMapping,
    _deep_freeze_json,
    _json_value,
    _validate_json,
    canonical_contract_digest_v1,
)
from .factory import KarmaEdgeReceipt, sha256_digest
from .character_identity_v1 import character_identity_binding_errors_v1
from .provenance import ClaimProvenance
from .voice_spec_v1 import VoiceSpecV1


# ── Sealed request sections ────────────────────────────────────────────────


class AresAuthorityV2(BaseModel):
    """JKPA authority bundle — all three fields required (no optional escape)."""

    model_config = _FROZEN_STRICT

    accepted_p2a_receipt: KarmaEdgeReceipt
    identity_lock_digest: DigestStr
    product_truth_digest: DigestStr

    @model_validator(mode="after")
    def _require_accepted_p2a(self) -> "AresAuthorityV2":
        receipt = self.accepted_p2a_receipt
        if receipt.edge_id != "p2a":
            raise ValueError("accepted_p2a_receipt.edge_id must be 'p2a'")
        if receipt.decision != "accepted":
            raise ValueError(
                "accepted_p2a_receipt.decision must be 'accepted' "
                f"(got {receipt.decision!r})"
            )
        if receipt.target_contract.name != "AresScriptInput":
            raise ValueError(
                "accepted_p2a_receipt.target_contract.name must be 'AresScriptInput'"
            )
        if self.identity_lock_digest not in receipt.source_output_digests:
            raise ValueError(
                "identity_lock_digest must appear in "
                "accepted_p2a_receipt.source_output_digests"
            )
        return self


class AresSpeakerSlotV2(BaseModel):
    """One sealed speaking role — Parzifal owns selection; Ares only consumes."""

    model_config = _FROZEN_STRICT

    role: NonBlankStr
    subject_id: NonBlankStr
    display_name: NonBlankStr
    voice_id: NonBlankStr | None = None
    face_id: NonBlankStr | None = None
    identity_binding_digest: DigestStr | None = None
    voice_spec: VoiceSpecV1

    @model_validator(mode="after")
    def _atomic_face_and_voice(self) -> "AresSpeakerSlotV2":
        errors = character_identity_binding_errors_v1(
            subject_id=self.subject_id,
            face_id=self.face_id,
            voice_id=self.voice_id,
            identity_binding_digest=self.identity_binding_digest,
        )
        if errors:
            raise ValueError(errors[0])
        if self.voice_spec.subject_id != self.subject_id:
            raise ValueError(
                "voice_spec.subject_id must match speaker subject_id"
            )
        return self


class AresIdentitySealedV2(BaseModel):
    """Sealed cast / identity from Parzifal (no Ares heuristic defaults)."""

    model_config = _FROZEN_STRICT

    identity_lock_digest: DigestStr
    cast_sheet_digest: DigestStr
    speakers: tuple[AresSpeakerSlotV2, ...] = Field(min_length=1)
    locale: NonBlankStr = "ko"
    audience_lock: NonBlankStr | None = None

    @field_validator("speakers", mode="before")
    @classmethod
    def _speakers_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _unique_roles(self) -> "AresIdentitySealedV2":
        roles = [slot.role for slot in self.speakers]
        if len(roles) != len(set(roles)):
            raise ValueError("speakers roles must be unique")
        return self


class AresProductFactsSealedV2(BaseModel):
    """Sealed product / listing truth from Janus (no Ares re-fetch)."""

    model_config = _FROZEN_STRICT

    product_truth_digest: DigestStr
    brand_slug: NonBlankStr
    brand_display_name: NonBlankStr
    product_name: NonBlankStr
    listing_slug: NonBlankStr | None = None
    listing_pitch: NonBlankStr | None = None
    price_text: NonBlankStr | None = None
    refund_policy_text: NonBlankStr | None = None
    usp_lines: tuple[NonBlankStr, ...] = ()
    regulation_notes: NonBlankStr | None = None
    facts_block: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("usp_lines", mode="before")
    @classmethod
    def _usp_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("facts_block", mode="after")
    @classmethod
    def _freeze_facts(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        _validate_json(value, "facts_block")
        return _deep_freeze_json(value)

    @field_serializer("facts_block", when_used="always")
    def _serialize_facts_block(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _json_value(value)


class AresClaimRefV2(BaseModel):
    """One claim Ares may use, already grounded by Artemis/Janus."""

    model_config = _FROZEN_STRICT

    claim_id: NonBlankStr
    text: NonBlankStr
    claim_kind: NonBlankStr = "product_fact"
    provenance: ClaimProvenance | None = None
    evidence_ref: NonBlankStr | None = None


class AresEvidenceAndClaimsSealedV2(BaseModel):
    """Approved evidence refs + claim set (Ares may not mint new product claims)."""

    model_config = _FROZEN_STRICT

    evidence_bundle_digest: DigestStr
    claims: tuple[AresClaimRefV2, ...] = Field(min_length=1)
    voc_quotes: tuple[NonBlankStr, ...] = ()
    allowed_claim_ids: tuple[NonBlankStr, ...] = ()

    @field_validator("claims", "voc_quotes", "allowed_claim_ids", mode="before")
    @classmethod
    def _to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _claim_ids_consistent(self) -> "AresEvidenceAndClaimsSealedV2":
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("claims claim_id values must be unique")
        if self.allowed_claim_ids:
            allowed = set(self.allowed_claim_ids)
            unknown = [c.claim_id for c in self.claims if c.claim_id not in allowed]
            if unknown:
                raise ValueError(
                    f"claims not in allowed_claim_ids: {unknown[:5]}"
                )
        return self


class AresHookDirectiveV2(BaseModel):
    """Metis-owned hook selection — Ares must not re-rank reel_kpi."""

    model_config = _FROZEN_STRICT

    directive_digest: DigestStr
    archetype_id: NonBlankStr
    hook_line: NonBlankStr | None = None
    hook_register: NonBlankStr | None = None
    experiment_id: NonBlankStr | None = None
    rationale: NonBlankStr | None = None


class AresCreativeConstraintsV2(BaseModel):
    """Creative bounds sealed by Star / upstream planets (no Ares defaults)."""

    model_config = _FROZEN_STRICT

    n_beats: NonNegativeInt = Field(ge=1, le=64)
    format_mode: NonBlankStr | None = None
    style_mode: NonBlankStr | None = None
    vertical_mode: NonBlankStr | None = None
    goal: NonBlankStr | None = None
    fixed_hook: NonBlankStr | None = None
    human_instruction: str = ""
    prior_script_package_digest: DigestStr | None = None
    banned_phrases: tuple[NonBlankStr, ...] = ()
    required_phrases: tuple[NonBlankStr, ...] = ()

    @field_validator("banned_phrases", "required_phrases", mode="before")
    @classmethod
    def _phrase_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value


class AresCreateScriptRequestV2(BaseModel):
    """Single public generate request — authority + sealed facts only."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresCreateScriptRequest.v2"]
    authority: AresAuthorityV2
    identity: AresIdentitySealedV2
    product_facts: AresProductFactsSealedV2
    evidence_and_claims: AresEvidenceAndClaimsSealedV2
    hook_directive: AresHookDirectiveV2
    creative_constraints: AresCreativeConstraintsV2

    @model_validator(mode="after")
    def _authority_digests_match_payloads(self) -> "AresCreateScriptRequestV2":
        if (
            self.identity.identity_lock_digest
            != self.authority.identity_lock_digest
        ):
            raise ValueError(
                "identity.identity_lock_digest must equal "
                "authority.identity_lock_digest"
            )
        if (
            self.product_facts.product_truth_digest
            != self.authority.product_truth_digest
        ):
            raise ValueError(
                "product_facts.product_truth_digest must equal "
                "authority.product_truth_digest"
            )
        return self


# ── Pure generate artifacts (no DB ids) ────────────────────────────────────


class ScriptPackageV2(BaseModel):
    """Semantic script content without candidate/revision/job identifiers."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresScriptPackage.v2"]
    master_sales_script: Mapping[str, Any]
    voice_script: tuple[AresScriptSegmentV1, ...]
    caption_script: tuple[AresScriptSegmentV1, ...]
    pronunciation_overrides: Mapping[NonEmptyStr, NonEmptyStr] = Field(
        default_factory=dict
    )
    package_digest: DigestStr

    @field_validator("voice_script", "caption_script", mode="before")
    @classmethod
    def _segments_to_tuples(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("master_sales_script", mode="after")
    @classmethod
    def _freeze_master(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if not value:
            raise ValueError("master_sales_script must not be empty")
        _validate_json(value, "master_sales_script")
        return _deep_freeze_json(value)

    @field_validator("pronunciation_overrides", mode="after")
    @classmethod
    def _freeze_pronunciation(
        cls, value: Mapping[str, str]
    ) -> Mapping[str, str]:
        return _FrozenMapping(dict(value))

    @field_serializer(
        "master_sales_script",
        "pronunciation_overrides",
        when_used="always",
    )
    def _serialize_frozen_mappings(self, value: Mapping[str, Any]) -> dict:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_content(self) -> "ScriptPackageV2":
        count = len(self.voice_script)
        if count == 0:
            raise ValueError("voice_script must contain at least one segment")
        if len(self.caption_script) != count:
            raise ValueError(
                "voice_script and caption_script must have equal length"
            )
        expected = list(range(count))
        voice_idx = [s.beat_index for s in self.voice_script]
        cap_idx = [s.beat_index for s in self.caption_script]
        if voice_idx != expected:
            raise ValueError("voice_script beat indices must be exactly 0..N-1")
        if cap_idx != expected:
            raise ValueError("caption_script beat indices must be exactly 0..N-1")
        if any(not s.text.strip() for s in self.voice_script):
            raise ValueError("voice_script segments must contain non-empty dialogue")
        expected_digest = canonical_contract_digest_v1(
            self, exclude={"package_digest"}
        )
        if self.package_digest != expected_digest:
            raise ValueError("package_digest does not match ScriptPackageV2 payload")
        return self


class AresBeatRoleIntentV2(BaseModel):
    """Semantic role intent only — no shot/camera/render mode."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    roles: tuple[NonBlankStr, ...] = Field(min_length=1)
    on_camera: bool = True
    notes: str = ""

    @field_validator("roles", mode="before")
    @classmethod
    def _roles_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value


class BeatPlanV2(BaseModel):
    """Semantic beat plan for downstream VisualBrief assembly (Star/Athena)."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresBeatPlan.v2"]
    script_package_digest: DigestStr
    beats: tuple[AresBeatV1, ...]
    beat_role_intents: tuple[AresBeatRoleIntentV2, ...] = ()
    plan_digest: DigestStr

    @field_validator("beats", "beat_role_intents", mode="before")
    @classmethod
    def _to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_content(self) -> "BeatPlanV2":
        if not self.beats:
            raise ValueError("beats must contain at least one beat")
        indices = [b.beat_index for b in self.beats]
        if indices != list(range(len(indices))):
            raise ValueError("beat indices must be exactly 0..N-1 in array order")
        if self.beat_role_intents:
            role_idx = [i.beat_index for i in self.beat_role_intents]
            if sorted(role_idx) != role_idx:
                raise ValueError("beat_role_intents must be ordered by beat_index")
            if any(i < 0 or i >= len(self.beats) for i in role_idx):
                raise ValueError("beat_role_intents beat_index out of range")
        expected_digest = canonical_contract_digest_v1(
            self, exclude={"plan_digest"}
        )
        if self.plan_digest != expected_digest:
            raise ValueError("plan_digest does not match BeatPlanV2 payload")
        return self


# ── Result envelope ────────────────────────────────────────────────────────


class AresQualityFindingV2(BaseModel):
    """One quality gate observation (Ares check_script output)."""

    model_config = _FROZEN_STRICT

    code: NonBlankStr
    severity: Literal["info", "warn", "error"]
    message: NonBlankStr
    beat_index: NonNegativeInt | None = None
    gate: NonBlankStr | None = None


class AresGenerateProvenanceV2(BaseModel):
    """How this package was produced (no DB write proof)."""

    model_config = _FROZEN_STRICT

    producer: Literal["ares"] = "ares"
    contract_version: Literal["AresCreateScriptResult.v2"] = "AresCreateScriptResult.v2"
    request_content_digest: DigestStr
    model_id: NonBlankStr | None = None
    prompt_digest: DigestStr | None = None
    produced_at: UtcTimestamp | None = None


class AresGenerateUsageV2(BaseModel):
    """Token / cost accounting only — not job state."""

    model_config = _FROZEN_STRICT

    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    cost_cents: NonNegativeInt = 0
    model_id: NonBlankStr | None = None


class AresCreateScriptResultV2(BaseModel):
    """Single public generate result — package + plan + checks only."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresCreateScriptResult.v2"]
    status: Literal["ok", "blocked", "needs_human"] = "ok"
    script_package: ScriptPackageV2 | None = None
    beat_plan: BeatPlanV2 | None = None
    quality_findings: tuple[AresQualityFindingV2, ...] = ()
    provenance: AresGenerateProvenanceV2
    usage: AresGenerateUsageV2 = Field(default_factory=AresGenerateUsageV2)
    content_digest: DigestStr
    block_reason: NonBlankStr | None = None

    @field_validator("quality_findings", mode="before")
    @classmethod
    def _findings_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _status_payload_rules(self) -> "AresCreateScriptResultV2":
        if self.status == "ok":
            if self.script_package is None or self.beat_plan is None:
                raise ValueError("ok result requires script_package and beat_plan")
            if (
                self.beat_plan.script_package_digest
                != self.script_package.package_digest
            ):
                raise ValueError(
                    "beat_plan.script_package_digest must match "
                    "script_package.package_digest"
                )
            if self.block_reason is not None:
                raise ValueError("ok result must not carry block_reason")
        else:
            if self.script_package is not None or self.beat_plan is not None:
                raise ValueError(
                    f"{self.status} result must not carry script_package/beat_plan"
                )
            if not self.block_reason:
                raise ValueError(f"{self.status} result requires block_reason")
        expected = canonical_contract_digest_v1(self, exclude={"content_digest"})
        if self.content_digest != expected:
            raise ValueError(
                "content_digest does not match AresCreateScriptResultV2 payload"
            )
        return self


def ares_create_script_request_schema_digest() -> str:
    """Stable schema digest for request envelope field shape."""
    schema = {
        "contract_version": "AresCreateScriptRequest.v2",
        "fields": sorted(AresCreateScriptRequestV2.model_fields.keys()),
        "authority_fields": sorted(AresAuthorityV2.model_fields.keys()),
        "identity_fields": sorted(AresIdentitySealedV2.model_fields.keys()),
        "speaker_fields": sorted(AresSpeakerSlotV2.model_fields.keys()),
        "voice_spec_fields": sorted(VoiceSpecV1.model_fields.keys()),
        "product_fields": sorted(AresProductFactsSealedV2.model_fields.keys()),
        "evidence_fields": sorted(AresEvidenceAndClaimsSealedV2.model_fields.keys()),
        "hook_fields": sorted(AresHookDirectiveV2.model_fields.keys()),
        "constraints_fields": sorted(AresCreativeConstraintsV2.model_fields.keys()),
    }
    return sha256_digest(schema)


def ares_create_script_result_schema_digest() -> str:
    """Stable schema digest for result envelope field shape."""
    schema = {
        "contract_version": "AresCreateScriptResult.v2",
        "fields": sorted(AresCreateScriptResultV2.model_fields.keys()),
        "package_fields": sorted(ScriptPackageV2.model_fields.keys()),
        "plan_fields": sorted(BeatPlanV2.model_fields.keys()),
    }
    return sha256_digest(schema)


def request_content_digest(request: AresCreateScriptRequestV2) -> str:
    """Digest of a validated request payload (for provenance binding)."""
    return canonical_contract_digest_v1(request)


__all__ = [
    "AresAuthorityV2",
    "AresSpeakerSlotV2",
    "AresIdentitySealedV2",
    "AresProductFactsSealedV2",
    "AresClaimRefV2",
    "AresEvidenceAndClaimsSealedV2",
    "AresHookDirectiveV2",
    "AresCreativeConstraintsV2",
    "AresCreateScriptRequestV2",
    "ScriptPackageV2",
    "AresBeatRoleIntentV2",
    "BeatPlanV2",
    "AresQualityFindingV2",
    "AresGenerateProvenanceV2",
    "AresGenerateUsageV2",
    "AresCreateScriptResultV2",
    "ares_create_script_request_schema_digest",
    "ares_create_script_result_schema_digest",
    "request_content_digest",
]
