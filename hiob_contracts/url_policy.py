"""Credential-free URL boundary helpers shared by contract validators."""
from __future__ import annotations

_WEB_SCHEMES = frozenset({"http", "https"})
_EMBEDDED_SCHEMES = frozenset({"data", "file"})


def starts_with_web_url(value: str, *, trim: bool = False) -> bool:
    """Return whether *value* starts with a conventional web URL scheme."""
    normalized = value.strip().casefold() if trim else value.casefold()
    scheme, separator, remainder = normalized.partition(":")
    return bool(separator and scheme in _WEB_SCHEMES and remainder.startswith("//"))


def starts_with_forbidden_artifact_reference(value: str, *, trim: bool = False) -> bool:
    """Reject web URLs and embedded/file references at opaque-ID boundaries."""
    normalized = value.strip().casefold() if trim else value.casefold()
    scheme, separator, remainder = normalized.partition(":")
    if not separator:
        return False
    if scheme in _EMBEDDED_SCHEMES:
        return True
    return scheme in _WEB_SCHEMES and remainder.startswith("//")


__all__ = ["starts_with_forbidden_artifact_reference", "starts_with_web_url"]
