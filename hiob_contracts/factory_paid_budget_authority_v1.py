"""Pre-script paid authority for one exact all-beat factory budget.

This authority exists before an Ares script or approved beat plan.  It therefore
does not carry a plan digest, provider model, or post-plan operation budget.
Those remain the responsibility of FactoryBeatManifest.v1 and the legacy
PaidCallBudget.v1 execution contract.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping, Protocol
from weakref import WeakKeyDictionary

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    UuidStr,
    _FROZEN_STRICT,
    _parse_utc,
    canonical_contract_digest_v1,
)


FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1 = "FactoryPaidBudgetAuthority.v1"
FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V1 = (
    "FactoryPaidBudgetApprovalReceipt.v1"
)
PositiveSafeInt = Annotated[int, Field(gt=0, le=9_007_199_254_740_991)]
AllBeatCount = Annotated[int, Field(ge=1, le=16)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


def _as_json_dict(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    return (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )


class FactoryPaidCallCardinalityV1(BaseModel):
    """Exact paid-call ceiling; every non-zero count is intentional."""

    model_config = _FROZEN_STRICT

    script: Literal[1]
    image: PositiveSafeInt
    video: PositiveSafeInt
    voice: PositiveSafeInt
    render: Literal[1]
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]


def factory_paid_call_cardinality_v1(
    all_beat_count: int,
) -> dict[str, int]:
    return {
        "script": 1,
        "image": all_beat_count,
        "video": all_beat_count,
        "voice": all_beat_count,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }


def derive_factory_paid_budget_approval_subject_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind exact scope, cardinality, currency, and total cost ceiling."""

    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "contract_version": "FactoryPaidBudgetApprovalSubject.v1",
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "all_beat_count": data["all_beat_count"],
            "paid_calls": data["paid_calls"],
            "max_total_cost_microunits": data[
                "max_total_cost_microunits"
            ],
            "currency": data["currency"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
        }
    )


