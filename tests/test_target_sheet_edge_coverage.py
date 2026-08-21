from __future__ import annotations

from hiob_contracts.parzifal_master_sheet import CharacterMasterSheet, SheetPanel
from hiob_contracts.target_sheet import (
    ElementLocksProfile,
    GroundingLayer,
    IdentityLayer,
    PersonaLayer,
    SourceTag,
    TargetProfile,
    TargetSheet,
    build_target_sheet,
    grounding_from_janus_narrow,
    identity_from_janus_narrow,
    persona_from_ares_character,
)


def test_target_layers_reject_unknown_vocab_and_round_trip() -> None:
    identity = IdentityLayer(
        id="persona",
        name="Jin",
        age=36,
        age_band="30-40",
        gender="female",
        region="Seoul",
        background="swimmer",
        language="ko",
        confidence="approved",
    )
    assert identity.validate() == []
    assert IdentityLayer.from_dict(identity.to_dict()) == identity
    assert IdentityLayer.from_dict(None) == IdentityLayer()
    assert IdentityLayer(gender="invalid", confidence="invalid").validate() == [
        "IdentityLayer.id 없음",
        "IdentityLayer.name 없음",
        "IdentityLayer.gender 미지원: invalid",
        "IdentityLayer.confidence 미지원: invalid",
    ]

    grounding = GroundingLayer(
        pain_points="fog",
        pain_points_source="naver_review",
        blocker="visibility",
        blocker_source="catalog",
        jtbd="finish the lane",
        jtbd_source="invented",
        activity_context="training",
        interest="swimming",
        children="none",
        demographics="beginner",
        voc_evidence="I cannot see",
    )
    assert grounding.validate() == []
    assert GroundingLayer.from_dict(grounding.to_dict()) == grounding
    assert GroundingLayer.from_dict(None) == GroundingLayer()
    assert GroundingLayer(
        pain_points_source="bad", blocker_source="bad", jtbd_source="bad"
    ).validate() == [
        "GroundingLayer.pain_points_source 미지원: bad",
        "GroundingLayer.blocker_source 미지원: bad",
        "GroundingLayer.jtbd_source 미지원: bad",
    ]

    persona = PersonaLayer(
        protagonist_role="heroine",
        actor_archetype="beginner swimmer",
        narrative_arc="clear finish",
        voice_persona="female1",
        voice_concept="friendly",
        speaking_style="direct",
        logic_structure="problem-solution",
        tone_and_manner="warm",
        backstory="race day",
        gender_axis="female_led",
        gaze_mode="female_gaze",
    )
    assert persona.validate() == []
    assert PersonaLayer.from_dict(persona.to_dict()) == persona
    assert PersonaLayer.from_dict(None) == PersonaLayer()
    assert PersonaLayer(
        protagonist_role="bad", gender_axis="bad", gaze_mode="bad"
    ).validate() == [
        "PersonaLayer.protagonist_role 미지원: bad",
        "PersonaLayer.gender_axis 미지원: bad",
        "PersonaLayer.gaze_mode 미지원: bad",
    ]


def test_element_locks_and_source_tag_preserve_serialized_values() -> None:
    panel = SheetPanel(slot="angle", label="front", storage_key="front.png")
    profile = ElementLocksProfile(
        persona_id="persona",
        gender_axis="female_led",
        gaze_mode="female_gaze",
        voice_persona="female1",
        protagonist_role="heroine",
        narrative_context="race day",
        angles=[panel, {"slot": "angle", "label": "side"}],
        expressions=[panel],
        wardrobe=[{"outfit": "swimsuit"}],
    )
    assert profile.validate() == []
    wire = profile.to_dict()
    assert wire["angles"][0]["label"] == "front"
    assert wire["angles"][1] == {"slot": "angle", "label": "side"}
    assert ElementLocksProfile.from_dict(wire).persona_id == "persona"
    assert ElementLocksProfile.from_dict(None) == ElementLocksProfile()
    assert ElementLocksProfile(
        protagonist_role="bad", gender_axis="bad", gaze_mode="bad"
    ).validate() == [
        "ElementLocksProfile.protagonist_role 미지원: bad",
        "ElementLocksProfile.gender_axis 미지원: bad",
        "ElementLocksProfile.gaze_mode 미지원: bad",
    ]

    tag = SourceTag(field_name="pain_points", source_type="catalog", evidence="proof")
    assert SourceTag.from_dict(tag.to_dict()) == tag
    assert SourceTag.from_dict(None) == SourceTag()


def test_target_profile_summaries_and_round_trip_every_public_field() -> None:
    assert TargetProfile().vivid_summary() == ""
    assert TargetProfile(name="Jin", age_band="30-40").vivid_summary() == "Jin, 30-40"
    assert TargetProfile(pain_points="fog").vivid_summary() == "fog"

    profile = TargetProfile(
        persona_id="persona",
        name="Jin",
        age=36,
        age_band="30-40",
        gender="female",
        region="Seoul",
        profile_image_placeholder="avatar/female/30-40/cute",
        pain_points="fog",
        blocker="cannot see",
        jtbd="finish safely",
        narrative_arc="clear finish",
        voice_persona="female1",
        speaking_style="direct",
        gender_axis="female_led",
        source_tags=[SourceTag("pain_points", "catalog", "fog")],
        approval_status="ear_test_pending",
    )
    assert profile.vivid_summary() == (
        "Jin, 36세 / Seoul / fog (cannot see) → finish safely"
    )
    assert TargetProfile.from_dict(profile.to_dict()) == profile
    assert TargetProfile.from_dict(None) == TargetProfile()


