"""Regression tests for the dynamic all-beat Star Reels budget."""
from __future__ import annotations

import pytest

from hiob_contracts.star_reels_view_v1 import _StarReelsBudgetMultiBeatV1


def _budget(**overrides):
    value = {
        "script": 1,
        "image": 2,
        "voice": 2,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }
    value.update(overrides)
    return value


def test_star_reels_budget_allows_positive_per_beat_image_and_voice_counts():
    budget = _StarReelsBudgetMultiBeatV1.model_validate(_budget(image=12, voice=12))
    assert budget.image == budget.voice == 12
    assert budget.script == budget.render == 1


@pytest.mark.parametrize("field", ["image", "voice"])
@pytest.mark.parametrize("value", [0, -1])
def test_star_reels_budget_rejects_non_positive_beat_counts(field, value):
    with pytest.raises(Exception):
        _StarReelsBudgetMultiBeatV1.model_validate(_budget(**{field: value}))


@pytest.mark.parametrize("image,voice", [(17, 17), (2, 3)])
def test_star_reels_budget_is_bounded_and_equal_per_beat(image, voice):
    with pytest.raises(Exception):
        _StarReelsBudgetMultiBeatV1.model_validate(_budget(image=image, voice=voice))
