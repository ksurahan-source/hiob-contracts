from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


MANIFEST_PATH = (
    Path(__file__).parents[1]
    / "hiob_contracts"
    / "runtime_node_manifest.json"
)
PARZIFAL_TRUTH_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "parzifal_node_contract_truth_21c8cdac.json"
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
    "output_schema_digest",
    "observed_runtime_contract_digest",
    "error",
    "version",
    "entry_digest",
    "side_effects",
    "source_revision",
    "registry_source",
    "contract_source",
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
        if key != "entry_digest"
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
        expected_registry = (
            "hiob_artemis/node_server/app.py"
            if node["node_id"] == "artemis.references.snapshot"
            else f"hiob_{node['owner']}/node_server/registry.py"
        )
        assert node["registry_source"] == expected_registry
        assert node["contract_source"].startswith(
            f"hiob_{node['owner']}/node_server/"
        )
        assert node["contract_source"].endswith(".py")
        assert node["input"]
        assert node["error"]
        assert node["version"]
        assert isinstance(node["side_effects"], list)
        assert len(node["side_effects"]) == len(set(node["side_effects"]))


def test_outputs_without_real_schema_digests_fail_closed() -> None:
    nodes = _load_manifest()["nodes"]
    assert sum(node["status"] == "active" for node in nodes) == 1
    assert sum(node["status"] == "blocked" for node in nodes) == 44

    blockers = {
        blocker: sum(node["blocker"] == blocker for node in nodes)
        for blocker in {
            "MISSING_TYPED_OUTPUT_CONTRACT",
            "MISSING_OUTPUT_SCHEMA_DIGEST",
            "PARTIAL_OUTPUT_SCHEMA_DIGEST",
            "OUTPUT_EXTENDS_DECLARED_CONTRACT",
            "MISSING_CANONICAL_OUTPUT_VALIDATOR",
            "OUTPUT_WRAPS_DECLARED_CONTRACT",
        }
    }

    assert blockers == {
        "MISSING_TYPED_OUTPUT_CONTRACT": 32,
        "MISSING_OUTPUT_SCHEMA_DIGEST": 8,
        "PARTIAL_OUTPUT_SCHEMA_DIGEST": 1,
        "OUTPUT_EXTENDS_DECLARED_CONTRACT": 1,
        "MISSING_CANONICAL_OUTPUT_VALIDATOR": 1,
        "OUTPUT_WRAPS_DECLARED_CONTRACT": 1,
    }
    for node in nodes:
        if node["status"] == "active":
            assert node["output"]
            assert node["output"] != "UnspecifiedInternalOutput"
            assert DIGEST_RE.fullmatch(node["output_schema_digest"])
            assert node["output_schema_digest"] != "sha256:" + ("0" * 64)
            assert node["observed_runtime_contract_digest"] == (
                node["output_schema_digest"]
            )
            assert node["blocker"] is None
        else:
            assert node["status"] == "blocked"
            assert node["output_schema_digest"] is None
            if node["blocker"] == "MISSING_TYPED_OUTPUT_CONTRACT":
                assert node["output"] is None
            elif node["blocker"] == "MISSING_OUTPUT_SCHEMA_DIGEST":
                assert node["output"]
                assert node["output"] != "UnspecifiedInternalOutput"
            else:
                assert node["blocker"] in {
                    "PARTIAL_OUTPUT_SCHEMA_DIGEST",
                    "OUTPUT_EXTENDS_DECLARED_CONTRACT",
                    "MISSING_CANONICAL_OUTPUT_VALIDATOR",
                    "OUTPUT_WRAPS_DECLARED_CONTRACT",
                }
                assert node["output"]
                assert DIGEST_RE.fullmatch(
                    node["observed_runtime_contract_digest"]
                )


def test_parzifal_manifest_matches_pinned_core_contract_truth() -> None:
    truth = json.loads(PARZIFAL_TRUTH_PATH.read_text())
    manifest_nodes = {
        node["node_id"]: node
        for node in _load_manifest()["nodes"]
    }

    for node_id, expected in truth["nodes"].items():
        actual = manifest_nodes[node_id]
        assert actual["source_revision"] == truth["source_revision"]
        assert actual["registry_source"] == (
            "hiob_parzifal/node_server/registry.py"
        )
        assert actual["contract_source"] == truth["contract_source"]
        assert actual["output"] == expected["output"]
        assert actual["output_schema_digest"] == (
            expected["output_schema_digest"]
        )
        assert actual["observed_runtime_contract_digest"] == (
            expected["observed_runtime_contract_digest"]
        )
        assert actual["status"] == expected["status"]
        assert actual["blocker"] == expected["blocker"]


def test_parzifal_truth_fixture_pins_source_metadata_and_excerpt_hashes() -> None:
    truth = json.loads(PARZIFAL_TRUTH_PATH.read_text())
    provenance = truth["provenance"]

    assert provenance["extraction_method"] == (
        "git show <source_revision>:<source_path> | sed -n '<line_spec>'"
    )
    for source in provenance["sources"]:
        assert DIGEST_RE.fullmatch(source["source_file_sha256"])
        excerpt = PARZIFAL_TRUTH_PATH.parent / source["excerpt_path"]
        observed = "sha256:" + hashlib.sha256(excerpt.read_bytes()).hexdigest()
        assert observed == source["excerpt_sha256"]


def test_entry_digests_are_nonzero_and_bind_each_full_entry() -> None:
    nodes = _load_manifest()["nodes"]

    for node in nodes:
        assert DIGEST_RE.fullmatch(node["entry_digest"])
        assert node["entry_digest"] != "sha256:" + ("0" * 64)
        assert node["entry_digest"] == _digest(node)


def test_built_wheel_contains_runtime_node_manifest(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to verify the distributable wheel"
    subprocess.run(
        [
            uv,
            "build",
            "--wheel",
            "--out-dir",
            str(tmp_path),
        ],
        cwd=MANIFEST_PATH.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        assert "hiob_contracts/runtime_node_manifest.json" in archive.namelist()
