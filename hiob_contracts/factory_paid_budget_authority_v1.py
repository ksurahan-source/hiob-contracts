"""Pre-script paid authority for one exact all-beat factory budget.

This authority exists before an Ares script or approved beat plan.  It therefore
does not carry a plan digest, provider model, or post-plan operation budget.
Those remain the responsibility of FactoryBeatManifest.v1 and the legacy
PaidCallBudget.v1 execution contract.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    UuidStr,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)


FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1 = "FactoryPaidBudgetAuthority.v1"
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
        }
    )


def derive_factory_paid_budget_authority_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return canonical_contract_digest_v1(value, exclude={"authority_digest"})


class FactoryPaidBudgetAuthorityV1(BaseModel):
    """Durable approval proof for pre-script paid scope and ceiling."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryPaidBudgetAuthority.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    all_beat_count: AllBeatCount
    paid_calls: FactoryPaidCallCardinalityV1
    max_total_cost_microunits: PositiveSafeInt
    currency: CurrencyCode
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


def build_factory_paid_budget_authority_v1(
    *,
    workspace_id: str,
    run_id: str,
    factory_revision: int,
    all_beat_count: int,
    max_total_cost_microunits: int,
    currency: str,
    approval_receipt_id: str,
    approval_receipt_digest: str,
) -> FactoryPaidBudgetAuthorityV1:
    """Build the only valid exact-cardinality authority shape."""

    body: dict[str, Any] = {
        "contract_version": FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1,
        "workspace_id": workspace_id,
        "run_id": run_id,
        "factory_revision": factory_revision,
        "all_beat_count": all_beat_count,
        "paid_calls": factory_paid_call_cardinality_v1(all_beat_count),
        "max_total_cost_microunits": max_total_cost_microunits,
        "currency": currency,
        "approval_receipt_id": approval_receipt_id,
        "approval_receipt_digest": approval_receipt_digest,
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
    return FactoryPaidBudgetAuthorityV1.model_validate(body)


__all__ = [
    "FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V1",
    "FactoryPaidCallCardinalityV1",
    "FactoryPaidBudgetAuthorityV1",
    "factory_paid_call_cardinality_v1",
    "derive_factory_paid_budget_approval_subject_digest_v1",
    "derive_factory_paid_budget_idempotency_key_v1",
    "derive_factory_paid_budget_authority_digest_v1",
    "build_factory_paid_budget_authority_v1",
]