def derive_factory_paid_budget_idempotency_key_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Stable authority identity; runtime attempt/provider data is excluded."""

    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "factory-paid-budget-authority.v1",
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "approval_subject_digest": data["approval_subject_digest"],
            "approval_receipt_id": data["approval_receipt_id"],
            "approval_receipt_digest": data["approval_receipt_digest"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
        }
    )


def derive_factory_paid_budget_authority_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return canonical_contract_digest_v1(value, exclude={"authority_digest"})


def derive_factory_paid_budget_approval_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return canonical_contract_digest_v1(value, exclude={"receipt_digest"})


class FactoryPaidBudgetApprovalResolverV1(Protocol):
    """Durable authority required to prove an approval is still current."""

    def is_current_approval(
        self,
        *,
        receipt_id: str,
        receipt_digest: str,
        workspace_id: str,
        run_id: str,
        factory_revision: int,
        state_revision: int,
        policy_version: str,
        approval_subject_digest: str,
        approver_account_id: str,
        cost_profile_digest: str,
        pricing_policy_revision: int,
    ) -> bool: ...


class FactoryPaidBudgetAuthorityV1(BaseModel):
    """Structurally sealed scope; validation alone is not execution authority."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryPaidBudgetAuthority.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    all_beat_count: AllBeatCount
    paid_calls: FactoryPaidCallCardinalityV1
    max_total_cost_microunits: PositiveSafeInt
    currency: CurrencyCode
    cost_profile_digest: DigestStr
    pricing_policy_revision: NonNegativeInt
    approval_receipt_id: NonBlankStr
    approval_receipt_digest: DigestStr
    approval_subject_digest: DigestStr
    idempotency_key: DigestStr
    authority_digest: DigestStr

    @model_validator(mode="after")
    def _bind_paid_authority(self) -> "FactoryPaidBudgetAuthorityV1":
        expected_calls = factory_paid_call_cardinality_v1(
            self.all_beat_count
        )
        if self.paid_calls.model_dump() != expected_calls:
            raise ValueError(
                "paid_calls must equal exact all_beat_count cardinality"
            )
        expected_subject = (
            derive_factory_paid_budget_approval_subject_digest_v1(self)
        )
        if self.approval_subject_digest != expected_subject:
            raise ValueError(
                "approval_subject_digest does not match paid budget scope"
            )
        expected_idempotency = (
            derive_factory_paid_budget_idempotency_key_v1(self)
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError(
                "idempotency_key does not match approval and budget authority"
            )
        expected_authority = derive_factory_paid_budget_authority_digest_v1(
            self
        )
        if self.authority_digest != expected_authority:
            raise ValueError(
                "authority_digest does not match factory paid budget authority"
            )
        return self

    @classmethod
    def from_verified(
        cls,
        value: Mapping[str, Any] | BaseModel,
        *,
        approval_receipt: "FactoryPaidBudgetApprovalReceiptV1",
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV1,
    ) -> "VerifiedFactoryPaidBudgetAuthorityV1":
        authority = cls.model_validate(_as_json_dict(value))
        if not approval_receipt.authorizes(
            authority, at_utc=at_utc, resolver=resolver
        ):
            raise ValueError("authority requires current durable approval")
        return VerifiedFactoryPaidBudgetAuthorityV1(
            authority, _token=_VERIFIED_AUTHORITY_TOKEN
        )


_VERIFIED_AUTHORITY_TOKEN = object()
_VERIFIED_AUTHORITY_REGISTRY: WeakKeyDictionary[
    object, FactoryPaidBudgetAuthorityV1
] = WeakKeyDictionary()


class VerifiedFactoryPaidBudgetAuthorityV1:
    """In-process paid capability; deliberately not a wire contract."""

    __slots__ = ("__weakref__",)

    def __init__(
        self,
        authority: FactoryPaidBudgetAuthorityV1,
        *,
        _token: object,
    ) -> None:
        if _token is not _VERIFIED_AUTHORITY_TOKEN:
            raise TypeError("verified authority can only be minted by from_verified")
        _VERIFIED_AUTHORITY_REGISTRY[self] = authority

    @property
    def authority(self) -> FactoryPaidBudgetAuthorityV1:
        return _unwrap_verified_factory_paid_budget_authority_v1(self)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise TypeError("verified paid authority is immutable")

    def __delattr__(self, _name: str) -> None:
        raise TypeError("verified paid authority is immutable")

    def __copy__(self) -> object:
        raise TypeError("verified paid authority cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> object:
        raise TypeError("verified paid authority cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise TypeError("verified paid authority is not serializable")

    def __repr__(self) -> str:
        return "VerifiedFactoryPaidBudgetAuthorityV1(<sealed>)"


def _unwrap_verified_factory_paid_budget_authority_v1(
    capability: object,
) -> FactoryPaidBudgetAuthorityV1:
    """Module-private brand check and registry unwrap for execution guards."""

    if not isinstance(capability, VerifiedFactoryPaidBudgetAuthorityV1):
        raise TypeError("execution requires VerifiedFactoryPaidBudgetAuthorityV1")
    try:
        return _VERIFIED_AUTHORITY_REGISTRY[capability]
    except KeyError as exc:
        raise TypeError("unminted verified paid authority capability") from exc


class FactoryPaidBudgetApprovalReceiptV1(BaseModel):
    """Approval evidence; never bearer authority without its durable resolver."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryPaidBudgetApprovalReceipt.v1"]
    receipt_id: NonBlankStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    all_beat_count: AllBeatCount
    paid_calls: FactoryPaidCallCardinalityV1
    max_total_cost_microunits: PositiveSafeInt
    currency: CurrencyCode
    cost_profile_digest: DigestStr
    pricing_policy_revision: NonNegativeInt
    approval_subject_digest: DigestStr
    approver_account_id: NonBlankStr
    decision: Literal["approved"]
    policy_version: NonBlankStr
    state_revision: PositiveSafeInt
    approved_at_utc: str
    expires_at_utc: str
    revoked_at_utc: str | None
    transaction_audit_id: NonBlankStr
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_receipt(self) -> "FactoryPaidBudgetApprovalReceiptV1":
        if self.transaction_audit_id != self.receipt_id:
            raise ValueError("transaction_audit_id must equal receipt_id")
        if self.paid_calls.model_dump() != factory_paid_call_cardinality_v1(
            self.all_beat_count
        ):
            raise ValueError("paid_calls must equal exact all_beat_count cardinality")
        if self.approval_subject_digest != (
            derive_factory_paid_budget_approval_subject_digest_v1(self)
        ):
            raise ValueError("approval_subject_digest does not match paid budget scope")
        approved = _parse_utc(self.approved_at_utc)
        expires = _parse_utc(self.expires_at_utc)
        if expires <= approved:
            raise ValueError("expires_at_utc must follow approved_at_utc")
        if self.revoked_at_utc is not None:
            revoked = _parse_utc(self.revoked_at_utc)
            if revoked < approved or revoked > expires:
                raise ValueError("revoked_at_utc must fall within approval lifetime")
        if self.receipt_digest != (
            derive_factory_paid_budget_approval_receipt_digest_v1(self)
        ):
            raise ValueError("receipt_digest does not match approval receipt")
        return self

    def structurally_binds(self, authority: FactoryPaidBudgetAuthorityV1) -> bool:
        return (
            self.receipt_id == authority.approval_receipt_id
            and self.receipt_digest == authority.approval_receipt_digest
            and self.workspace_id == authority.workspace_id
            and self.run_id == authority.run_id
            and self.factory_revision == authority.factory_revision
            and self.all_beat_count == authority.all_beat_count
            and self.paid_calls == authority.paid_calls
            and self.max_total_cost_microunits
            == authority.max_total_cost_microunits
            and self.currency == authority.currency
            and self.cost_profile_digest == authority.cost_profile_digest
            and self.pricing_policy_revision
            == authority.pricing_policy_revision
            and self.approval_subject_digest == authority.approval_subject_digest
        )

    def authorizes(
        self,
        authority: FactoryPaidBudgetAuthorityV1,
        *,
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV1,
    ) -> bool:
        if not self.structurally_binds(authority):
            return False
        at = _parse_utc(at_utc)
        if (
            at < _parse_utc(self.approved_at_utc)
            or at >= _parse_utc(self.expires_at_utc)
            or self.revoked_at_utc is not None
        ):
            return False
        return resolver.is_current_approval(
            receipt_id=self.receipt_id,
            receipt_digest=self.receipt_digest,
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            factory_revision=self.factory_revision,
            state_revision=self.state_revision,
            policy_version=self.policy_version,
            approval_subject_digest=self.approval_subject_digest,
            approver_account_id=self.approver_account_id,
            cost_profile_digest=self.cost_profile_digest,
            pricing_policy_revision=self.pricing_policy_revision,
        )


def build_factory_paid_budget_authority_v1(
    *,
    workspace_id: str,
    run_id: str,
    factory_revision: int,
    all_beat_count: int,
    max_total_cost_microunits: int,
    currency: str,
    cost_profile_digest: str,
    pricing_policy_revision: int,
    approval_receipt: FactoryPaidBudgetApprovalReceiptV1,
    at_utc: str,
    resolver: FactoryPaidBudgetApprovalResolverV1,
) -> VerifiedFactoryPaidBudgetAuthorityV1:
    """Build only from a typed, current, durable approval receipt."""

    body: dict[str, Any] = {
        "contract_version": FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1,
        "workspace_id": workspace_id,
        "run_id": run_id,
        "factory_revision": factory_revision,
        "all_beat_count": all_beat_count,
        "paid_calls": factory_paid_call_cardinality_v1(all_beat_count),
        "max_total_cost_microunits": max_total_cost_microunits,
        "currency": currency,
        "cost_profile_digest": cost_profile_digest,
        "pricing_policy_revision": pricing_policy_revision,
        "approval_receipt_id": approval_receipt.receipt_id,
        "approval_receipt_digest": approval_receipt.receipt_digest,
    }
    body["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v1(body)
    )
    body["idempotency_key"] = (
        derive_factory_paid_budget_idempotency_key_v1(body)
    )
    body["authority_digest"] = (
        derive_factory_paid_budget_authority_digest_v1(body)
    )
    return FactoryPaidBudgetAuthorityV1.from_verified(
        body,
        approval_receipt=approval_receipt,
        at_utc=at_utc,
        resolver=resolver,
    )


__all__ = [
    "FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1",
    "FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V1",
    "FactoryPaidCallCardinalityV1",
    "FactoryPaidBudgetApprovalResolverV1",
    "FactoryPaidBudgetApprovalReceiptV1",
    "FactoryPaidBudgetAuthorityV1",
    "VerifiedFactoryPaidBudgetAuthorityV1",
    "factory_paid_call_cardinality_v1",
    "derive_factory_paid_budget_approval_subject_digest_v1",
    "derive_factory_paid_budget_idempotency_key_v1",
    "derive_factory_paid_budget_authority_digest_v1",
    "derive_factory_paid_budget_approval_receipt_digest_v1",
    "build_factory_paid_budget_authority_v1",
]
