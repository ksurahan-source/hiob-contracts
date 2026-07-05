"""ElementLocks 계약 테스트 — 도면 락·히어로컷·3-ref 소비 API (E-1)."""
from __future__ import annotations

from hiob_contracts import (
    ElementLocks, ElementRef, CharacterLock, ProductLock, BackgroundLock,
    ensure_valid, validate_payload, registered_contracts,
)

APPROVED = {
    "version": 3,
    "status": "approved",
    "authored_by": "claude-fable-5",
    "characters": {
        "heroine": {
            "hero_cut": {"storage_key": "viewok/el/heroine_v3.png", "derived_from": "master v3"},
            "voice_persona": "female1",
            "sheet": {
                "identity": "한국 여성 20대 중반 단발",
                "wardrobe": {"outfit": "버건디 폴로 + 와이드 데님",
                             "palette": ["#8b2635"], "forbidden": ["로고 티셔츠", "수영복 외 노출"]},
            },
        }
    },
    "product": {"hero_cut": {"storage_key": "viewok/el/product_v3.png"},
                "sheet": {"constraints": ["실물만·AI발명 금지", "라벨 가독"]}},
    "background": {"hero_cut": {"storage_key": "viewok/el/bg_v3.png"},
                   "text_lock": "이른 아침 수영장, 자연광"},
    "version_history": [{"version": 2, "changed_by": "founder"}],
}


def test_registered():
    assert "ElementLocks" in registered_contracts()


def test_from_dict_roundtrip():
    el = ElementLocks.from_dict(APPROVED)
    assert el.version == 3 and el.is_approved
    assert el.character("heroine").voice_persona == "female1"
    assert el.to_dict()["characters"]["heroine"]["hero_cut"]["storage_key"] == "viewok/el/heroine_v3.png"


def test_approved_refs_returns_three_hero_cuts_in_order():
    el = ElementLocks.from_dict(APPROVED)
    refs = el.approved_refs("heroine")
    assert [r.kind for r in refs] == ["character", "product", "background"]
    assert refs[0].storage_key == "viewok/el/heroine_v3.png"
    assert refs[2].storage_key == "viewok/el/bg_v3.png"


def test_draft_yields_no_refs_and_no_prompt():
    d = dict(APPROVED, status="draft")
    el = ElementLocks.from_dict(d)
    assert el.approved_refs("heroine") == []
    assert el.constraint_prompt("heroine") == ""


def test_constraint_prompt_includes_wardrobe_product_background():
    el = ElementLocks.from_dict(APPROVED)
    p = el.constraint_prompt("heroine")
    assert "버건디 폴로" in p
    assert "로고 티셔츠" in p                 # forbidden
    assert "실물" in p                          # product constraint
    assert "배경 락" in p                       # background


def test_single_character_fallback_on_persona_mismatch():
    el = ElementLocks.from_dict(APPROVED)
    # unknown persona_id → single-character fallback
    refs = el.approved_refs("someone_else")
    assert refs and refs[0].kind == "character"


def test_validate_approved_requires_a_hero_cut():
    empty_approved = ElementLocks(version=1, status="approved")
    errs = empty_approved.validate()
    assert any("히어로컷" in e for e in errs)
    ok = ElementLocks.from_dict(APPROVED)
    assert ok.validate() == []


def test_ensure_valid_via_envelope():
    obj = ensure_valid("ElementLocks", APPROVED)
    assert isinstance(obj, ElementLocks) and obj.is_approved


def test_partial_locks_only_available_refs():
    # only product hero_cut present
    partial = {"version": 1, "status": "approved",
               "product": {"hero_cut": {"storage_key": "p.png"}}}
    el = ElementLocks.from_dict(partial)
    refs = el.approved_refs("x")
    assert [r.kind for r in refs] == ["product"]
    assert el.validate() == []