def _complete_sheet(*, identity_gender: str = "female") -> TargetSheet:
    visual = CharacterMasterSheet(
        persona_id="visual-persona",
        identity={"name": "old"},
        narrow_target={"pain_points": "old"},
        angles=[SheetPanel(slot="angle", label="front", storage_key="front.png")],
        expressions=[SheetPanel(slot="expression", label="smile", storage_key="smile.png")],
        wardrobe={"outfit": "swimsuit"},
    )
    return TargetSheet(
        persona_id="persona",
        identity=IdentityLayer(
            id="persona",
            name="Jin",
            age=36,
            age_band="30-40",
            gender=identity_gender,
            region="Seoul",
        ),
        grounding=GroundingLayer(
            pain_points="fog",
            pain_points_source="naver_review",
            blocker="cannot see",
            blocker_source="catalog",
            jtbd="finish safely",
        ),
        persona=PersonaLayer(
            protagonist_role="heroine",
            narrative_arc="race",
            voice_persona="female1",
            speaking_style="direct",
            backstory="training",
            gender_axis="female_led",
            gaze_mode="female_gaze",
        ),
        visual=visual,
    )


def test_target_sheet_bridges_visual_profile_and_master_sheet() -> None:
    default_sheet = TargetSheet()
    assert "TargetSheet.persona_id 없음" in default_sheet.validate()

    sheet = _complete_sheet()
    assert sheet.validate() == []

    locks = sheet.element_locks_profile()
    assert locks.persona_id == "persona"
    assert locks.narrative_context == "race → training"
    assert locks.angles == sheet.visual.angles

    profile = sheet.as_target_profile()
    assert profile.gender_axis == "female_led"
    assert profile.profile_image_placeholder == "avatar/female/30-40/cute"
    assert [tag.field_name for tag in profile.source_tags] == [
        "pain_points",
        "blocker",
        "jtbd",
    ]
    assert profile.source_tags[-1].source_type == "invented"

    master = sheet.as_master_sheet()
    assert master.persona_id == "visual-persona"
    assert master.identity["name"] == "Jin"
    assert master.narrow_target["pain_points"] == "fog"

    restored = TargetSheet.from_dict(sheet.to_dict())
    assert restored.persona_id == sheet.persona_id
    assert restored.identity == sheet.identity
    assert restored.grounding == sheet.grounding
    assert restored.persona == sheet.persona
    assert TargetSheet.from_dict(None).persona_id == ""

    migrated = TargetSheet.from_master_sheet(master)
    assert migrated.persona_id == master.persona_id
    assert migrated.visual is master
    assert migrated.persona == PersonaLayer()


def test_target_profile_gender_fallbacks_and_empty_narrative() -> None:
    female = _complete_sheet(identity_gender="여성")
    female_without_axis = TargetSheet(
        persona_id=female.persona_id,
        identity=female.identity,
        grounding=GroundingLayer(),
        persona=PersonaLayer(),
        visual=female.visual,
    )
    assert female_without_axis.as_target_profile().gender_axis == "female_led"
    assert female_without_axis.element_locks_profile().narrative_context == ""

    male = TargetSheet(
        persona_id="male",
        identity=IdentityLayer(id="male", name="Min", gender="남성"),
        visual=CharacterMasterSheet(persona_id=""),
    )
    assert male.as_target_profile().gender_axis == "male_led"
    neutral = TargetSheet(
        persona_id="neutral",
        identity=IdentityLayer(id="neutral", name="N", gender="neutral"),
        visual=CharacterMasterSheet(persona_id=""),
    )
    assert neutral.as_target_profile().gender_axis == ""


def test_target_sheet_helpers_map_janus_ares_and_default_visual() -> None:
    identity = identity_from_janus_narrow(
        {
            "id": "persona",
            "name": "Jin",
            "age": "36",
            "age_band": "30-40",
            "gender": "female",
            "region": "Seoul",
            "background": "swimmer",
            "language": "en",
            "confidence": "ear_test_pending",
        }
    )
    assert identity.age == 36
    assert identity_from_janus_narrow(None) == IdentityLayer()

    grounding = grounding_from_janus_narrow(
        {
            "pain_points": "fog",
            "pain_points_source": "catalog",
            "blocker": "visibility",
            "blocker_source": "catalog",
            "jtbd": "finish",
            "jtbd_source": "catalog",
            "activity_context": "race",
            "interest": "swimming",
            "children": "none",
            "demographics": "beginner",
            "voc_evidence": "quote",
        }
    )
    assert grounding.jtbd == "finish"
    assert grounding_from_janus_narrow(None) == GroundingLayer()

    co_star = persona_from_ares_character(
        {
            "protagonist_role": "narrator",
            "actor_archetype": "coach",
            "narrative_arc": "guide",
            "voice_persona": "male1",
            "voice_concept": "calm",
            "speaking_style": "direct",
            "logic_structure": "proof",
            "tone_and_manner": "warm",
            "backstory": "trainer",
        },
        "hero",
    )
    assert co_star.gaze_mode == "neutral"
    assert co_star.gender_axis == "hero"
    explicit = persona_from_ares_character(
        {"protagonist_role": "opponent", "gaze_mode": "female_gaze"}
    )
    assert explicit.gaze_mode == "female_gaze"
    assert persona_from_ares_character(None) == PersonaLayer()

    built = build_target_sheet("persona", identity, grounding, co_star)
    assert built.persona_id == "persona"
    assert built.visual.persona_id == ""
