"""Deterministic Star receipt proving one run is ready without a provider call."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ares_script_revision_v1 import DigestStr
from .artemis_product_lock_v1 import OpaqueId
from .factory.digest import sha256_digest

_STRICT_FROZEN = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    revalidate_instances="always",
)
UuidStr = Annotated[
    str,
    Field(
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
        strict=True,
    ),
]
PositiveRevision = Annotated[
    int,
    Field(gt=0, le=9_007_199_254_740_991, strict=True),
]

_REQUEST_FIELDS = (
    "contract_version",
    "workspace_id",
    "run_id",
    "run_revision",
)
_COMMAND_ID_FIELDS = (
    "workspace_id",
    "run_id",
    "run_revision",
    "request_digest",
    "character_lock_digest",
    "character_lock_version",
    "product_lock_digest",
    "artemis_approval_receipt_id",
    "artemis_approval_receipt_digest",
    "artemis_approval_state_revision",
)
_RECEIPT_FIELDS = (
    "contract_version",
    "command_id",
    *_COMMAND_ID_FIELDS,
    "state",
    "provider_call",
)


def _json_mapping(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    return (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )


def _digest_fields(
    value: Mapping[str, Any] | BaseModel,
    fields: tuple[str, ...],
) -> str:
    data = _json_mapping(value)
    return sha256_digest({field: data[field] for field in fields})


def derive_star_make_ready_request_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _digest_fields(value, _REQUEST_FIELDS)


def derive_star_make_ready_command_id_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _json_mapping(value)
    receipt_id = data["artemis_approval_receipt_id"]
    if (
        not isinstance(receipt_id, str)
        or not receipt_id
        or len(receipt_id) > 255
        or any(
            not (
                character.isascii()
                and (character.isalnum() or character in "._/-")
            )
            for character in receipt_id
        )
        or any(segment in {"", ".", ".."} for segment in receipt_id.split("/"))
    ):
        raise ValueError("artemis_approval_receipt_id is not an opaque id")
    return sha256_digest(
        {
            "command_kind": "star.make_ready",
            **{field: data[field] for field in _COMMAND_ID_FIELDS},
        }
    )


def derive_star_make_ready_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    derive_star_make_ready_command_id_v1(value)
    return _digest_fields(value, _RECEIPT_FIELDS)


class StarMakeReadyResolverV1(Protocol):
    """Durable authority required to use a structurally valid receipt."""

    def is_current_make_ready(
        self,
        *,
        command_id: str,
        workspace_id: str,
        run_id: str,
        run_revision: int,
        character_lock_digest: str,
        character_lock_version: int,
        product_lock_digest: str,
        artemis_approval_receipt_id: str,
        artemis_approval_receipt_digest: str,
        artemis_approval_state_revision: int,
    ) -> bool: ...


class StarMakeReadyRequestV1(BaseModel):
    """Server-scoped read request; it accepts no authority or provider payload."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StarMakeReadyRequest.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    run_revision: PositiveRevision
    request_digest: DigestStr

    @model_validator(mode="after")
    def _validate_digest(self) -> "StarMakeReadyRequestV1":
        if self.request_digest != derive_star_make_ready_request_digest_v1(self):
            raise ValueError("request_digest does not match make-ready request")
        return self


class StarMakeReadyReceiptV1(BaseModel):
    """Read receipt binding current CharacterLock and Artemis product authority."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StarMakeReadyReceipt.v1"]
    command_id: DigestStr
    workspace_id: UuidStr
    run_id: UuidStr
    run_revision: PositiveRevision
    request_digest: DigestStr
    character_lock_digest: DigestStr
    character_lock_version: PositiveRevision
    product_lock_digest: DigestStr
    artemis_approval_receipt_id: OpaqueId
    artemis_approval_receipt_digest: DigestStr
    artemis_approval_state_revision: PositiveRevision
    state: Literal["succeeded"]
    provider_call: Literal["none"]
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _validate_bindings(self) -> "StarMakeReadyReceiptV1":
        request_payload = {
            "contract_version": "StarMakeReadyRequest.v1",
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "run_revision": self.run_revision,
        }
        if self.request_digest != derive_star_make_ready_request_digest_v1(
            request_payload
        ):
            raise ValueError("request_digest does not match make-ready scope")
        if self.command_id != derive_star_make_ready_command_id_v1(self):
            raise ValueError("command_id does not match make-ready authority")
        if self.receipt_digest != derive_star_make_ready_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match make-ready receipt")
        return self

    def authorizes(self, *, resolver: StarMakeReadyResolverV1) -> bool:
        """Require current server state; the receipt itself is not authority."""

        return resolver.is_current_make_ready(
            command_id=self.command_id,
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            run_revision=self.run_revision,
            character_lock_digest=self.character_lock_digest,
            character_lock_version=self.character_lock_version,
            product_lock_digest=self.product_lock_digest,
            artemis_approval_receipt_id=self.artemis_approval_receipt_id,
            artemis_approval_receipt_digest=(
                self.artemis_approval_receipt_digest
            ),
            artemis_approval_state_revision=(
                self.artemis_approval_state_revision
            ),
        ) is True


__all__ = [
    "StarMakeReadyRequestV1",
    "StarMakeReadyReceiptV1",
    "StarMakeReadyResolverV1",
    "derive_star_make_ready_request_digest_v1",
    "derive_star_make_ready_command_id_v1",
    "derive_star_make_ready_receipt_digest_v1",
]
