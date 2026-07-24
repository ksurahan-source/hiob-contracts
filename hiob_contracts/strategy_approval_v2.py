"""Strict immutable contracts for strategy approval and Parzifal identity binding.

The database is authoritative for approval activity and revocation.  These
value contracts only prove that the evidence returned by that authority is
canonical, internally consistent, and safe to hand across planet boundaries.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .ares_script_revision_v1 import (
    DigestStr,
    UtcTimestamp,
    UuidStr,
    _deep_freeze_json,
    _json_value,
    _validate_json,
    canonical_contract_digest_v1,
)


_FROZEN_STRICT = ConfigDict(
    frozen=True,
    extra="forbid",
    strict=True,
    revalidate_instances="always",
)


def _canonical_nonempty(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("string must not be blank")
    if value != value.strip():
        raise ValueError("string must not contain surrounding whitespace")
    return value


CanonicalNonEmptyStr = Annotated[str, AfterValidator(_canonical_nonempty)]
RevisionInt = Annotated[int, Field(ge=1, le=2_147_483_647)]
InputRevisionInt = Annotated[int, Field(ge=0, le=2_147_483_647)]


def _freeze_json_object(
    value: Mapping[str, Any],
    *,
    field: str,
    require_nonempty: bool,
) -> Mapping[str, Any]:
    if require_nonempty and not value:
        raise ValueError(f"{field} must be a non-empty JSON object")
    _validate_json_key_unicode(value, field)
    _validate_json(value, field)
    return _deep_freeze_json(value)


def _validate_json_key_unicode(
    value: Any,
    path: str,
    active: set[int] | None = None,
) -> None:
    """Reject invalid key Unicode and cyclic non-JSON graphs before hashing."""

    active = active if active is not None else set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ValueError(f"{path} contains a cyclic non-JSON value")
        active.add(identity)
        try:
            for key, item in value.items():
                if isinstance(key, str) and any(
                    0xD800 <= ord(char) <= 0xDFFF for char in key
                ):
                    raise ValueError(
                        f"{path} contains an unpaired Unicode surrogate key"
                    )
                _validate_json_key_unicode(item, f"{path}.{key}", active)
        finally:
            active.remove(identity)
    elif isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError(f"{path} contains a cyclic non-JSON value")
        active.add(identity)
        try:
            for index, item in enumerate(value):
                _validate_json_key_unicode(item, f"{path}[{index}]", active)
        finally:
            active.remove(identity)


class StrategyApprovalBundleV1(BaseModel):
    """Exact immutable bundle persisted by migration 0120."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StrategyApprovalBundle.v1"]
    run_id: UuidStr
    workspace_id: UuidStr
    strategy: Mapping[str, Any]
    brief_patch: Mapping[str, Any]
    attributes_patch: Mapping[str, Any]

    @field_validator("strategy", mode="after")
    @classmethod
    def _freeze_strategy(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_json_object(value, field="strategy", require_nonempty=True)

    @field_validator("brief_patch", "attributes_patch", mode="after")
    @classmethod
    def _freeze_patch(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_json_object(value, field="patch", require_nonempty=False)

    @field_serializer("strategy", "brief_patch", "attributes_patch", when_used="always")
    def _serialize_mappings(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _json_value(value)

    @property
    def strategy_digest(self) -> str:
        return canonical_contract_digest_v1(self.strategy)

    @property
    def bundle_digest(self) -> str:
        return canonical_contract_digest_v1(self)


class StrategyApprovalReceiptV2(BaseModel):
    """Exact immutable receipt returned by the DB verification RPC."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StrategyApprovalReceipt.v2"]
    approval_id: UuidStr
    claim_id: UuidStr
    run_id: UuidStr
    workspace_id: UuidStr
    strategy_input_revision: InputRevisionInt
    approval_revision: RevisionInt
    source_digest: DigestStr
    strategy_digest: DigestStr
    bundle_digest: DigestStr
    approved_by_account_id: UuidStr
    approved_at: UtcTimestamp
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_digest(self) -> "StrategyApprovalReceiptV2":
        expected = canonical_contract_digest_v1(self, exclude={"receipt_digest"})
        if self.receipt_digest != expected:
            raise ValueError(
                "receipt_digest does not match StrategyApprovalReceipt payload"
            )
        return self


class ParzifalIdentityBindingV1(BaseModel):
    """Immutable identity snapshots bound to one approved strategy receipt."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ParzifalIdentityBinding.v1"]
    binding_id: UuidStr
    binding_revision: RevisionInt
    workspace_id: UuidStr
    run_id: UuidStr
    strategy_approval_id: UuidStr
    strategy_digest: DigestStr
    strategy_bundle_digest: DigestStr
    strategy_receipt_digest: DigestStr
    target_profile: Mapping[str, Any]
    target_profile_digest: DigestStr
    master_sheet: Mapping[str, Any]
    master_sheet_digest: DigestStr
    cast_sheets: Mapping[str, Any]
    cast_sheets_digest: DigestStr
    identity_source: Literal["parzifal"]
    source_node: CanonicalNonEmptyStr
    source_revision: CanonicalNonEmptyStr
    created_at: UtcTimestamp
    created_by_account_id: CanonicalNonEmptyStr
    binding_digest: DigestStr

    @field_validator("target_profile", "master_sheet", "cast_sheets", mode="after")
    @classmethod
    def _freeze_snapshots(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_json_object(
            value, field="identity_snapshot", require_nonempty=True
        )

    @field_serializer(
        "target_profile",
        "master_sheet",
        "cast_sheets",
        when_used="always",
    )
    def _serialize_snapshots(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_snapshots(self) -> "ParzifalIdentityBindingV1":
        expected_digests = {
            "target_profile_digest": canonical_contract_digest_v1(
                self.target_profile
            ),
            "master_sheet_digest": canonical_contract_digest_v1(self.master_sheet),
            "cast_sheets_digest": canonical_contract_digest_v1(self.cast_sheets),
        }
        for field, expected in expected_digests.items():
            if getattr(self, field) != expected:
                raise ValueError(f"{field} does not match its immutable snapshot")
        expected_binding = canonical_contract_digest_v1(
            self, exclude={"binding_digest"}
        )
        if self.binding_digest != expected_binding:
            raise ValueError(
                "binding_digest does not match ParzifalIdentityBinding payload"
            )
        return self


def derive_parzifal_identity_binding_id_v1(receipt_digest: str) -> str:
    """Derive the one canonical binding UUID for an approval receipt."""

    if (
        not isinstance(receipt_digest, str)
        or len(receipt_digest) != 71
        or not receipt_digest.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in receipt_digest[7:])
    ):
        raise ValueError("receipt_digest must be a lowercase sha256 digest")
    hex_chars = list(receipt_digest[7:39])
    hex_chars[12] = "5"
    hex_chars[16] = ("8", "9", "a", "b")[int(hex_chars[16], 16) % 4]
    value = "".join(hex_chars)
    return (
        f"{value[:8]}-{value[8:12]}-{value[12:16]}-"
        f"{value[16:20]}-{value[20:32]}"
    )


def validate_strategy_approval_evidence_v2(
    bundle: StrategyApprovalBundleV1 | Mapping[str, Any],
    receipt: StrategyApprovalReceiptV2 | Mapping[str, Any],
) -> tuple[StrategyApprovalBundleV1, StrategyApprovalReceiptV2]:
    """Parse and bind a DB bundle/receipt pair, rejecting cross-scope evidence."""

    parsed_bundle = StrategyApprovalBundleV1.model_validate(bundle)
    parsed_receipt = StrategyApprovalReceiptV2.model_validate(receipt)
    if parsed_receipt.run_id != parsed_bundle.run_id:
        raise ValueError("strategy approval run_id scope mismatch")
    if parsed_receipt.workspace_id != parsed_bundle.workspace_id:
        raise ValueError("strategy approval workspace_id scope mismatch")
    if parsed_receipt.strategy_digest != parsed_bundle.strategy_digest:
        raise ValueError("strategy approval strategy_digest mismatch")
    if parsed_receipt.bundle_digest != parsed_bundle.bundle_digest:
        raise ValueError("strategy approval bundle_digest mismatch")
    return parsed_bundle, parsed_receipt


def validate_parzifal_identity_binding_v1(
    binding: ParzifalIdentityBindingV1 | Mapping[str, Any],
    *,
    bundle: StrategyApprovalBundleV1 | Mapping[str, Any],
    receipt: StrategyApprovalReceiptV2 | Mapping[str, Any],
) -> ParzifalIdentityBindingV1:
    """Parse a binding and prove it belongs to the supplied DB evidence."""

    parsed_bundle, parsed_receipt = validate_strategy_approval_evidence_v2(
        bundle, receipt
    )
    parsed_binding = ParzifalIdentityBindingV1.model_validate(binding)
    expected = {
        "binding_id": derive_parzifal_identity_binding_id_v1(
            parsed_receipt.receipt_digest
        ),
        "binding_revision": parsed_receipt.approval_revision,
        "workspace_id": parsed_bundle.workspace_id,
        "run_id": parsed_bundle.run_id,
        "strategy_approval_id": parsed_receipt.approval_id,
        "strategy_digest": parsed_receipt.strategy_digest,
        "strategy_bundle_digest": parsed_receipt.bundle_digest,
        "strategy_receipt_digest": parsed_receipt.receipt_digest,
        "source_node": "parzifal.identity.bind",
        "source_revision": "parzifal.identity.bind.v1",
        "created_at": parsed_receipt.approved_at,
        "created_by_account_id": parsed_receipt.approved_by_account_id,
    }
    for field, value in expected.items():
        if getattr(parsed_binding, field) != value:
            raise ValueError(f"Parzifal identity {field} binding mismatch")
    attributes_patch = parsed_bundle.attributes_patch
    if attributes_patch.get("identity_source") != "parzifal":
        raise ValueError(
            "Parzifal identity bundle identity_source must be parzifal"
        )
    approved_snapshots = {
        "target_profile": attributes_patch.get("target_profile"),
        "master_sheet": attributes_patch.get("parzifal_master_sheet"),
        "cast_sheets": attributes_patch.get("parzifal_cast_sheets"),
    }
    for field, approved in approved_snapshots.items():
        if not isinstance(approved, Mapping) or not approved:
            raise ValueError(
                f"Parzifal identity bundle {field} snapshot is missing"
            )
        if canonical_contract_digest_v1(approved) != canonical_contract_digest_v1(
            getattr(parsed_binding, field)
        ):
            raise ValueError(
                f"Parzifal identity {field} does not match approved bundle"
            )
    return parsed_binding


__all__ = [
    "StrategyApprovalBundleV1",
    "StrategyApprovalReceiptV2",
    "ParzifalIdentityBindingV1",
    "derive_parzifal_identity_binding_id_v1",
    "validate_strategy_approval_evidence_v2",
    "validate_parzifal_identity_binding_v1",
]
