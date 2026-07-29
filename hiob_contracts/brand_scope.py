"""Canonical production brand scope shared by V3 make contracts."""

from __future__ import annotations

import unicodedata
from typing import Annotated

from pydantic import AfterValidator

from .ares_script_revision_v1 import NonBlankStr


def normalize_unicode_scalars(value: str) -> str:
    """Reject unpaired surrogates and normalize valid UTF-16 pairs."""

    normalized: list[str] = []
    index = 0
    while index < len(value):
        code = ord(value[index])
        if 0xD800 <= code <= 0xDBFF:
            if index + 1 >= len(value):
                raise ValueError(
                    "text must contain valid Unicode scalar values"
                )
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise ValueError(
                    "text must contain valid Unicode scalar values"
                )
            normalized.append(
                chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00))
            )
            index += 2
            continue
        if 0xDC00 <= code <= 0xDFFF:
            raise ValueError(
                "text must contain valid Unicode scalar values"
            )
        normalized.append(value[index])
        index += 1
    return "".join(normalized)


def canonical_brand_slug(value: str) -> str:
    """Preserve the exact DB slug while rejecting ambiguous text."""

    if not isinstance(value, str):
        raise ValueError("brand_slug must be text")
    normalized = normalize_unicode_scalars(value)
    if normalized != normalized.strip():
        raise ValueError("brand_slug must not have surrounding whitespace")
    if any(unicodedata.category(char) == "Cc" for char in normalized):
        raise ValueError("brand_slug must not contain control characters")
    return normalized


CanonicalBrandSlug = Annotated[
    NonBlankStr,
    AfterValidator(canonical_brand_slug),
]


__all__ = [
    "CanonicalBrandSlug",
    "canonical_brand_slug",
    "normalize_unicode_scalars",
]
