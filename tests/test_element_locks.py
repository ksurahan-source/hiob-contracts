"""ElementLocks 계약 테스트 — 도면 락·히어로컷·3-ref 소비 API (E-1) + BW·T22 스코프."""
from __future__ import annotations

from hiob_contracts import (
    ElementLocks, ElementRef, CharacterLock, ProductLock, BackgroundLock,
    ensure_valid, validate_payload, registered_contracts, standing_lookup,
)

APPROVED = {
    "version": 3,
    "status": "approved",
    "authored_by": "claude-fable-5",
    "workspace_id": "ws-viewok",
    "brand_slug": "viewok",
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
    assert el.workspace_id == "ws-viewok" and el.brand_slug == "viewok"
    assert el.character("heroine").voice_persona == "female1"
    assert el.to_dict()["characters"]["heroine"]["hero_cut"]["storage_key"] == "viewok/el/heroine_v3.png"
    assert el.to_dict()["workspace_id"] == "ws-viewok"
    assert el.to_dict()["brand_slug"] == "viewok"


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


def test_persona_mismatch_zero_fallback():
    """BW·T22: persona_id 미스매치 시 단일 히로인 상속 금지 (폴백 0)."""
    el = ElementLocks.from_dict(APPROVED)
    assert el.character("someone_else") is None
    refs = el.approved_refs("someone_else")
    # character ref 없음; product/background만 (persona-scoped 아님)
    assert all(r.kind != "character" for r in refs)
    assert [r.kind for r in refs] == ["product", "background"]


def test_standing_lookup_scope_mismatch_empty():
    """LP2-4 VERIFY: 불일치 스코프 조회 → 빈 결과 (None)."""
    store = [
        ElementLocks.from_dict(APPROVED),
        ElementLocks.from_dict({
            **APPROVED,
            "workspace_id": "ws-other",
            "brand_slug": "alive",
            "characters": {
                "heroine": {
                    "hero_cut": {"storage_key": "alive/el/leak.png"},
                    "voice_persona": "female2",
                }
            },
        }),
    ]
    # wrong brand
    assert standing_lookup(store, workspace_id="ws-viewok", brand_slug="alive") is None
    # wrong workspace
    assert standing_lookup(store, workspace_id="ws-other", brand_slug="viewok") is None
    # empty scope args
    assert standing_lookup(store, workspace_id="", brand_slug="viewok") is None
    assert standing_lookup(store, workspace_id="ws-viewok", brand_slug="") is None
    # for_scope / approved_refs kwargs also empty on mismatch
    el = ElementLocks.from_dict(APPROVED)
    assert el.for_scope("ws-other", "viewok") is None
    assert el.approved_refs("heroine", workspace_id="ws-viewok", brand_slug="alive") == []
    assert el.constraint_prompt("heroine", workspace_id="ws-other", brand_slug="viewok") == ""


def test_standing_lookup_exact_scope_hit():
    """Exact (workspace_id, brand_slug) dual-key hit returns the matching record only."""
    viewok = ElementLocks.from_dict(APPROVED)
    alive = ElementLocks.from_dict({
        **APPROVED,
        "workspace_id": "ws-alive",
        "brand_slug": "alive",
        "characters": {
            "heroine": {
                "hero_cut": {"storage_key": "alive/el/heroine.png"},
                "voice_persona": "female2",
            }
        },
    })
    store = [viewok, alive]
    hit = standing_lookup(store, workspace_id="ws-viewok", brand_slug="viewok")
    assert hit is not None
    assert hit.brand_slug == "viewok"
    assert hit.character("heroine").hero_cut.storage_key == "viewok/el/heroine_v3.png"
    hit2 = standing_lookup(store, workspace_id="ws-alive", brand_slug="alive")
    assert hit2 is not None and hit2.brand_slug == "alive"
    # unscoped record never matches (no inheritance of bare standing data)
    bare = ElementLocks.from_dict({**APPROVED, "workspace_id": "", "brand_slug": ""})
    assert standing_lookup([bare], workspace_id="ws-viewok", brand_slug="viewok") is None
    # scoped approved_refs green path
    refs = viewok.approved_refs(
        "heroine", workspace_id="ws-viewok", brand_slug="viewok",
    )
    assert [r.kind for r in refs] == ["character", "product", "background"]


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
