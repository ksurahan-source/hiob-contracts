"""Language-neutral database RPC contracts shared by callers and SQL gates."""
from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def _load_contract(filename: str) -> dict[str, Any]:
    resource = files(__package__).joinpath(filename)
    return json.loads(resource.read_text(encoding="utf-8"))


def load_ares_insert_xl_script_candidate_v2_contract() -> dict[str, Any]:
    """Load the reviewed 0127 Python↔SQL RPC boundary."""

    return _load_contract("ares_insert_xl_script_candidate_v2.json")


def load_ares_claim_xl_paid_writer_v1_contract() -> dict[str, Any]:
    """Load the reviewed 0127 paid-writer reservation RPC boundary."""

    return _load_contract("ares_claim_xl_paid_writer_v1.json")


__all__ = [
    "load_ares_claim_xl_paid_writer_v1_contract",
    "load_ares_insert_xl_script_candidate_v2_contract",
]
