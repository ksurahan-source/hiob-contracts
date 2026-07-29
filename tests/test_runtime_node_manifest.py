from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


MANIFEST_PATH = (
    Path(__file__).parents[1]
    / "hiob_contracts"
    / "runtime_node_manifest.json"
)
EXPECTED_REVISIONS = {
    "janus": "73d16f79f9dd24972fcbe350f8dbba013826d96b",
    "karma": "bc5561de963bd5db9bf8eff860980ed94e38b1ba",
    "parzifal": "21c8cdac5fb5627d189c97ddf806532742868293",
    "artemis": "4bf754e326fe9f9590a419c53f1552064287ee19",
    "ares": "173df263a8a5100f05adef421471033465e1ee71",
    "athena": "612f7a2f585f5dcd086aaf8e435e2cada3933cdc",
    "orpheus": "4f453de621f2c865b3ab2549056f1e8aa2581ffe",
    "apollo": "9a516a492e3b6e201d03dd129e590f7c055af162",
    "atropos": "a7dd805d20be9129bcc4cd152ab369d9112ae96d",
}
EXPECTED_NODE_IDS = {
    "janus.intake.interpret",
    "janus.url.ingest",
    "janus.proof.harvest",
    "janus.product.seal",
    "karma.reconcile",
    "karma.edge.refine",
    "parzifal.target.consolidate",
    "parzifal.target.generate",
    "parzifal.references.snapshot",
    "parzifal.identity.seal",
    "parzifal.voice.seal",
    "artemis.references.snapshot",
    "artemis.evidence.seal",
    "ares.script.build_kit",
    "ares.script.build",
    "ares.script.prepare_generation",
    "ares.revision.seal_generated_pair",
    "ares.revision.assemble_pair",
    "ares.script.assemble_revision",
    "ares.plan.assemble_revision",
    "ares.script.critic_review",
    "ares.voice.review",
    "ares.visual.seal",
    "athena.director.plan",
    "athena.visual.frame_plan",
    "athena.visual.from_ares_revision",
    "athena.visual.materialize_receipt",
    "athena.visual.plan",
    "athena.visual.safe_prompt",
    "orpheus.audio.select_music",
    "orpheus.audio.resolve_voice",
    "orpheus.audio.synthesize_voice",
    "orpheus.audio.consume_sealed_voice",
    "orpheus.audio.materialize_receipt",
    "orpheus.audio.render_tts",
    "orpheus.audio.validate_sealed_clip",
    "orpheus.audio.validate_sealed_music_clip",
    "apollo.sfx.select",
    "apollo.sfx.from_plan",
    "apollo.sfx.materialize",
    "atropos.draft",
    "atropos.typed_snapshot",
    "atropos.compose_and_render_v2",
    "atropos.ares.persist_script_revision",
    "atropos.ares.persist_plan_revision",
}
REQUIRED_FIELDS = {
    "node_id",
    "owner",
    "input",
    "output",
    "error",
    "version",
    "schema_digest",
    "side_effects",
    "source_revision",
    "registry_source",
    "status",
    "blocker",
}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def _digest(node: dict) -> str:
    descriptor = {
        key: value
        for key, value in node.items()
        if key != "schema_digest"
    }
    canonical = json.dumps(
        descriptor,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def test_manifest_freezes_exact_latest_origin_main_inventory() -> None:
    manifest = _load_manifest()
    nodes = manifest["nodes"]

    assert manifest["manifest_version"] == "runtime-node-contracts.v1"
    assert manifest["node_count"] == 45
    assert len(nodes) == 45
    assert {node["node_id"] for node in nodes} == EXPECTED_NODE_IDS
    assert len({node["node_id"] for node in nodes}) == 45


def test_every_node_pins_required_contract_and_source_fields() -> None:
    nodes = _load_manifest()["nodes"]

    for node in nodes:
        assert set(node) == REQUIRED_FIELDS
        assert node["owner"] == node["node_id"].split(".", 1)[0]
        assert node["source_revision"] == EXPECTED_REVISIONS[node["owner"]]
        assert node["registry_source"].startswith(
            f"hiob_{node['owner']}/node_server/"
        )
        assert node["registry_source"].endswith(".py")
        assert node["input"]
        assert node["error"]
        assert node["version"]
        assert isinstance(node["side_effects"], list)
        assert len(node["side_effects"]) == len(set(node["side_effects"]))


def test_active_outputs_are_typed_and_untyped_outputs_fail_closed() -> None:
    nodes = _load_manifest()["nodes"]

    for node in nodes:
        if node["status"] == "active":
            assert node["output"]
            assert node["output"] != "UnspecifiedInternalOutput"
            assert node["blocker"] is None
        else:
            assert node["status"] == "blocked"
            assert node["output"] is None
            assert node["blocker"] == "MISSING_TYPED_OUTPUT_CONTRACT"


def test_schema_digests_are_nonzero_and_bind_each_full_entry() -> None:
    nodes = _load_manifest()["nodes"]

    for node in nodes:
        assert DIGEST_RE.fullmatch(node["schema_digest"])
        assert node["schema_digest"] != "sha256:" + ("0" * 64)
        assert node["schema_digest"] == _digest(node)
