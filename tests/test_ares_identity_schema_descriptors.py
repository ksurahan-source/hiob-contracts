from __future__ import annotations

from hiob_contracts import sha256_digest
from hiob_contracts.ares_create_script_v2 import (
    ares_create_script_request_schema_descriptor_v2,
    ares_create_script_request_schema_digest,
)
from hiob_contracts.ares_create_script_v3 import (
    ares_create_script_request_v3_schema_descriptor,
    ares_create_script_request_v3_schema_digest,
)


EXPECTED_SPEAKER_FIELDS = [
    "display_name",
    "face_id",
    "identity_binding_digest",
    "role",
    "subject_id",
    "voice_id",
]
EXPECTED_IDENTITY_INVARIANTS = [
    "speaker_face_voice_atomic_binding",
    "speaker_roles_unique",
    "voice_spec_requires_exactly_one_speaker",
    "voice_spec_subject_matches_speaker",
]


def test_v2_descriptor_binds_speaker_voice_spec_and_identity_invariants() -> None:
    descriptor = ares_create_script_request_schema_descriptor_v2()

    assert descriptor["speaker_fields"] == EXPECTED_SPEAKER_FIELDS
    assert descriptor["voice_spec_fields"] == [
        "approved_examples",
        "contract_version",
        "forbidden_phrases",
        "rhythm",
        "subject_id",
        "vocabulary",
        "voice_spec_digest",
    ]
    assert descriptor["identity_invariants"] == EXPECTED_IDENTITY_INVARIANTS
    assert ares_create_script_request_schema_digest() == sha256_digest(descriptor)
    assert ares_create_script_request_schema_digest() == (
        "sha256:85c65dc8b323daecbd5abc8e982fec7460c574abc7f3267e4f0bfafbc4c36a6d"
    )


def test_v3_descriptor_binds_the_same_identity_boundary() -> None:
    descriptor = ares_create_script_request_v3_schema_descriptor()

    assert descriptor["speaker_fields"] == EXPECTED_SPEAKER_FIELDS
    assert descriptor["identity_invariants"] == EXPECTED_IDENTITY_INVARIANTS
    assert ares_create_script_request_v3_schema_digest() == sha256_digest(descriptor)
    assert ares_create_script_request_v3_schema_digest() == (
        "sha256:e3043b68c15ecdc9c560912067c8b7c6b7f25cdce3bce6dfb0facf20204be8b6"
    )
