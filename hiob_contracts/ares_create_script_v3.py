"""Ares pure generate V3: producer-issued authority in, semantic script out.

V3 makes the orchestration boundary explicit:

* Star supplies scope and five producer-issued authority references.
* Every input section is byte-bound to its producer reference.
* The Karma p2a receipt is accepted, scope-bound, and canonically digested.
* Ares returns script content and semantic scene intent only.

Athena owns shot, camera, render, and other visual-production decisions. Those
fields do not exist in the V3 output schema and nested models forbid extras.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .ares_create_script_v2 import (
    AresCreativeConstraintsV2,
    AresEvidenceAndClaimsSealedV2,
    AresHookDirectiveV2,
    AresIdentitySealedV2,
    AresSpeakerSlotV2,
    AresProductFactsSealedV2,
)
from .voice_spec_v1 import VoiceSpecV1
from .ares_script_revision_v1 import (
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


_ATHENA_OWNED_OUTPUT_KEYS = frozenset(
    {
        "shot",
        "shottype",
        "shotplan",
        "camera",
        "cameraangle",
        "cameramode",
        "render",
        "rendermode",
        "productionplan",
        "visualplan",
        "visualprompt",
        "personacast",
        "cast",
        "scenedirection",
        "visualcontext",
    }
)


def _normalize_output_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _reject_athena_owned_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _normalize_output_key(str(key)) in _ATHENA_OWNED_OUTPUT_KEYS:
                raise ValueError(f"{path}.{key} is owned by Athena, not Ares")
            _reject_athena_owned_keys(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_athena_owned_keys(item, f"{path}[{index}]")


class AresRequestScopeV3(BaseModel):
    """Caller-owned execution scope; all authority refs must share it."""

    model_config = _FROZEN_STRICT

    workspace_id: NonBlankStr
    run_id: NonBlankStr
    operation_id: NonBlankStr
    idempotency_key: NonBlankStr


def authority_ref_receipt_digest_v3(
    *,
    receipt_id: str,
    producer: str,
    artifact_type: str,
    artifact_digest: str,
    source_output_digest: str,
    payload_digest: str,
    workspace_id: str,
    run_id: str,
) -> str:
    """Canonical issuer-receipt subject for non-p2a authority references.

    The digest does not prove who issued the receipt; consumers still resolve
    ``receipt_id`` against the producer-owned authority store. It prevents the
    reference fields and claimed receipt digest from drifting independently.
    P2A is stronger: its digest binds the embedded canonical Karma receipt.
    """

    return sha256_digest(
        {
            "contract_version": "AresAuthorityArtifactRefReceipt.v3",
            "receipt_id": receipt_id,
            "producer": producer,
            "artifact_type": artifact_type,
            "artifact_digest": artifact_digest,
            "source_output_digest": source_output_digest,
            "payload_digest": payload_digest,
            "workspace_id": workspace_id,
            "run_id": run_id,
        }
    )


class AresAuthorityArtifactRefV3(BaseModel):
    """Opaque producer receipt plus digests binding one authority artifact."""

    model_config = _FROZEN_STRICT

    producer: Literal["parzifal", "janus", "artemis", "metis", "karma"]
    artifact_type: Literal[
        "identity_lock",
        "product_truth",
        "evidence_bundle",
        "hook_directive",
        "p2a_receipt",
    ]
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    payload_digest: DigestStr
    receipt_id: NonBlankStr
    receipt_digest: DigestStr
    workspace_id: NonBlankStr
    run_id: NonBlankStr

    @model_validator(mode="after")
    def _bind_receipt_subject(self) -> "AresAuthorityArtifactRefV3":
        if self.artifact_type == "p2a_receipt":
            return self
        expected = authority_ref_receipt_digest_v3(
            receipt_id=self.receipt_id,
            producer=self.producer,
            artifact_type=self.artifact_type,
            artifact_digest=self.artifact_digest,
            source_output_digest=self.source_output_digest,
            payload_digest=self.payload_digest,
            workspace_id=self.workspace_id,
            run_id=self.run_id,
        )
        if self.receipt_digest != expected:
            raise ValueError(
                "receipt_digest must bind the canonical authority reference"
            )
        return self


class AresP2ATargetProjectionV3(BaseModel):
    """Canonical Karma target projection authorizing one scoped V3 request."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresP2ATargetProjection.v3"]
    scope: AresRequestScopeV3
    command_source_output_digest: DigestStr
    identity_ref: AresAuthorityArtifactRefV3
    product_ref: AresAuthorityArtifactRefV3
    evidence_ref: AresAuthorityArtifactRefV3
    hook_ref: AresAuthorityArtifactRefV3
    creative_constraints: AresCreativeConstraintsV2

    @model_validator(mode="after")
    def _require_authority_owners(self) -> "AresP2ATargetProjectionV3":
        expected = {
            "identity_ref": ("parzifal", "identity_lock"),
            "product_ref": ("janus", "product_truth"),
            "evidence_ref": ("artemis", "evidence_bundle"),
            "hook_ref": ("metis", "hook_directive"),
        }
        for field, (producer, artifact_type) in expected.items():
            ref = getattr(self, field)
            if ref.producer != producer or ref.artifact_type != artifact_type:
                raise ValueError(
                    f"{field} must be issued by {producer} as {artifact_type}"
                )
            if (
                ref.workspace_id != self.scope.workspace_id
                or ref.run_id != self.scope.run_id
            ):
                raise ValueError(f"{field} must match the projection scope")
        return self


