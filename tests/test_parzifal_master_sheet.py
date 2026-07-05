"""ParzifalMasterSheet — 멀티앵글 마스터시트 계약 + ElementLocks 소비 호환 (D-Parzifal)."""
from __future__ import annotations

from hiob_contracts import ParzifalMasterSheet, CharacterMasterSheet, ProductMasterSheet, SheetPanel


def _panel(label, slot="angle", key="k.png"):
    return SheetPanel(slot=slot, label=label, storage_key=key, engine="qwen-image")


def _approved():
    ch = CharacterMasterSheet(
        persona_id="heroine",
        identity={"name": "김수아", "age": "34", "gender": "여성"},
        narrow_target={"activity_context": "야외 물놀이", "interest": "워킹맘"},
        angles=[_panel("front"), _panel("3-4"), _panel("side"), _panel("full-body")],
        expressions=[_panel("neutral", slot="expression"), _panel("smile", slot="expression")],
        wardrobe={"outfit": "버건디 폴로", "forbidden": ["로고"]})
    prod = ProductMasterSheet(sku="eyesafe-500", angles=[_panel("front", key="p.png"), _panel("pour", key="pour.png")])
    return ParzifalMasterSheet(listing_slug="viewok", master_id="m1", version=1, status="approved",
                               engine="qwen-image", characters={"heroine": ch}, product=prod,
                               background={"ref": _panel("bg", slot="detail", key="bg.png"), "text_lock": "실내 수영장"})


def test_hero_panel_prefers_front():
    ch = _approved().character("heroine")
    assert ch.hero_panel().label == "front"


def test_approved_refs_character_product_background():
    refs = _approved().approved_refs("heroine")
    kinds = [r.kind for r in refs]
    assert kinds == ["character", "product", "background"]   # 3-ref 순서(element_locks 동형)


def test_draft_no_op_byte_identical():
    ms = _approved()
    draft = ParzifalMasterSheet.from_dict({**ms.to_dict(), "status": "draft"})
    assert draft.approved_refs("heroine") == []              # draft=소비 no-op
    assert draft.constraint_prompt("heroine") == ""


def test_constraint_prompt_wardrobe_forbidden_narrow():
    p = _approved().constraint_prompt("heroine")
    assert "버건디 폴로" in p and "로고" in p and "물놀이" in p


def test_single_heroine_fallback():
    ms = _approved()
    assert ms.character(None) is not None                    # persona_id 없어도 단일 폴백


def test_to_element_locks_bridge():
    el = _approved().to_element_locks()
    assert el.status == "approved"
    assert el.characters["heroine"].hero_cut.storage_key == "k.png"   # front 컷 브릿지
    assert el.characters["heroine"].sheet["narrow_target"]["interest"] == "워킹맘"


def test_roundtrip_from_to_dict():
    ms = _approved()
    again = ParzifalMasterSheet.from_dict(ms.to_dict())
    assert again.approved_refs("heroine")[0].storage_key == "k.png"
    assert again.character("heroine").narrow_target["activity_context"] == "야외 물놀이"


def test_validate_approved_requires_hero():
    empty = ParzifalMasterSheet(status="approved", characters={"x": CharacterMasterSheet(persona_id="x")})
    assert any("hero" in e for e in empty.validate())        # 승인인데 hero 패널 없음 → 에러
    assert _approved().validate() == []
