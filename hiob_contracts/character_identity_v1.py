"""Atomic face + voice identity binding shared by Parzifal and its consumers."""

from __future__ import annotations

from typing import Any

from .factory.digest import is_digest, sha256_digest

CONTRACT_VERSION = "CharacterIdentityBinding.v1"


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def character_identity_binding_payload_v1(
    *,
    subject_id: str,
    face_id: str,
    voice_id: str,
) -> dict[str, str]:
    """Return the one canonical payload whose digest binds face and voice."""

    return {
        "contract_version": CONTRACT_VERSION,
        "subject_id": _required_text(subject_id, "subject_id"),
        "face_id": _required_text(face_id, "face_id"),
        "voice_id": _required_text(voice_id, "voice_id"),
    }


def derive_character_identity_binding_digest_v1(
    *,
    subject_id: str,
    face_id: str,
    voice_id: str,
) -> str:
    return sha256_digest(
        character_identity_binding_payload_v1(
            subject_id=subject_id,
            face_id=face_id,
            voice_id=voice_id,
        )
    )


def character_identity_binding_errors_v1(
    *,
    subject_id: str,
    face_id: str | None,
    voice_id: str | None,
    identity_binding_digest: str | None,
) -> list[str]:
    """Validate an optional legacy identity, failing closed once either ID exists."""

    has_face = bool(str(face_id or "").strip())
    has_voice = bool(str(voice_id or "").strip())
    has_digest = bool(str(identity_binding_digest or "").strip())
    if not has_face and not has_voice and not has_digest:
        return []
    if not has_face or not has_voice:
        return ["face_id and voice_id must be sealed together"]
    if not has_digest or not is_digest(str(identity_binding_digest)):
        return ["identity_binding_digest is required for sealed face_id + voice_id"]
    expected = derive_character_identity_binding_digest_v1(
        subject_id=subject_id,
        face_id=str(face_id),
        voice_id=str(voice_id),
    )
    if identity_binding_digest != expected:
        return ["identity_binding_digest does not match subject_id + face_id + voice_id"]
    return []


__all__ = [
    "character_identity_binding_payload_v1",
    "derive_character_identity_binding_digest_v1",
    "character_identity_binding_errors_v1",
]
