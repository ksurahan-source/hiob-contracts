"""H0: Beat.scene_direction preserve / round-trip (Ares direction → typed Beat)."""
from hiob_contracts.beat_plan import Beat, BeatPlan, normalize_scene_direction


def test_normalize_scene_direction_caps_and_strips():
    raw = {
        "shot": "x" * 400,
        "subject": "  product in hands  ",
        "setting": "bathroom",
        "junk": "drop",
    }
    out = normalize_scene_direction(raw)
    assert out is not None
    assert out["subject"] == "product in hands"
    assert out["setting"] == "bathroom"
    assert len(out["shot"]) == 300
    assert "junk" not in out


def test_beat_from_dict_preserves_ares_direction_as_scene_direction():
    b = Beat.from_dict({
        "beat_index": 0,
        "text": "line",
        "direction": {
            "shot": "[CU] spray",
            "subject": "UNIQUE_TOKEN_SUBJECT_ABC",
            "setting": "bright bathroom UNIQUE_TOKEN_SETTING_DEF",
            "overlay": "눈에 안전",
        },
    })
    assert b.scene_direction is not None
    assert b.scene_direction["subject"] == "UNIQUE_TOKEN_SUBJECT_ABC"
    assert "UNIQUE_TOKEN_SETTING_DEF" in b.scene_direction["setting"]
    # to_dict emits both keys for Star/Ares compatibility
    d = b.to_dict()
    assert d["scene_direction"]["subject"] == "UNIQUE_TOKEN_SUBJECT_ABC"
    assert d["direction"]["subject"] == "UNIQUE_TOKEN_SUBJECT_ABC"


def test_beat_plan_roundtrip_keeps_scene_direction():
    plan = BeatPlan.from_list([{
        "beat_index": 0,
        "text": "voice line",
        "direction": {
            "shot": "[MCU]",
            "subject": "mom holds product UNIQUE_ROUNDTRIP",
            "setting": "pool deck",
        },
    }, {
        "beat_index": 1,
        "text": "b1",
        "scene_direction": {
            "subject": "product solo UNIQUE_B1",
            "setting": "shelf",
            "shot": "[CU]",
        },
    }])
    assert plan.beat_for(0).scene_direction["subject"].endswith("UNIQUE_ROUNDTRIP")
    assert plan.beat_for(1).scene_direction["subject"].endswith("UNIQUE_B1")
    again = BeatPlan.from_list(plan.to_dict()["beats"])
    assert again.beat_for(0).scene_direction["subject"].endswith("UNIQUE_ROUNDTRIP")
    assert again.beat_for(1).scene_direction["subject"].endswith("UNIQUE_B1")


def test_empty_direction_is_none_not_empty_dict():
    b = Beat.from_dict({"beat_index": 0, "text": "x", "direction": {}})
    assert b.scene_direction is None
