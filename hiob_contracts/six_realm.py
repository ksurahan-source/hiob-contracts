"""TMPL-6DO: 六道 감정 상태별 캡션·SFX·전환 craft 프리셋 레지스트리.

각 레알름 → {caption_position, sfx_category, transition} 결정적 매핑.
미지정 레알름 → None 반환 (caption_position 미주입 = 기존 렌더 byte-identical 유지).
"""
from __future__ import annotations

from typing import TypedDict


class SixDoPreset(TypedDict):
    caption_position: str  # 'top' | 'mid-top' | 'mid' | 'mid-bottom'
    sfx_category: str
    transition: str


# Meta Reels 세이프존 기준(1080×1920):
#   상단 14% = 269px 회피  ·  하단 35% = y>1248px 회피  ·  우측 15% = x>918px 회피
# 각 position 프리셋의 y+height 는 1248px 이하에 클램프됨 (렌더러 SIX_DO_CAPTION_POSITIONS 참조).
REALM_CRAFT_PRESETS: dict[str, SixDoPreset] = {
    # PROBLEM 레알름 — 긴장·수축
    "지옥":   {"caption_position": "mid",        "sfx_category": "impact",  "transition": "cut"},
    "축생":   {"caption_position": "mid-top",    "sfx_category": "tense",   "transition": "cut"},
    "아수라": {"caption_position": "top",         "sfx_category": "impact",  "transition": "flash"},
    # TRANSITION 레알름 — 도전·열망
    "인간":   {"caption_position": "mid",        "sfx_category": "neutral", "transition": "cut"},
    "아귀":   {"caption_position": "mid-bottom", "sfx_category": "hope",    "transition": "dissolve"},
    # SOLUTION 레알름 — 해소·개방
    "천상":   {"caption_position": "top",        "sfx_category": "soft",    "transition": "dissolve"},
}

# SFX 큐 매핑: 각 emotion(六道 realm) → canonical SFX cue name (APOLLO가 소비).
# 미지정 emotion → "" (no SFX, silent).
REALM_TO_SFX_CUE: dict[str, str] = {
    # PROBLEM — tension, impact, danger
    "지옥":   "impact-kick",       # sharp percussive hit (urgency)
    "축생":   "impact-snap",       # snappy, quick (tension spike)
    "아수라": "ambient-impact",    # layered impact (conflict)
    # TRANSITION — neutral, rise, anticipation
    "인간":   "neutral-click",     # minimal, grounding (observation)
    "아귀":   "hope-uplift",       # ascending, positive (transformation)
    # SOLUTION — soft, release, opening
    "천상":   "soft-whoosh",       # gentle, open (resolution)
}


def get_realm_preset(realm: str) -> SixDoPreset | None:
    """Return craft preset for a six-realm label, or None for unknown (byte-identical)."""
    return REALM_CRAFT_PRESETS.get(realm)


def get_sfx_cue_for_emotion(emotion: str) -> str:
    """Map emotion (six-realm label) → SFX cue name for APOLLO.

    Args:
        emotion: 六道 realm (지옥, 축생, 아수라, 인간, 아귀, 천상) or any string.

    Returns:
        Canonical SFX cue name (e.g., "impact-kick"), or "" if not mapped (silent).
    """
    emotion = str(emotion or "").strip()
    return REALM_TO_SFX_CUE.get(emotion, "")
