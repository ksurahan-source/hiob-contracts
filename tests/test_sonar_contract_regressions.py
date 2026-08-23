"""Regression guards for Sonar-reported V3 contract cleanups."""

from __future__ import annotations

import inspect

from hiob_contracts import envelope_validation
from hiob_contracts.storyboard_two_stage_v1 import ReelsFactoryFailureReceiptV3


def test_phase_a_registry_declares_star_reels_module_literal_once() -> None:
    source = inspect.getsource(envelope_validation)

    assert source.count('"hiob_contracts.star_reels_view_v1"') == 1


def test_verified_failure_receipt_has_one_terminal_return() -> None:
    source = inspect.getsource(ReelsFactoryFailureReceiptV3.from_verified.__func__)

    assert source.count("return receipt") == 1