def ares_p2a_target_projection_v3(
    *,
    scope: AresRequestScopeV3,
    command_source_output_digest: str,
    identity_ref: AresAuthorityArtifactRefV3,
    product_ref: AresAuthorityArtifactRefV3,
    evidence_ref: AresAuthorityArtifactRefV3,
    hook_ref: AresAuthorityArtifactRefV3,
    creative_constraints: AresCreativeConstraintsV2,
) -> AresP2ATargetProjectionV3:
    """Build the exact non-circular p2a target input authorized by Karma."""

    return AresP2ATargetProjectionV3(
        contract_version="AresP2ATargetProjection.v3",
        scope=scope,
        command_source_output_digest=command_source_output_digest,
        identity_ref=identity_ref,
        product_ref=product_ref,
        evidence_ref=evidence_ref,
        hook_ref=hook_ref,
        creative_constraints=creative_constraints,
    )


def ares_p2a_target_projection_v3_schema_descriptor() -> dict[str, Any]:
    """Canonical cross-language structural schema, including invariants."""

    nonblank = {"type": "string", "minLength": 1, "invariant": "trim_nonblank"}
    digest = {
        "type": "string",
        "pattern": "^sha256:[0-9a-f]{64}$",
    }
    ref_shape = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "producer",
            "artifact_type",
            "artifact_digest",
            "source_output_digest",
            "payload_digest",
            "receipt_id",
            "receipt_digest",
            "workspace_id",
            "run_id",
        ],
        "properties": {
            "producer": {"enum": ["parzifal", "janus", "artemis", "metis", "karma"]},
            "artifact_type": {
                "enum": [
                    "identity_lock",
                    "product_truth",
                    "evidence_bundle",
                    "hook_directive",
                    "p2a_receipt",
                ]
            },
            "artifact_digest": digest,
            "source_output_digest": digest,
            "payload_digest": digest,
            "receipt_id": nonblank,
            "receipt_digest": digest,
            "workspace_id": nonblank,
            "run_id": nonblank,
        },
        "invariants": [
            "receipt_digest=canonical_ref_subject",
            "source_output_digest=producer_planet_output.output_digest",
            "workspace_id/run_id=scope",
        ],
    }
    constraints_shape = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "n_beats",
            "format_mode",
            "style_mode",
            "vertical_mode",
            "goal",
            "fixed_hook",
            "human_instruction",
            "prior_script_package_digest",
            "banned_phrases",
            "required_phrases",
        ],
        "properties": {
            "n_beats": {"type": "integer", "minimum": 1, "maximum": 64},
            "format_mode": {"oneOf": [nonblank, {"type": "null"}]},
            "style_mode": {"oneOf": [nonblank, {"type": "null"}]},
            "vertical_mode": {"oneOf": [nonblank, {"type": "null"}]},
            "goal": {"oneOf": [nonblank, {"type": "null"}]},
            "fixed_hook": {"oneOf": [nonblank, {"type": "null"}]},
            "human_instruction": {"type": "string"},
            "prior_script_package_digest": {"oneOf": [digest, {"type": "null"}]},
            "banned_phrases": {"type": "array", "items": nonblank},
            "required_phrases": {"type": "array", "items": nonblank},
        },
        "invariants": ["all_fields_bound_in_target_input_digest"],
    }
    return {
        "$id": "hiob.AresP2ATargetProjection.v3",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_version",
            "scope",
            "command_source_output_digest",
            "identity_ref",
            "product_ref",
            "evidence_ref",
            "hook_ref",
            "creative_constraints",
        ],
        "properties": {
            "contract_version": {"const": "AresP2ATargetProjection.v3"},
            "scope": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "workspace_id",
                    "run_id",
                    "operation_id",
                    "idempotency_key",
                ],
                "properties": {
                    "workspace_id": nonblank,
                    "run_id": nonblank,
                    "operation_id": nonblank,
                    "idempotency_key": nonblank,
                },
            },
            "command_source_output_digest": digest,
            "identity_ref": ref_shape,
            "product_ref": ref_shape,
            "evidence_ref": ref_shape,
            "hook_ref": ref_shape,
            "creative_constraints": constraints_shape,
        },
        "invariants": [
            "identity_ref=parzifal/identity_lock",
            "product_ref=janus/product_truth",
            "evidence_ref=artemis/evidence_bundle",
            "hook_ref=metis/hook_directive",
            "target_input=canonical_projection",
            "source_output_digests_cover_four_authority_outputs_and_command",
        ],
    }


