from hiob_contracts.shot_list import ShotList, ShotMetadata


def test_shot_list_round_trips_typed_frame_intent():
    shots = ShotList.from_list([
        {
            "beat_index": 0,
            "render_mode": "hands_demo",
            "shot_size": "insert",
            "angle": "high",
            "lens": "macro",
            "composition": "center",
            "direction": "none",
            "gesture": "demonstrating_product",
            "product_intent": "demonstrated",
        }
    ])
    assert shots.validate() == []
    assert shots.to_dict()["shots"][0]["product_intent"] == "demonstrated"


def test_shot_list_rejects_lens_and_direction_contradictions():
    shots = ShotList((
        ShotMetadata(
            beat_index=1,
            shot_size="wide",
            lens="macro",
            direction="camera_left",
            continuity_cue="same_subject_from_right",
        ),
    ))
    errors = shots.validate()
    assert any("macro lens conflicts" in error for error in errors)
    assert any("direction conflicts" in error for error in errors)
