"""BFA-2 LockRegistry schema round-trip."""
from hiob_contracts.factory.lock_registry import LockEntry, LockRegistry, lock_registry_from_dict


def test_lock_registry_roundtrip():
    reg = LockRegistry(
        run_id="r1",
        workspace_id="w1",
        locks=[
            LockEntry(lock_key="environment_lock", owner="karma", force_level="hard", value={"loc": "pool"}),
            LockEntry(lock_key="face_seed", owner="parzifal", force_level="soft"),
        ],
    )
    raw = reg.model_dump()
    back = lock_registry_from_dict(raw)
    assert back.run_id == "r1"
    assert back.get("environment_lock").force_level == "hard"
    assert back.get("missing") is None
    updated = back.upsert(LockEntry(lock_key="environment_lock", owner="karma", force_level="advisory", value=1))
    assert updated.get("environment_lock").force_level == "advisory"
    assert len(updated.locks) == 2
