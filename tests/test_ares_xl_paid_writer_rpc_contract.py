from __future__ import annotations

from hiob_contracts.rpc_contracts import (
    load_ares_claim_xl_paid_writer_v1_contract,
)


EXPECTED_ARGUMENTS = (
    ("p_workspace_id", "uuid"),
    ("p_run_id", "uuid"),
    ("p_approval_id", "uuid"),
    ("p_approval_revision", "bigint"),
    ("p_strategy_digest", "text"),
    ("p_bundle_digest", "text"),
    ("p_receipt_digest", "text"),
    ("p_binding_canonical_text", "text"),
    ("p_binding_payload", "jsonb"),
    ("p_target_profile_canonical_text", "text"),
    ("p_master_sheet_canonical_text", "text"),
    ("p_cast_sheets_canonical_text", "text"),
    ("p_binding_digest", "text"),
    ("p_xl_idempotency_key", "text"),
    ("p_round", "integer"),
    ("p_ordinal", "integer"),
    ("p_production_job_id", "uuid"),
    ("p_execution_claim_token", "uuid"),
    ("p_expected_job_attributes", "jsonb"),
    ("p_next_job_attributes", "jsonb"),
    ("p_artemis_reference_master_canonical_text", "text"),
    ("p_artemis_authority_canonical_text", "text"),
    ("p_artemis_authority_payload", "jsonb"),
    ("p_ares_xl_jkpa_authority_canonical_text", "text"),
    ("p_ares_xl_jkpa_authority_payload", "jsonb"),
    ("p_ares_xl_jkpa_authority_digest", "text"),
)
EXPECTED_RESULT_KEYS = (
    "ok",
    "outcome",
    "paid_allowed",
    "reservation_id",
    "provider_idempotency_key",
    "production_job_id",
    "execution_claim_token",
    "xl_idempotency_key",
    "round",
    "ordinal",
    "production_job_attributes",
    "production_job_attributes_digest",
)


def test_0127_shared_paid_writer_rpc_fixture_pins_exact_contract():
    contract = load_ares_claim_xl_paid_writer_v1_contract()
    arguments = tuple(tuple(item) for item in contract["arguments"])
    result_keys = tuple(contract["result_keys"])

    assert contract["schema"] == "public"
    assert contract["rpc_name"] == "ares_claim_xl_paid_writer_v1"
    assert (
        contract["qualified_rpc_name"]
        == "public.ares_claim_xl_paid_writer_v1"
    )
    assert contract["source_migration"] == (
        "0127_ares_xl_artemis_authority_cas.sql"
    )
    assert arguments == EXPECTED_ARGUMENTS
    assert len(arguments) == 26
    assert len({name for name, _type in arguments}) == 26
    assert result_keys == EXPECTED_RESULT_KEYS
    assert len(result_keys) == 12
    assert len(set(result_keys)) == 12
