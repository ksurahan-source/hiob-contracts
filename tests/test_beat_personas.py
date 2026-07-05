"""BeatPersonas 계약 테스트 — Ares→Athena seam 정형화."""
from __future__ import annotations

from hiob_contracts.beat_personas import BeatPersona, BeatPersonas, RENDER_MODES
from hiob_contracts import BeatPersona as BP_export, BeatPersonas as BPS_export
from hiob_contracts import ensure_valid, validate_payload, ContractViolation, registered_contracts


REAL = [
    {"id": "narrator", "render_mode": "still", "emotion": "curiosity", "scene_type": "hook",
     "gender": "female", "role": "guide", "image": "hero_cut_1", "face_lock_id": "f1",
     "wardrobe": "casual", "setting": "bathroom", "locks_accessories": ["glasses"]},
    {"persona_id": "lead", "render_mode": "video", "emotion": "지옥", "scene_type": "problem",
     "social_proof_style": None, "gender": "female"},
    {"id": "reviewer", "render_mode": "proof", "social_proof_style": "screenshot", "scene_type": "proof"},
]


def test_exports_wired():
    assert BP_export is BeatPersona and BPS_export is BeatPersonas
    assert "BeatPersonas" in registered_contracts()
    assert "BeatPersona" in registered_contracts()


def test_from_list_assigns_beat_index_from_position():
    bps = BeatPersonas.from_list(REAL)
    assert len(bps) == 3
    assert [p.beat_index for p in bps] == [0, 1, 2]
    assert bps.by_beat(1).persona_id == "lead"
    assert bps.by_beat(0).persona_id == "narrator"


def test_from_dict_aliases_and_accessories():
    p = BeatPersona.from_dict(REAL[0], beat_index=0)
    assert p.persona_id == "narrator"           # id → persona_id
    assert p.face_lock_id == "f1"
    assert p.locks_accessories == ("glasses",)   # list preserved
    p2 = BeatPersona.from_dict({"id": "x", "locks_accessories": "hat"}, beat_index=5)
    assert p2.locks_accessories == ("hat",)      # str → tuple


def test_render_mode_normalization():
    assert BeatPersona(beat_index=0, render_mode="image").normalized_render_mode() == "still"
    assert BeatPersona(beat_index=0, render_mode="kling").normalized_render_mode() == "avatar"
    assert BeatPersona(beat_index=0, render_mode="proof").normalized_render_mode() == "social_proof"
    # 미지값 보존
    assert BeatPersona(beat_index=0, render_mode="weird").normalized_render_mode() == "weird"


def test_is_social_proof():
    assert BeatPersonas.from_list(REAL).by_beat(2).is_social_proof is True
    assert BeatPersonas.from_list(REAL).by_beat(0).is_social_proof is False


def test_validate_requires_beat_index_and_unique():
    ok = BeatPersonas.from_list(REAL)
    assert ok.validate() == []
    dup = BeatPersonas(personas=(BeatPersona(beat_index=1), BeatPersona(beat_index=1)))
    assert any("중복" in e for e in dup.validate())


def test_ensure_valid_roundtrip_via_envelope():
    obj = ensure_valid("BeatPersonas", REAL)
    assert isinstance(obj, BeatPersonas)
    assert len(obj) == 3
    # to_list round-trip stable
    again = BeatPersonas.from_list(obj.to_list())
    assert again.to_list() == obj.to_list()


def test_validate_payload_reports_bad_beat_index():
    bad = BeatPersonas(personas=(BeatPersona(beat_index=None),))  # type: ignore[arg-type]
    r = validate_payload("BeatPersonas", bad)
    assert r.ok is False
    assert any("beat_index" in e for e in r.errors)


def test_render_modes_vocab_present():
    for m in ("still", "video", "avatar", "social_proof"):
        assert m in RENDER_MODES