def ares_p2a_target_projection_v3_schema_digest() -> str:
    return sha256_digest(ares_p2a_target_projection_v3_schema_descriptor())


def _karma_receipt_payload_v3(receipt: KarmaEdgeReceipt) -> dict[str, Any]:
    body = receipt.model_dump(mode="python", exclude={"target_input"})
    body["target_input"] = _json_value(receipt.target_input)
    return _json_value(body)


def karma_receipt_digest_v3(receipt: KarmaEdgeReceipt) -> str:
    return canonical_contract_digest_v1(_karma_receipt_payload_v3(receipt))


class AresAuthorityBundleV3(BaseModel):
    """Five explicit upstream authorities. Star is intentionally not a producer."""

    model_config = _FROZEN_STRICT

    identity_ref: AresAuthorityArtifactRefV3
    product_ref: AresAuthorityArtifactRefV3
    evidence_ref: AresAuthorityArtifactRefV3
    hook_ref: AresAuthorityArtifactRefV3
    p2a_ref: AresAuthorityArtifactRefV3
    accepted_p2a_receipt: KarmaEdgeReceipt

    @field_validator("accepted_p2a_receipt", mode="after")
    @classmethod
    def _freeze_p2a_receipt(cls, receipt: KarmaEdgeReceipt) -> KarmaEdgeReceipt:
        if receipt.target_input is None:
            return receipt
        return receipt.model_copy(
            update={"target_input": _deep_freeze_json(receipt.target_input)}
        )

    @field_serializer("accepted_p2a_receipt", when_used="always")
    def _serialize_p2a_receipt(self, receipt: KarmaEdgeReceipt) -> dict[str, Any]:
        return _karma_receipt_payload_v3(receipt)

    @model_validator(mode="after")
    def _validate_authority_owners_and_p2a(self) -> "AresAuthorityBundleV3":
        expected = {
            "identity_ref": ("parzifal", "identity_lock"),
            "product_ref": ("janus", "product_truth"),
            "evidence_ref": ("artemis", "evidence_bundle"),
            "hook_ref": ("metis", "hook_directive"),
            "p2a_ref": ("karma", "p2a_receipt"),
        }
        for field, (producer, artifact_type) in expected.items():
            ref = getattr(self, field)
            if ref.producer != producer or ref.artifact_type != artifact_type:
                raise ValueError(
                    f"{field} must be issued by {producer} as {artifact_type}"
                )

        receipt = self.accepted_p2a_receipt
        if receipt.edge_id != "p2a":
            raise ValueError("accepted_p2a_receipt.edge_id must be 'p2a'")
        if receipt.decision != "accepted":
            raise ValueError("accepted_p2a_receipt.decision must be 'accepted'")
        if receipt.target_contract.name != "AresP2ATargetProjection":
            raise ValueError(
                "accepted_p2a_receipt.target_contract.name must be "
                "'AresP2ATargetProjection'"
            )
        if receipt.target_contract.version != "v3":
            raise ValueError(
                "accepted_p2a_receipt.target_contract.version must be 'v3'"
            )
        if (
            receipt.target_contract.schema_digest
            != ares_p2a_target_projection_v3_schema_digest()
        ):
            raise ValueError(
                "accepted_p2a_receipt target schema digest must match "
                "AresP2ATargetProjection.v3"
            )
        if receipt.target_input_digest is None:
            raise ValueError("accepted_p2a_receipt requires target_input_digest")
        if self.p2a_ref.receipt_id != receipt.receipt_id:
            raise ValueError("p2a_ref.receipt_id must match Karma receipt")
        expected_receipt_digest = karma_receipt_digest_v3(receipt)
        if self.p2a_ref.receipt_digest != expected_receipt_digest:
            raise ValueError(
                "p2a_ref.receipt_digest must match canonical Karma receipt payload"
            )
        if self.p2a_ref.artifact_digest != receipt.target_input_digest:
            raise ValueError(
                "p2a_ref.artifact_digest must match Karma target_input_digest"
            )
        if self.p2a_ref.payload_digest != receipt.target_input_digest:
            raise ValueError(
                "p2a_ref.payload_digest must match Karma target_input_digest"
            )
        return self


