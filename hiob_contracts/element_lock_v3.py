"""Small URL-free contract for Parzifal V3 element locks."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .factory.digest import Digest, assert_digest, sha256_digest
from .url_policy import starts_with_forbidden_artifact_reference, starts_with_web_url

_FROZEN = {"frozen": True, "extra": "forbid"}
ElementRole = Literal["source", "character_sheet"]
ElementStatus = Literal["review", "ready", "failed"]


class ElementArtifactRefV1(BaseModel):
    """Stable binary handle. Storage and signed URLs stay behind the adapter."""

    model_config = _FROZEN

    artifact_id: str = Field(min_length=1)
    sha256: Digest
    role: ElementRole

    @field_validator("artifact_id")
    @classmethod
    def _reject_url_id(cls, value: str) -> str:
        if starts_with_forbidden_artifact_reference(value, trim=True):
            raise ValueError("artifact_id must be an opaque server id, not a URL")
        return value

    @model_validator(mode="after")
    def _check_digest(self) -> "ElementArtifactRefV1":
        assert_digest(self.sha256, "element_artifact.sha256")
        return self


class CreateElementLockRequestV1(BaseModel):
    """Exactly one paid character-sheet operation."""

    model_config = _FROZEN

    operation_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    identity_spec: dict[str, Any]
    source_refs: tuple[ElementArtifactRefV1, ...] = ()
    paid_policy_digest: Digest
    request_digest: Digest

    @classmethod
    def build(cls, **values: Any) -> "CreateElementLockRequestV1":
        values["source_refs"] = tuple(
            ref
            if isinstance(ref, ElementArtifactRefV1)
            else ElementArtifactRefV1.model_validate(ref)
            for ref in values.get("source_refs", ())
        )
        draft = cls.model_construct(request_digest=sha256_digest("draft"), **values)
        payload = draft.model_dump(mode="json")
        payload.pop("request_digest")
        return cls(**payload, request_digest=sha256_digest(payload))

    @model_validator(mode="after")
    def _check(self) -> "CreateElementLockRequestV1":
        assert_digest(self.paid_policy_digest, "paid_policy_digest")
        if _contains_url(self.identity_spec):
            raise ValueError("identity_spec must not contain URLs")
        source_ids = [ref.artifact_id for ref in self.source_refs]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_refs contains duplicate artifact_id")
        if any(ref.role != "source" for ref in self.source_refs):
            raise ValueError("source_refs must use role=source")
        payload = self.model_dump(mode="json")
        payload.pop("request_digest")
        if self.request_digest != sha256_digest(payload):
            raise ValueError("request_digest does not match request")
        return self


class ElementLockPackageV1(BaseModel):
    """Review candidate or approved immutable character sheet."""

    model_config = _FROZEN

    lock_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    operation_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    status: ElementStatus
    character_sheet_ref: ElementArtifactRefV1 | None = None
    provider_receipt_digest: Digest | None = None
    approved_by: str | None = None
    lock_digest: Digest

    @classmethod
    def build(cls, **values: Any) -> "ElementLockPackageV1":
        values.pop("lock_digest", None)
        artifact = values.get("character_sheet_ref")
        if artifact is not None and not isinstance(artifact, ElementArtifactRefV1):
            values["character_sheet_ref"] = ElementArtifactRefV1.model_validate(artifact)
        draft = cls.model_construct(lock_digest=sha256_digest("draft"), **values)
        payload = draft.model_dump(mode="json")
        payload.pop("lock_digest")
        return cls(**payload, lock_digest=sha256_digest(payload))

    @model_validator(mode="after")
    def _check(self) -> "ElementLockPackageV1":
        if self.status in {"review", "ready"}:
            if self.character_sheet_ref is None:
                raise ValueError("character_sheet_ref is required")
            if self.character_sheet_ref.role != "character_sheet":
                raise ValueError("character_sheet_ref must use role=character_sheet")
            if self.provider_receipt_digest is None:
                raise ValueError("provider_receipt_digest is required")
        if self.status == "ready" and not str(self.approved_by or "").strip():
            raise ValueError("approved_by is required when ready")
        if self.status == "ready" and self.version < 2:
            raise ValueError("ready package must be a new version")
        payload = self.model_dump(mode="json")
        payload.pop("lock_digest")
        if self.lock_digest != sha256_digest(payload):
            raise ValueError("lock_digest does not match package")
        return self


def _contains_url(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            "url" in str(key).lower() or _contains_url(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_url(item) for item in value)
    return isinstance(value, str) and starts_with_web_url(value)


__all__ = [
    "CreateElementLockRequestV1",
    "ElementArtifactRefV1",
    "ElementLockPackageV1",
]
