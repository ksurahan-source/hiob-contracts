"""Luna-simple Artemis I/O: observations -> draft -> approved lock."""
from __future__ import annotations

from typing import Annotated, Any, Literal

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
_URL_PREFIXES = ("http://", "https://", "data:", "file:")


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("string must not be blank")
    return value


def _opaque(value: str) -> str:
    value = _non_blank(value)
    if value.lower().startswith(_URL_PREFIXES):
        raise ValueError("artifact and record ids must be opaque, not a URL")
    return value


def _digest(value: str) -> str:
    return assert_digest(value)


Text = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_non_blank)]
OpaqueId = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_opaque)]
DigestStr = Annotated[str, AfterValidator(_digest)]
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
    """Observed source atom. It is not an approved claim."""

    observation_id: OpaqueId
    kind: Text
    text: Text


class _ProductScope(_StrictModel):
    workspace_id: Text
    run_id: Text
    brand_slug: Text
    listing_slug: Text
    product_id: Text
    product_name: Text
    product_image_artifact_id: OpaqueId
    product_image_sha256: DigestStr


class JanusProductObservationsV1(_ProductScope):
    """Immutable source material owned by Janus."""

    contract_version: Literal["JanusProductObservations.v1"] = (
        "JanusProductObservations.v1"
    )
    observations: tuple[JanusProductObservationV1, ...] = Field(min_length=1)
    observations_digest: DigestStr

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
    def _valid(self) -> "JanusProductObservationsV1":
        ids = [item.observation_id for item in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("observations observation_id values must be unique")
        _require_digest(self, "observations_digest")
        return self

    @classmethod
    def build(cls, **values: Any) -> "JanusProductObservationsV1":
        payload = _without(values, "contract_version", "observations_digest")
        payload["contract_version"] = "JanusProductObservations.v1"
        payload["observations"] = [
            (
                item
                if isinstance(item, JanusProductObservationV1)
                else JanusProductObservationV1.model_validate(item)
            ).model_dump(mode="json")
            for item in payload.get("observations", ())
        ]
        return cls(**payload, observations_digest=sha256_digest(payload))


class ArtemisCompileRequestV1(_StrictModel):
    contract_version: Literal["ArtemisCompileRequest.v1"] = (
        "ArtemisCompileRequest.v1"
    )
    observations: JanusProductObservationsV1
    request_digest: DigestStr

    @model_validator(mode="after")
    def _valid(self) -> "ArtemisCompileRequestV1":
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
    kind: Text
    source_observation_ids: tuple[OpaqueId, ...] = Field(min_length=1)

    @field_validator("source_observation_ids", mode="before")
    @classmethod
    def _to_source_ids(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _unique_sources(self) -> "ArtemisClaimV1":
        if len(self.source_observation_ids) != len(set(self.source_observation_ids)):
            raise ValueError("source_observation_ids must be unique")
        return self


class _ProductLockContent(_ProductScope):
    claims: tuple[ArtemisClaimV1, ...] = Field(min_length=1)
    forbidden_claims: tuple[Text, ...] = ()
    source_observations_digest: DigestStr

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
    def _unique_claims(self) -> "_ProductLockContent":
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claims claim_id values must be unique")
        return self


class ProductElementLockDraftV1(_ProductLockContent):
    contract_version: Literal["ProductElementLockDraft.v1"] = (
        "ProductElementLockDraft.v1"
    )
    draft_digest: DigestStr

    @model_validator(mode="after")
    def _valid(self) -> "ProductElementLockDraftV1":
        _require_digest(self, "draft_digest")
        return self

    @classmethod
    def build(cls, **values: Any) -> "ProductElementLockDraftV1":
        payload = _without(values, "contract_version", "draft_digest")
        payload["contract_version"] = "ProductElementLockDraft.v1"
        payload["claims"] = [
            (
                item
                if isinstance(item, ArtemisClaimV1)
                else ArtemisClaimV1.model_validate(item)
            ).model_dump(mode="json")
            for item in payload.get("claims", ())
        ]
        payload["forbidden_claims"] = list(payload.get("forbidden_claims", ()))
        return cls(**payload, draft_digest=sha256_digest(payload))


class ArtemisCompileResultV1(_StrictModel):
    contract_version: Literal["ArtemisCompileResult.v1"] = (
        "ArtemisCompileResult.v1"
    )
    status: Literal["compiled", "blocked"]
    draft: ProductElementLockDraftV1 | None = None
    error_code: BlockCode | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> "ArtemisCompileResultV1":
        _require_result_shape(self.status, self.draft, self.error_code, "compiled")
        return self

    @classmethod
    def compiled(cls, draft: ProductElementLockDraftV1) -> "ArtemisCompileResultV1":
        return cls(status="compiled", draft=draft)

    @classmethod
    def blocked(cls, error_code: BlockCode) -> "ArtemisCompileResultV1":
        return cls(status="blocked", error_code=error_code)


def approval_subject_v1(
    *,
    workspace_id: str,
    run_id: str,
    listing_slug: str,
    draft_digest: str,
    approved_by: str,
) -> dict[str, str]:
    return {
        "contract_version": "ArtemisProductLockApproval.v1",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "listing_slug": listing_slug,
        "draft_digest": draft_digest,
        "approved_by": approved_by,
    }


class ArtemisSealRequestV1(_StrictModel):
    contract_version: Literal["ArtemisSealRequest.v1"] = "ArtemisSealRequest.v1"
    workspace_id: Text
    run_id: Text
    listing_slug: Text
    draft: ProductElementLockDraftV1
    approved_by: Text
    approval_digest: DigestStr
    request_digest: DigestStr

    @model_validator(mode="after")
    def _valid(self) -> "ArtemisSealRequestV1":
        if (self.workspace_id, self.run_id, self.listing_slug) != (
            self.draft.workspace_id,
            self.draft.run_id,
            self.draft.listing_slug,
        ):
            raise ValueError("seal request scope must equal draft scope")
        if self.approval_digest != sha256_digest(
            approval_subject_v1(
                workspace_id=self.workspace_id,
                run_id=self.run_id,
                listing_slug=self.listing_slug,
                draft_digest=self.draft.draft_digest,
                approved_by=self.approved_by,
            )
        ):
            raise ValueError("approval_digest does not match approved draft")
        _require_digest(self, "request_digest")
        return self

    @classmethod
    def build(cls, **values: Any) -> "ArtemisSealRequestV1":
        draft = values["draft"]
        approval = approval_subject_v1(
            workspace_id=values["workspace_id"],
            run_id=values["run_id"],
            listing_slug=values["listing_slug"],
            draft_digest=draft.draft_digest,
            approved_by=values["approved_by"],
        )
        payload = {
            "contract_version": "ArtemisSealRequest.v1",
            **values,
            "draft": draft.model_dump(mode="json"),
            "approval_digest": sha256_digest(approval),
        }
        return cls(**payload, request_digest=sha256_digest(payload))


class ProductElementLockV1(_ProductLockContent):
    contract_version: Literal["ProductElementLock.v1"] = "ProductElementLock.v1"
    draft_digest: DigestStr
    approved_by: Text
    approval_digest: DigestStr
    lock_digest: DigestStr

    @model_validator(mode="after")
    def _valid(self) -> "ProductElementLockV1":
        expected_approval = sha256_digest(
            approval_subject_v1(
                workspace_id=self.workspace_id,
                run_id=self.run_id,
                listing_slug=self.listing_slug,
                draft_digest=self.draft_digest,
                approved_by=self.approved_by,
            )
        )
        if self.approval_digest != expected_approval:
            raise ValueError("approval_digest does not match product element lock")
        _require_digest(self, "lock_digest")
        return self

    @classmethod
    def from_approved(cls, request: ArtemisSealRequestV1) -> "ProductElementLockV1":
        payload = request.draft.model_dump(
            mode="json",
            exclude={"contract_version", "draft_digest"},
        )
        payload.update(
            contract_version="ProductElementLock.v1",
            draft_digest=request.draft.draft_digest,
            approved_by=request.approved_by,
            approval_digest=request.approval_digest,
        )
        return cls(**payload, lock_digest=sha256_digest(payload))


class ArtemisSealResultV1(_StrictModel):
    contract_version: Literal["ArtemisSealResult.v1"] = "ArtemisSealResult.v1"
    status: Literal["sealed", "blocked"]
    lock: ProductElementLockV1 | None = None
    error_code: BlockCode | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> "ArtemisSealResultV1":
        _require_result_shape(self.status, self.lock, self.error_code, "sealed")
        return self

    @classmethod
    def sealed(cls, lock: ProductElementLockV1) -> "ArtemisSealResultV1":
        return cls(status="sealed", lock=lock)

    @classmethod
    def blocked(cls, error_code: BlockCode) -> "ArtemisSealResultV1":
        return cls(status="blocked", error_code=error_code)


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


__all__ = [
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