class AresCreateScriptRequestV3(BaseModel):
    """Scoped generate request with externally issued, byte-bound authority."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresCreateScriptRequest.v3"]
    scope: AresRequestScopeV3
    authority: AresAuthorityBundleV3
    identity: AresIdentitySealedV2
    product_facts: AresProductFactsSealedV2
    evidence_and_claims: AresEvidenceAndClaimsSealedV2
    hook_directive: AresHookDirectiveV2
    creative_constraints: AresCreativeConstraintsV2

    @model_validator(mode="after")
    def _bind_scope_authority_and_payloads(self) -> "AresCreateScriptRequestV3":
        refs = (
            self.authority.identity_ref,
            self.authority.product_ref,
            self.authority.evidence_ref,
            self.authority.hook_ref,
            self.authority.p2a_ref,
        )
        for ref in refs:
            if ref.workspace_id != self.scope.workspace_id:
                raise ValueError("authority ref workspace_id must match request scope")
            if ref.run_id != self.scope.run_id:
                raise ValueError("authority ref run_id must match request scope")

        receipt = self.authority.accepted_p2a_receipt
        if receipt.workspace_id != self.scope.workspace_id:
            raise ValueError("Karma receipt workspace_id must match request scope")
        if receipt.run_id != self.scope.run_id:
            raise ValueError("Karma receipt run_id must match request scope")

        receipt_projection = AresP2ATargetProjectionV3.model_validate(
            _json_value(receipt.target_input)
        )
        projection = ares_p2a_target_projection_v3(
            scope=self.scope,
            command_source_output_digest=(
                receipt_projection.command_source_output_digest
            ),
            identity_ref=self.authority.identity_ref,
            product_ref=self.authority.product_ref,
            evidence_ref=self.authority.evidence_ref,
            hook_ref=self.authority.hook_ref,
            creative_constraints=self.creative_constraints,
        )
        projection_payload = projection.model_dump(mode="json")
        projection_digest = sha256_digest(projection_payload)
        if _json_value(receipt.target_input) != projection_payload:
            raise ValueError(
                "Karma receipt target_input must equal canonical "
                "AresP2ATargetProjection.v3"
            )
        if receipt.target_input_digest != projection_digest:
            raise ValueError(
                "Karma receipt target_input_digest must bind canonical "
                "AresP2ATargetProjection.v3"
            )
        if (
            self.authority.p2a_ref.artifact_digest != projection_digest
            or self.authority.p2a_ref.payload_digest != projection_digest
        ):
            raise ValueError(
                "p2a_ref digests must bind canonical AresP2ATargetProjection.v3"
            )
        source_digests = set(receipt.source_output_digests)
        required_sources = {
            self.authority.identity_ref.source_output_digest,
            self.authority.product_ref.source_output_digest,
            self.authority.evidence_ref.source_output_digest,
            self.authority.hook_ref.source_output_digest,
            projection.command_source_output_digest,
        }
        if not required_sources.issubset(source_digests):
            raise ValueError(
                "Karma receipt source_output_digests must cover four authority "
                "outputs and the Star command output"
            )

        bindings = (
            (
                self.authority.identity_ref,
                self.identity,
                self.identity.identity_lock_digest,
                "identity_ref",
            ),
            (
                self.authority.product_ref,
                self.product_facts,
                self.product_facts.product_truth_digest,
                "product_ref",
            ),
            (
                self.authority.evidence_ref,
                self.evidence_and_claims,
                self.evidence_and_claims.evidence_bundle_digest,
                "evidence_ref",
            ),
            (
                self.authority.hook_ref,
                self.hook_directive,
                self.hook_directive.directive_digest,
                "hook_ref",
            ),
        )
        for ref, payload, artifact_digest, field in bindings:
            if ref.artifact_digest != artifact_digest:
                raise ValueError(
                    f"{field}.artifact_digest must match sealed artifact digest"
                )
            expected_payload_digest = sha256_digest(payload.model_dump(mode="json"))
            if ref.payload_digest != expected_payload_digest:
                raise ValueError(f"{field}.payload_digest must match sealed payload")
        return self


class ScriptPackageV3(BaseModel):
    """Pure script content without persistence, approval, or job identifiers."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresScriptPackage.v3"]
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
        _reject_athena_owned_keys(value, "master_sales_script")
        return _deep_freeze_json(value)

    @field_validator("pronunciation_overrides", mode="after")
    @classmethod
    def _freeze_pronunciation(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _FrozenMapping(dict(value))

    @field_serializer(
        "master_sales_script", "pronunciation_overrides", when_used="always"
    )
    def _serialize_frozen_mappings(self, value: Mapping[str, Any]) -> dict:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_content(self) -> "ScriptPackageV3":
        count = len(self.voice_script)
        if count == 0:
            raise ValueError("voice_script must contain at least one segment")
        if len(self.caption_script) != count:
            raise ValueError("voice_script and caption_script must have equal length")
        expected = list(range(count))
        if [item.beat_index for item in self.voice_script] != expected:
            raise ValueError("voice_script beat indices must be exactly 0..N-1")
        if [item.beat_index for item in self.caption_script] != expected:
            raise ValueError("caption_script beat indices must be exactly 0..N-1")
        if any(not item.text.strip() for item in self.voice_script):
            raise ValueError("voice_script segments must contain non-empty dialogue")
        master_beats = self.master_sales_script.get("beats")
        if not isinstance(master_beats, (list, tuple)):
            raise ValueError("master_sales_script.beats must be a canonical beat array")
        if len(master_beats) != count:
            raise ValueError(
                "master_sales_script.beats must match script segment count"
            )
        for index, beat in enumerate(master_beats):
            if not isinstance(beat, Mapping):
                raise ValueError("master_sales_script beats must be JSON objects")
            if beat.get("beat_index") != index:
                raise ValueError(
                    "master_sales_script beat indices must be exactly 0..N-1"
                )
            if beat.get("text") != self.voice_script[index].text:
                raise ValueError(
                    "master_sales_script beat text must match voice_script"
                )
            if beat.get("caption") != self.caption_script[index].text:
                raise ValueError(
                    "master_sales_script beat caption must match caption_script"
                )
        if self.package_digest != canonical_contract_digest_v1(
            self, exclude={"package_digest"}
        ):
            raise ValueError("package_digest does not match ScriptPackageV3 payload")
        return self


class AresSemanticBeatV3(BaseModel):
    """One semantic beat; Athena remains sole owner of visual grammar."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    text: NonBlankStr
    caption: str = ""
    scene_intent: NonBlankStr
    role_intents: tuple[NonBlankStr, ...] = Field(min_length=1)

    @field_validator("role_intents", mode="before")
    @classmethod
    def _roles_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value


class SemanticBeatPlanV3(BaseModel):
    """Semantic beat order bound to a script package, with no visual plan."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresSemanticBeatPlan.v3"]
    script_package_digest: DigestStr
    beats: tuple[AresSemanticBeatV3, ...] = Field(min_length=1)
    plan_digest: DigestStr

    @field_validator("beats", mode="before")
    @classmethod
    def _beats_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_content(self) -> "SemanticBeatPlanV3":
        indices = [beat.beat_index for beat in self.beats]
        if indices != list(range(len(indices))):
            raise ValueError("semantic beat indices must be exactly 0..N-1")
        if self.plan_digest != canonical_contract_digest_v1(
            self, exclude={"plan_digest"}
        ):
            raise ValueError("plan_digest does not match SemanticBeatPlanV3 payload")
        return self


