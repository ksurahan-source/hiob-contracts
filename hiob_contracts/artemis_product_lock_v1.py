"""Luna-simple Artemis I/O: observations -> draft -> approval -> lock."""
from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Protocol

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .factory.digest import assert_digest, sha256_digest


_CONFIG = ConfigDict(
    frozen=True,
    extra="forbid",
    strict=True,
    revalidate_instances="always",
)
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("string must not be blank")
    return value


def _opaque(value: str) -> str:
    segments = value.split("/")
    if (
        not _OPAQUE_ID.fullmatch(value)
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise ValueError("technical id must use the opaque id grammar")
    return value


def _digest(value: str) -> str:
    return assert_digest(value)


Text = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_non_blank)]
OpaqueId = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_opaque)]
DigestStr = Annotated[str, AfterValidator(_digest)]
ObservationKind = Literal["product_fact", "forbidden_claim", "social_proof"]
ClaimKind = Literal["product_fact", "social_proof"]
BlockCode = Literal[
    "APPROVAL_INVALID",
    "SCOPE_MISMATCH",
    "SOURCE_STALE",
    "DIGEST_MISMATCH",
    "PRODUCT_LOCK_INCOMPLETE",
    "NO_APPROVED_EVIDENCE",
]


class _StrictModel(BaseModel):
    model_config = _CONFIG


class ObservationProvenanceV1(_StrictModel):
    source_record_id: OpaqueId
    quote: Text


class _EvidenceItem(_StrictModel):
    evidence_artifact_id: OpaqueId
    evidence_sha256: DigestStr
    provenance: ObservationProvenanceV1


class JanusProductObservationV1(_EvidenceItem):
    """Observed source atom. It is evidence, not an approved claim."""

    observation_id: OpaqueId
    kind: ObservationKind
    text: Text

    def fingerprint(self) -> tuple[str, ...]:
        return (
            self.kind,
            self.text,
            self.evidence_sha256,
            self.provenance.source_record_id,
            self.provenance.quote,
        )


class _ProductScope(_StrictModel):
    workspace_id: OpaqueId
    run_id: OpaqueId
    brand_slug: OpaqueId
    listing_slug: OpaqueId
    product_id: OpaqueId
    product_name: Text
    product_image_artifact_id: OpaqueId
    product_image_sha256: DigestStr


