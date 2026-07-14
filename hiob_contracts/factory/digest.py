"""Canonical JSON serialization + SHA-256 content digests.

PRD_CREATIVE_FACTORY_HARMONY §6: "Canonical JSON serialization is required
before hashing." Every semantic Planet-to-Planet handoff is hash-linked, so the
*byte-for-byte* serialization must be deterministic and identical across Python,
TypeScript, and JSON-Schema consumers. This module is the single source of that
serialization.

Rules:
- Object keys are emitted in sorted order, recursively.
- No insignificant whitespace (`separators=(",", ":")`).
- Non-ASCII is preserved (`ensure_ascii=False`) and encoded UTF-8 before hashing.
- Array order is significant and preserved (never sorted).
- Digest form is ``sha256:<64 lowercase hex>`` — the `Digest` string shape used
  everywhere in the kernel.

Numbers: digested payloads should carry integers or strings, not floats, because
cross-language float formatting is not guaranteed identical. Callers that must
carry a real number should serialize it to a string first. `canonical_json`
rejects non-finite floats (NaN/Inf) rather than emit provider-specific tokens.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# A digest string, e.g. "sha256:9f86d0…". Kept as a plain str alias so it is
# portable to TypeScript's `sha256:${string}` template type and JSON Schema.
Digest = str


class DigestError(ValueError):
    """Raised when a value cannot be canonically serialized or a digest is malformed."""


def _reject_non_finite(obj: Any) -> None:
    """Fail closed on NaN/Inf: they have no canonical, cross-language JSON form."""
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise DigestError(f"non-finite float cannot be canonically serialized: {obj!r}")
    elif isinstance(obj, dict):
        for v in obj.values():
            _reject_non_finite(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _reject_non_finite(v)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON string for hashing. Sorted keys, compact, UTF-8, no NaN/Inf."""
    _reject_non_finite(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_digest(obj: Any) -> Digest:
    """Canonical-JSON SHA-256 of any JSON-serializable value → ``sha256:<hex>``."""
    canonical = canonical_json(obj)
    hexdigest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{hexdigest}"


def is_digest(value: str) -> bool:
    """True iff `value` is a well-formed ``sha256:<64 hex>`` digest."""
    return bool(DIGEST_RE.match(value or ""))


def assert_digest(value: str, field: str = "digest") -> Digest:
    """Return `value` if it is a valid digest, else raise `DigestError` (fail closed)."""
    if not is_digest(value):
        raise DigestError(f"{field} is not a valid sha256 digest: {value!r}")
    return value