class AresQualityFindingV3(BaseModel):
    model_config = _FROZEN_STRICT

    code: NonBlankStr
    severity: Literal["info", "warn", "error"]
    message: NonBlankStr
    beat_index: NonNegativeInt | None = None
    gate: NonBlankStr | None = None


class AresGenerateProvenanceV3(BaseModel):
    model_config = _FROZEN_STRICT

    producer: Literal["ares"] = "ares"
    contract_version: Literal["AresCreateScriptResult.v3"] = "AresCreateScriptResult.v3"
    request_content_digest: DigestStr
    model_id: NonBlankStr | None = None
    prompt_digest: DigestStr | None = None
    produced_at: UtcTimestamp | None = None


class AresGenerateUsageV3(BaseModel):
    model_config = _FROZEN_STRICT

    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    cost_cents: NonNegativeInt = 0
    model_id: NonBlankStr | None = None


class AresCreateScriptResultV3(BaseModel):
    """Ares result: script package plus semantic plan, never a render plan."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresCreateScriptResult.v3"]
    status: Literal["ok", "blocked", "needs_human"] = "ok"
    script_package: ScriptPackageV3 | None = None
    semantic_beat_plan: SemanticBeatPlanV3 | None = None
    quality_findings: tuple[AresQualityFindingV3, ...] = ()
    provenance: AresGenerateProvenanceV3
    usage: AresGenerateUsageV3 = Field(default_factory=AresGenerateUsageV3)
    content_digest: DigestStr
    block_reason: NonBlankStr | None = None

    @field_validator("quality_findings", mode="before")
    @classmethod
    def _findings_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_status_and_content(self) -> "AresCreateScriptResultV3":
        if self.status == "ok":
            if self.script_package is None or self.semantic_beat_plan is None:
                raise ValueError(
                    "ok result requires script_package and semantic_beat_plan"
                )
            if (
                self.semantic_beat_plan.script_package_digest
                != self.script_package.package_digest
            ):
                raise ValueError(
                    "semantic_beat_plan.script_package_digest must match "
                    "script_package.package_digest"
                )
            if len(self.semantic_beat_plan.beats) != len(
                self.script_package.voice_script
            ):
                raise ValueError(
                    "semantic beat count must match script package segments"
                )
            for index, beat in enumerate(self.semantic_beat_plan.beats):
                if beat.text != self.script_package.voice_script[index].text:
                    raise ValueError("semantic beat text must match voice_script")
                if beat.caption != self.script_package.caption_script[index].text:
                    raise ValueError("semantic beat caption must match caption_script")
            if self.block_reason is not None:
                raise ValueError("ok result must not carry block_reason")
        else:
            if self.script_package is not None or self.semantic_beat_plan is not None:
                raise ValueError(
                    f"{self.status} result must not carry generated artifacts"
                )
            if not self.block_reason:
                raise ValueError(f"{self.status} result requires block_reason")
        if self.content_digest != canonical_contract_digest_v1(
            self, exclude={"content_digest"}
        ):
            raise ValueError(
                "content_digest does not match AresCreateScriptResultV3 payload"
            )
        return self


def ares_create_script_request_v3_schema_digest() -> str:
    schema = {
        "contract_version": "AresCreateScriptRequest.v3",
        "fields": sorted(AresCreateScriptRequestV3.model_fields),
        "scope_fields": sorted(AresRequestScopeV3.model_fields),
        "authority_fields": sorted(AresAuthorityBundleV3.model_fields),
        "authority_ref_fields": sorted(AresAuthorityArtifactRefV3.model_fields),
        "identity_fields": sorted(AresIdentitySealedV2.model_fields),
        "speaker_fields": sorted(AresSpeakerSlotV2.model_fields),
        "voice_spec_fields": sorted(VoiceSpecV1.model_fields),
        "product_fields": sorted(AresProductFactsSealedV2.model_fields),
        "evidence_fields": sorted(AresEvidenceAndClaimsSealedV2.model_fields),
        "hook_fields": sorted(AresHookDirectiveV2.model_fields),
        "constraints_fields": sorted(AresCreativeConstraintsV2.model_fields),
    }
    return sha256_digest(schema)


def ares_create_script_result_v3_schema_digest() -> str:
    schema = {
        "contract_version": "AresCreateScriptResult.v3",
        "fields": sorted(AresCreateScriptResultV3.model_fields),
        "package_fields": sorted(ScriptPackageV3.model_fields),
        "semantic_plan_fields": sorted(SemanticBeatPlanV3.model_fields),
        "semantic_beat_fields": sorted(AresSemanticBeatV3.model_fields),
    }
    return sha256_digest(schema)


def request_content_digest_v3(request: AresCreateScriptRequestV3) -> str:
    return canonical_contract_digest_v1(request)


__all__ = [
    "AresRequestScopeV3",
    "authority_ref_receipt_digest_v3",
    "AresAuthorityArtifactRefV3",
    "AresP2ATargetProjectionV3",
    "ares_p2a_target_projection_v3",
    "ares_p2a_target_projection_v3_schema_descriptor",
    "ares_p2a_target_projection_v3_schema_digest",
    "karma_receipt_digest_v3",
    "AresAuthorityBundleV3",
    "AresCreateScriptRequestV3",
    "ScriptPackageV3",
    "AresSemanticBeatV3",
    "SemanticBeatPlanV3",
    "AresQualityFindingV3",
    "AresGenerateProvenanceV3",
    "AresGenerateUsageV3",
    "AresCreateScriptResultV3",
    "ares_create_script_request_v3_schema_digest",
    "ares_create_script_result_v3_schema_digest",
    "request_content_digest_v3",
]