class _JanusObservationsContent(_ProductScope):
    contract_version: Literal["JanusProductObservations.v1"] = (
        "JanusProductObservations.v1"
    )
    observations: tuple[JanusProductObservationV1, ...] = Field(min_length=1)

    @field_validator("observations", mode="before")
    @classmethod
    def _to_observations(cls, value: Any) -> Any:
        if isinstance(value, list):
            return tuple(
                item
                if isinstance(item, JanusProductObservationV1)
                else JanusProductObservationV1.model_validate(item)
                for item in value
            )
        return value

    @model_validator(mode="after")
    def _unique_observations(self) -> "_JanusObservationsContent":
        ids = [item.observation_id for item in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("observations observation_id values must be unique")
        fingerprints = [item.fingerprint() for item in self.observations]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("duplicate observation content is forbidden")
        return self


class JanusProductObservationsV1(_JanusObservationsContent):
    """Immutable source material owned by Janus."""

    observations_digest: DigestStr

    @model_validator(mode="after")
    def _valid_digest(self) -> "JanusProductObservationsV1":
        _require_digest(self, "observations_digest")
        return self

    @classmethod
    def build(cls, **values: Any) -> "JanusProductObservationsV1":
        content = _JanusObservationsContent.model_validate(
            _without(values, "observations_digest")
        )
        payload = content.model_dump(mode="json")
        return cls(**payload, observations_digest=sha256_digest(payload))


class ArtemisCompileRequestV1(_StrictModel):
    contract_version: Literal["ArtemisCompileRequest.v1"] = (
        "ArtemisCompileRequest.v1"
    )
    observations: JanusProductObservationsV1
    request_digest: DigestStr

    @model_validator(mode="after")
    def _valid_digest(self) -> "ArtemisCompileRequestV1":
        _require_digest(self, "request_digest")
        return self

    @classmethod
    def build(
        cls,
        *,
        observations: JanusProductObservationsV1,
    ) -> "ArtemisCompileRequestV1":
        payload = {
            "contract_version": "ArtemisCompileRequest.v1",
            "observations": observations.model_dump(mode="json"),
        }
        return cls(**payload, request_digest=sha256_digest(payload))


class ArtemisClaimV1(_EvidenceItem):
    """Claim owned by Artemis and grounded in Janus observations."""

    claim_id: OpaqueId
    text: Text
    kind: ClaimKind
    source_observation_ids: tuple[OpaqueId, ...] = Field(
        min_length=1,
        max_length=1,
    )

    @field_validator("source_observation_ids", mode="before")
    @classmethod
    def _to_source_ids(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _unique_sources(self) -> "ArtemisClaimV1":
        if len(self.source_observation_ids) != len(set(self.source_observation_ids)):
            raise ValueError("source_observation_ids must be unique")
        return self

    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.text,
            self.kind,
            tuple(sorted(self.source_observation_ids)),
            self.evidence_sha256,
            self.provenance.source_record_id,
            self.provenance.quote,
        )


class _ProductLockDraftContent(_ProductScope):
    contract_version: Literal["ProductElementLockDraft.v1"] = (
        "ProductElementLockDraft.v1"
    )
    claims: tuple[ArtemisClaimV1, ...] = Field(min_length=1)
    forbidden_claims: tuple[Text, ...] = ()
    source_observations_digest: DigestStr
    compile_request_digest: DigestStr

    @field_validator("claims", mode="before")
    @classmethod
    def _to_claims(cls, value: Any) -> Any:
        if isinstance(value, list):
            return tuple(
                item
                if isinstance(item, ArtemisClaimV1)
                else ArtemisClaimV1.model_validate(item)
                for item in value
            )
        return value

    @field_validator("forbidden_claims", mode="before")
    @classmethod
    def _to_forbidden(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _unique_content(self) -> "_ProductLockDraftContent":
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claims claim_id values must be unique")
        fingerprints = [claim.fingerprint() for claim in self.claims]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("duplicate claim content is forbidden")
        if len(self.forbidden_claims) != len(set(self.forbidden_claims)):
            raise ValueError("duplicate forbidden_claims are forbidden")
        return self


class ProductElementLockDraftV1(_ProductLockDraftContent):
    """Reviewable product understanding with no approval authority."""

    draft_digest: DigestStr

    @model_validator(mode="after")
    def _valid_digest(self) -> "ProductElementLockDraftV1":
        _require_digest(self, "draft_digest")
        return self

    @classmethod
    def build(cls, **values: Any) -> "ProductElementLockDraftV1":
        content = _ProductLockDraftContent.model_validate(
            _without(values, "draft_digest")
        )
        payload = content.model_dump(mode="json")
        return cls(**payload, draft_digest=sha256_digest(payload))


class ArtemisCompileResultV1(_StrictModel):
    contract_version: Literal["ArtemisCompileResult.v1"] = (
        "ArtemisCompileResult.v1"
    )
    status: Literal["compiled", "blocked"]
    request_digest: DigestStr
    draft: ProductElementLockDraftV1 | None = None
    error_code: BlockCode | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> "ArtemisCompileResultV1":
        _require_result_shape(self.status, self.draft, self.error_code, "compiled")
        if (
            self.draft is not None
            and self.draft.compile_request_digest != self.request_digest
        ):
            raise ValueError("draft compile_request_digest must match result")
        return self

    @classmethod
    def compiled(
        cls,
        request: ArtemisCompileRequestV1,
        draft: ProductElementLockDraftV1,
    ) -> "ArtemisCompileResultV1":
        if not _draft_is_grounded_in(request, draft):
            raise ValueError("draft claims are not grounded in compile request")
        return cls(
            status="compiled",
            request_digest=request.request_digest,
            draft=draft,
        )

    @classmethod
    def blocked(
        cls,
        request_digest: str,
        error_code: BlockCode,
    ) -> "ArtemisCompileResultV1":
        return cls(
            status="blocked",
            request_digest=request_digest,
            error_code=error_code,
        )


class ArtemisApprovalResolverV1(Protocol):
    """Durable Star authority required before Artemis may seal."""

    def is_current_approval(
        self,
        *,
        receipt_id: str,
        receipt_digest: str,
        workspace_id: str,
        run_id: str,
        listing_slug: str,
        product_id: str,
        compile_request_digest: str,
        draft_digest: str,
        approver_account_id: str,
        state_revision: int,
    ) -> bool: ...


class _ApprovalReceiptContent(_StrictModel):
    contract_version: Literal["ArtemisApprovalReceipt.v1"] = (
        "ArtemisApprovalReceipt.v1"
    )
    receipt_id: OpaqueId
    workspace_id: OpaqueId
    run_id: OpaqueId
    listing_slug: OpaqueId
    product_id: OpaqueId
    compile_request_digest: DigestStr
    draft_digest: DigestStr
    approver_account_id: OpaqueId
    decision: Literal["approved"] = "approved"
    state_revision: int = Field(ge=1, le=9_007_199_254_740_991)


class ArtemisApprovalReceiptV1(_ApprovalReceiptContent):
    """Approval evidence. It authorizes only through a durable resolver."""

    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _valid_digest(self) -> "ArtemisApprovalReceiptV1":
        _require_digest(self, "receipt_digest")
        return self

    @classmethod
    def build(
        cls,
        *,
        receipt_id: str,
        draft: ProductElementLockDraftV1,
        approver_account_id: str,
        state_revision: int,
    ) -> "ArtemisApprovalReceiptV1":
        content = _ApprovalReceiptContent(
            receipt_id=receipt_id,
            workspace_id=draft.workspace_id,
            run_id=draft.run_id,
            listing_slug=draft.listing_slug,
            product_id=draft.product_id,
            compile_request_digest=draft.compile_request_digest,
            draft_digest=draft.draft_digest,
            approver_account_id=approver_account_id,
            state_revision=state_revision,
        )
        payload = content.model_dump(mode="json")
        return cls(**payload, receipt_digest=sha256_digest(payload))

    def structurally_binds(self, draft: ProductElementLockDraftV1) -> bool:
        return (
            self.receipt_digest
            == sha256_digest(
                self.model_dump(mode="json", exclude={"receipt_digest"})
            )
            and self.workspace_id == draft.workspace_id
            and self.run_id == draft.run_id
            and self.listing_slug == draft.listing_slug
            and self.product_id == draft.product_id
            and self.compile_request_digest == draft.compile_request_digest
            and self.draft_digest == draft.draft_digest
        )

    def authorizes(
        self,
        draft: ProductElementLockDraftV1,
        *,
        resolver: ArtemisApprovalResolverV1,
    ) -> bool:
        if not self.structurally_binds(draft):
            return False
        return resolver.is_current_approval(
            receipt_id=self.receipt_id,
            receipt_digest=self.receipt_digest,
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            listing_slug=self.listing_slug,
            product_id=self.product_id,
            compile_request_digest=self.compile_request_digest,
            draft_digest=self.draft_digest,
            approver_account_id=self.approver_account_id,
            state_revision=self.state_revision,
        ) is True


class _SealRequestContent(_StrictModel):
    contract_version: Literal["ArtemisSealRequest.v1"] = "ArtemisSealRequest.v1"
    draft: ProductElementLockDraftV1
    approval_receipt: ArtemisApprovalReceiptV1

    @model_validator(mode="after")
    def _bind_receipt(self) -> "_SealRequestContent":
        if not self.approval_receipt.structurally_binds(self.draft):
            raise ValueError("approval receipt does not bind draft")
        return self


class ArtemisSealRequestV1(_SealRequestContent):
    request_digest: DigestStr

    @model_validator(mode="after")
    def _valid_digest(self) -> "ArtemisSealRequestV1":
        _require_digest(self, "request_digest")
        return self

    @classmethod
    def build(
        cls,
        *,
        draft: ProductElementLockDraftV1,
        approval_receipt: ArtemisApprovalReceiptV1,
    ) -> "ArtemisSealRequestV1":
        content = _SealRequestContent(
            draft=draft,
            approval_receipt=approval_receipt,
        )
        payload = content.model_dump(mode="json")
        return cls(**payload, request_digest=sha256_digest(payload))

    def authorizes(self, *, resolver: ArtemisApprovalResolverV1) -> bool:
        return self.approval_receipt.authorizes(
            self.draft,
            resolver=resolver,
        )


class ProductElementLockV1(_ProductLockDraftContent):
    """Approved immutable lock that preserves its approval evidence."""

    contract_version: Literal["ProductElementLock.v1"] = "ProductElementLock.v1"
    draft_digest: DigestStr
    approval_receipt: ArtemisApprovalReceiptV1
    lock_digest: DigestStr

    @model_validator(mode="after")
    def _valid(self) -> "ProductElementLockV1":
        draft = self._reconstructed_draft()
        if not self.approval_receipt.structurally_binds(draft):
            raise ValueError("approval receipt does not bind product element lock")
        _require_digest(self, "lock_digest")
        return self

    def _reconstructed_draft(self) -> ProductElementLockDraftV1:
        payload = self.model_dump(
            mode="json",
            include=set(_ProductLockDraftContent.model_fields),
        )
        payload["contract_version"] = "ProductElementLockDraft.v1"
        return ProductElementLockDraftV1(
            **payload,
            draft_digest=self.draft_digest,
        )

    @classmethod
    def from_verified(
        cls,
        request: ArtemisSealRequestV1,
        *,
        resolver: ArtemisApprovalResolverV1,
    ) -> "ProductElementLockV1":
        if not request.authorizes(resolver=resolver):
            raise ValueError("approval receipt is not current")
        payload = request.draft.model_dump(
            mode="json",
            exclude={"contract_version"},
        )
        payload.update(
            contract_version="ProductElementLock.v1",
            approval_receipt=request.approval_receipt.model_dump(mode="json"),
        )
        return cls(**payload, lock_digest=sha256_digest(payload))

    def authorizes(self, *, resolver: ArtemisApprovalResolverV1) -> bool:
        return self.approval_receipt.authorizes(
            self._reconstructed_draft(),
            resolver=resolver,
        )


class ArtemisSealResultV1(_StrictModel):
    contract_version: Literal["ArtemisSealResult.v1"] = "ArtemisSealResult.v1"
    status: Literal["sealed", "blocked"]
    request_digest: DigestStr
    lock: ProductElementLockV1 | None = None
    error_code: BlockCode | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> "ArtemisSealResultV1":
        _require_result_shape(self.status, self.lock, self.error_code, "sealed")
        if self.lock is not None:
            reconstructed = ArtemisSealRequestV1.build(
                draft=self.lock._reconstructed_draft(),
                approval_receipt=self.lock.approval_receipt,
            )
            if reconstructed.request_digest != self.request_digest:
                raise ValueError("sealed result does not bind seal request")
        return self

    @classmethod
    def sealed(
        cls,
        request: ArtemisSealRequestV1,
        *,
        resolver: ArtemisApprovalResolverV1,
    ) -> "ArtemisSealResultV1":
        lock = ProductElementLockV1.from_verified(
            request,
            resolver=resolver,
        )
        return cls(
            status="sealed",
            request_digest=request.request_digest,
            lock=lock,
        )

    @classmethod
    def blocked(
        cls,
        request_digest: str,
        error_code: BlockCode,
    ) -> "ArtemisSealResultV1":
        return cls(
            status="blocked",
            request_digest=request_digest,
            error_code=error_code,
        )

    def authorizes(
        self,
        request: ArtemisSealRequestV1,
        *,
        resolver: ArtemisApprovalResolverV1,
    ) -> bool:
        if (
            self.status != "sealed"
            or self.lock is None
            or self.request_digest != request.request_digest
        ):
            return False
        reconstructed = ArtemisSealRequestV1.build(
            draft=self.lock._reconstructed_draft(),
            approval_receipt=self.lock.approval_receipt,
        )
        return reconstructed == request and request.authorizes(resolver=resolver)


def _without(values: dict[str, Any], *keys: str) -> dict[str, Any]:
    result = dict(values)
    for key in keys:
        result.pop(key, None)
    return result


def _require_digest(model: BaseModel, field: str) -> None:
    expected = sha256_digest(model.model_dump(mode="json", exclude={field}))
    if getattr(model, field) != expected:
        raise ValueError(f"{field} does not match payload")


def _require_result_shape(
    status: str,
    value: object | None,
    error_code: str | None,
    success: str,
) -> None:
    if status == success and (value is None or error_code is not None):
        raise ValueError(f"{success} result requires only its value")
    if status == "blocked" and (value is not None or error_code is None):
        raise ValueError("blocked result requires only error_code")


def _draft_is_grounded_in(
    request: ArtemisCompileRequestV1,
    draft: ProductElementLockDraftV1,
) -> bool:
    source = request.observations
    if (
        draft.compile_request_digest != request.request_digest
        or draft.source_observations_digest != source.observations_digest
        or (
            draft.workspace_id,
            draft.run_id,
            draft.brand_slug,
            draft.listing_slug,
            draft.product_id,
            draft.product_name,
            draft.product_image_artifact_id,
            draft.product_image_sha256,
        )
        != (
            source.workspace_id,
            source.run_id,
            source.brand_slug,
            source.listing_slug,
            source.product_id,
            source.product_name,
            source.product_image_artifact_id,
            source.product_image_sha256,
        )
    ):
        return False
    observations = {
        item.observation_id: item for item in source.observations
    }
    used_observation_ids: set[str] = set()
    for claim in draft.claims:
        observation_id = claim.source_observation_ids[0]
        item = observations.get(observation_id)
        if item is None or observation_id in used_observation_ids:
            return False
        used_observation_ids.add(observation_id)
        if not (
            item.kind == claim.kind
            and item.text == claim.text
            and item.evidence_artifact_id == claim.evidence_artifact_id
            and item.evidence_sha256 == claim.evidence_sha256
            and item.provenance == claim.provenance
        ):
            return False
    required_claim_ids = {
        item.observation_id
        for item in source.observations
        if item.kind in {"product_fact", "social_proof"}
    }
    if used_observation_ids != required_claim_ids:
        return False
    expected_forbidden: list[str] = []
    for item in source.observations:
        if item.kind == "forbidden_claim" and item.text not in expected_forbidden:
            expected_forbidden.append(item.text)
    return draft.forbidden_claims == tuple(expected_forbidden)


__all__ = [
    "ArtemisApprovalReceiptV1",
    "ArtemisApprovalResolverV1",
    "ArtemisClaimV1",
    "ArtemisCompileRequestV1",
    "ArtemisCompileResultV1",
    "ArtemisSealRequestV1",
    "ArtemisSealResultV1",
    "JanusProductObservationV1",
    "JanusProductObservationsV1",
    "ObservationProvenanceV1",
    "ProductElementLockDraftV1",
    "ProductElementLockV1",
]
