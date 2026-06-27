"""Locale packs — the i18n orthogonal axis (Phase 0 foundation).

HIOB's monomyth is the SCHEMA (invariant): viewer=hero, brand=guide, the
3-role theatre, the 7-beat arc. A LOCALE is DATA layered on top — the "face"
the one hero wears per culture (Campbell's thousand faces). This module is the
SINGLE SOURCE that names every locale-varying Modal knob so the pipeline reads
one contract instead of scattering language assumptions.

Contract (mirrors reel_mode / vertical_mode): the axis is ADDITIVE — when no
locale resolves, every consumer is byte-identical to the legacy Korean path.
``resolve_locale_pack`` returns None for the legacy/unknown case so callers keep
their existing env-default fallback untouched.

Resolution order (byte-identical to the old voiceover router on legacy fields):
  1. brief.locale — the canonical axis (BCP-47-ish: ko/en/zh-Hant-TW/...).
     Never present in legacy data, so checking it first changes nothing today.
  2. the FIRST TRUTHY of brief.language / attributes.language / brief.lang
     (Napkin I5) — exactly the old `_provider_for_language` semantics.
  3. brand.language — a fallback for NEW consumers only (the provider path omits
     `brand` to stay byte-identical; ethnicity is safe because every Phase 0 pack
     defaults to Korean).
Unknown values resolve to None (legacy path), never an error.

Phase 0 ships ``ko`` (+ ``en``, which already had behaviour via the voiceover
language router). Each pack reproduces today's hardcoded values EXACTLY. Adding a
language later = adding ONE pack here (+ its prompt template, font, guardrails) —
never touching the monomyth core.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LocalePack:
    """The Modal-side knobs that vary by locale, in one place.

    code              — canonical short code used across layers (ko/en/...).
    aliases           — language strings (brief.locale/language/lang) mapping here.
    voice_provider    — TTS provider (Napkin I5 routing: ko→typecast, en→elevenlabs).
    tts_language      — provider language tag (Typecast ISO 639-3 `kor`, ...).
    default_ethnicity — cast face default when the brief sets no target_ethnicity.
    """

    code: str
    aliases: tuple[str, ...]
    voice_provider: str
    tts_language: str
    default_ethnicity: str


# Phase 0 registry. ko reproduces today's hardcoded behaviour EXACTLY so the
# byte-identical invariant holds; en mirrors the existing voiceover en→ElevenLabs
# branch (and keeps the Korean cast default until a real en pack lands in Phase 3).
LOCALE_PACKS: dict[str, LocalePack] = {
    "ko": LocalePack(
        code="ko",
        aliases=("ko", "kor", "korean", "ko-kr", "ko_kr"),
        voice_provider="typecast",   # voiceover._provider_for_language (ko → Typecast)
        tts_language="kor",          # voiceover.TYPECAST_DEFAULT_LANGUAGE
        default_ethnicity="Korean",  # visual.DEFAULT_ETHNICITY
    ),
    "en": LocalePack(
        code="en",
        aliases=("en", "eng", "english", "en-us", "en_us"),
        voice_provider="elevenlabs",  # voiceover._provider_for_language (en → ElevenLabs)
        tts_language="eng",
        default_ethnicity="Korean",   # unchanged until a real en cast pack ships (Phase 3)
    ),
}

# Lowercased alias → pack, built once.
_ALIAS_INDEX: dict[str, LocalePack] = {
    alias.lower(): pack for pack in LOCALE_PACKS.values() for alias in pack.aliases
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def resolve_locale_pack(
    brief: dict | None,
    attrs: dict | None = None,
    brand: dict | None = None,
) -> LocalePack | None:
    """Resolve the active LocalePack, or None for the legacy/unknown path.

    Returns None (NOT the ko pack) when nothing resolves, so callers preserve
    their existing env-default fallback and stay byte-identical to today.
    """
    brief = brief or {}
    attrs = attrs or {}
    brand = brand or {}

    # 1. canonical axis (absent in legacy data).
    loc = _norm(brief.get("locale"))
    if loc and loc in _ALIAS_INDEX:
        return _ALIAS_INDEX[loc]

    # 2. Napkin I5 legacy: the FIRST TRUTHY language field decides (byte-identical
    #    to the old _provider_for_language, which only inspected one value).
    legacy = brief.get("language") or attrs.get("language") or brief.get("lang")
    key = _norm(legacy)
    if key and key in _ALIAS_INDEX:
        return _ALIAS_INDEX[key]

    # 3. brand fallback — NEW consumers only (provider path omits `brand`).
    bl = _norm(brand.get("language"))
    if bl and bl in _ALIAS_INDEX:
        return _ALIAS_INDEX[bl]

    return None
