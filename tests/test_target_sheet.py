"""TargetSheet — 4층(Identity·Grounding·Persona·Visual) 계약 왕복 (Parzifal 단일권위자)."""
from __future__ import annotations

from hiob_contracts import CharacterMasterSheet, SheetPanel
from hiob_contracts.target_sheet import (
    TargetSheet, IdentityLayer, GroundingLayer, PersonaLayer,
)


def _sheet() -> TargetSheet:
    visual = CharacterMasterSheet(
        persona_id="heroine",
        identity={"name": "김수아"},
        narrow_target={"activity_context": "야외 물놀이"},
        angles=[SheetPanel(slot="angle", label="front", storage_key="k.png", engine="qwen-image")],
        expressions=[SheetPanel(slot="expression", label="smile", storage_key="s.png")],
        wardrobe={"outfit": "버건디 폴로", "forbidden": ["로고"]})
    return TargetSheet(
        persona_id="heroine",
        identity=IdentityLayer(id="heroine", name="김수아", age=34, age_band="30-40",
                               gender="female", region="서울"),
        grounding=GroundingLayer(pain_points="물안경 김서림", pain_points_source="naver_review",
                                 jtbd="물놀이를 편하게", jtbd_source="catalog"),
        persona=PersonaLayer(protagonist_role="heroine", voice_persona="female1",
                             gender_axis="female_led", narrative_arc="여정의 시작"),
        visual=visual)


def test_roundtrip_to_from_dict():
    ts = _sheet()
    again = TargetSheet.from_dict(ts.to_dict())
    assert again == ts                                       # 4층 전부 무손실 왕복
    assert again.to_dict() == ts.to_dict()                   # 재직렬화 안정성(idempotent)


def test_roundtrip_preserves_visual_layer():
    """visual 층 = CharacterMasterSheet.to_dict/from_dict에 위임되는 계약."""
    again = TargetSheet.from_dict(_sheet().to_dict())
    assert again.visual.hero_panel().storage_key == "k.png"
    assert again.visual.wardrobe["forbidden"] == ["로고"]
    assert again.grounding.pain_points_source == "naver_review"


def test_valid_sheet_validates_clean():
    assert _sheet().validate() == []


def test_from_dict_none_defaults():
    empty = TargetSheet.from_dict(None)
    assert empty.persona_id == ""
    assert empty.visual.hero_panel() is None
    assert any("persona_id" in e for e in empty.validate())
