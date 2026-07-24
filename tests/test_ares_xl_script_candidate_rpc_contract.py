from __future__ import annotations

from hiob_contracts.rpc_contracts import (
    load_ares_insert_xl_script_candidate_v2_contract,
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
    ("p_candidate_canonical_text", "text"),
    ("p_candidate_payload", "jsonb"),
    ("p_candidate_digest", "text"),
    ("p_production_job_id", "uuid"),
    ("p_execution_claim_token", "uuid"),
    ("p_production_job_attributes", "jsonb"),
    ("p_artemis_reference_master_canonical_text", "text"),
    ("p_artemis_authority_canonical_text", "text"),
    ("p_artemis_authority_payload", "jsonb"),
    ("p_ares_xl_jkpa_authority_canonical_text", "text"),
    ("p_ares_xl_jkpa_authority_payload", "jsonb"),
    ("p_ares_xl_jkpa_authority_digest", "text"),
)
EXPECTED_RESULT_KEYS = {
    "approval_id",
    "approval_revision",
    "ares_xl_authoritative_job_attributes_digest",
    "artemis_authority_digest",
    "artemis_listing_slug",
    "artemis_reference_master_digest",
    "artemis_reference_master_id",
    "artemis_reference_master_version",
    "binding_digest",
    "candidate_digest",
    "candidate_id",
    "execution_claim_token",
    "jkpa_authority_digest",
    "ok",
    "outcome",
    "production_job_id",
    "xl_idempotency_key",
}


def test_0127_shared_rpc_fixture_pins_exact_argument_and_result_contract():
    contract = load_ares_insert_xl_script_candidate_v2_contract()
    arguments = tuple(tuple(item) for item in contract["arguments"])
    result_keys = set(contract["result_keys"])

    assert contract["rpc_name"] == "ares_insert_xl_script_candidate_v2"
    assert contract["source_migration"] == (
        "0127_ares_xl_artemis_authority_cas.sql"
    )
    assert arguments == EXPECTED_ARGUMENTS
    assert len(arguments) == 26
    assert len({name for name, _type in arguments}) == 26
    assert result_keys == EXPECTED_RESULT_KEYS
    assert len(result_keys) == 17
    assert result_keys == (
        set(contract["base_result_keys"])
        | set(contract["sql_appended_result_keys"])
    )
