import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AtroposFanInManifestV2Schema,
  BeatArtifactSetReceiptV1Schema,
  BeatVideoReceiptV1Schema,
  BeatVideoRequestV1Schema,
  FactoryBeatManifestV1Schema,
  HephaestusFinalRenderReceiptV2Schema,
  ReelsFactoryReceiptV2Schema,
  deriveAtroposFanInManifestDigestV2,
  deriveBeatArtifactSetReceiptDigestV1,
  deriveBeatVideoReceiptDigestV1,
  deriveBeatVideoRequestDigestV1,
  deriveFactoryBeatManifestDigestV1,
  deriveHephaestusFinalRenderReceiptDigestV2,
  deriveReelsFactoryReceiptDigestV2,
} from './index.js';
import { sha256Digest } from './factory/digest.js';

const workspaceId = '00000000-0000-4000-8000-000000000001';
const runId = '00000000-0000-4000-8000-000000000002';
const planDigest = sha256Digest({ plan: 'approved-v2' });
const timelineDigest = sha256Digest({ timeline: 'all-beats' });
const audioMixDigest = sha256Digest({ audio: 'sealed-mix' });
const renderPolicyDigest = sha256Digest({ render: 'vertical-1080p' });

function artifact(
  beatIndex: number | null,
  kind: 'image' | 'video',
  artifactId: string,
  shaSeed: string,
  durationMs: number | null = null,
) {
  return {
    artifact_id: artifactId,
    kind,
    uri: `factory-artifacts/${artifactId}`,
    sha256: sha256Digest({ artifact: shaSeed }),
    mime: kind === 'video' ? 'video/mp4' : 'image/png',
    bytes_len: 2048,
    duration_ms: durationMs,
    width: 1080,
    height: 1920,
    beat_index: beatIndex,
    producer_planet: kind === 'video' ? 'hephaestus' : 'athena',
    producer_node_id: kind === 'video' ? 'video.materialize' : 'image.materialize',
    execution_id: `exec-${artifactId}`,
    producer_revision: 'rev-1',
    image_digest: null,
    source_output_digests: [],
    edge_receipt_digests: [],
    provenance_refs: [],
    consent_refs: [],
  };
}

function manifest() {
  const body = {
    contract_version: 'FactoryBeatManifest.v1' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: 11,
    plan_digest: planDigest,
    beats: [0, 1].map((beatIndex) => ({
      beat_index: beatIndex,
      generation_nonce: `00000000-0000-4000-8000-00000000001${beatIndex}`,
      prompt: `sealed prompt ${beatIndex}`,
      duration_ms: 5000,
      fps: 30,
      width: 1080,
      height: 1920,
      reference_artifacts: [artifact(beatIndex, 'image', `image-${beatIndex}.png`, `image-${beatIndex}`)],
      provider: 'fal',
      model: 'kling-video-v2.1-master',
    })),
  };
  return { ...body, manifest_digest: deriveFactoryBeatManifestDigestV1(body) };
}

function request(beatIndex: number) {
  const factoryManifest = manifest();
  const beat = factoryManifest.beats[beatIndex];
  const body = {
    contract_version: 'BeatVideoRequest.v1' as const,
    workspace_id: workspaceId,
    run_id: runId,
    beat_index: beatIndex,
    factory_revision: factoryManifest.factory_revision,
    plan_digest: planDigest,
    factory_manifest_digest: factoryManifest.manifest_digest,
    generation_nonce: beat.generation_nonce,
    prompt: beat.prompt,
    duration_ms: beat.duration_ms,
    fps: beat.fps,
    width: beat.width,
    height: beat.height,
    reference_artifacts: beat.reference_artifacts,
    provider: beat.provider,
    model: beat.model,
  };
  return { ...body, request_digest: deriveBeatVideoRequestDigestV1(body) };
}

function videoReceipt(beatIndex: number) {
  const videoRequest = request(beatIndex);
  const body = {
    contract_version: 'BeatVideoReceipt.v1' as const,
    workspace_id: workspaceId,
    run_id: runId,
    beat_index: beatIndex,
    factory_revision: videoRequest.factory_revision,
    plan_digest: planDigest,
    factory_manifest_digest: videoRequest.factory_manifest_digest,
    generation_nonce: videoRequest.generation_nonce,
    request_digest: videoRequest.request_digest,
    provider: videoRequest.provider,
    model: videoRequest.model,
    provider_job_id: `provider-job-${beatIndex}`,
    status: 'succeeded' as const,
    artifact: artifact(beatIndex, 'video', `beat-${beatIndex}.mp4`, `video-${beatIndex}`, 5000),
  };
  return { ...body, receipt_digest: deriveBeatVideoReceiptDigestV1(body) };
}

function artifactSet() {
  const factoryManifest = manifest();
  const body = {
    contract_version: 'BeatArtifactSetReceipt.v1' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: factoryManifest.factory_revision,
    plan_digest: planDigest,
    factory_manifest_digest: factoryManifest.manifest_digest,
    expected_beat_count: factoryManifest.beats.length,
    video_receipts: [videoReceipt(0), videoReceipt(1)],
  };
  return { ...body, receipt_digest: deriveBeatArtifactSetReceiptDigestV1(body) };
}

function fanIn() {
  const setReceipt = artifactSet();
  const body = {
    contract_version: 'AtroposFanInManifest.v2' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: setReceipt.factory_revision,
    plan_digest: planDigest,
    factory_manifest_digest: setReceipt.factory_manifest_digest,
    beat_artifact_set_receipt: setReceipt,
    video_artifacts: setReceipt.video_receipts.map((receipt) => receipt.artifact),
    timeline_digest: timelineDigest,
    audio_mix_digest: audioMixDigest,
    render_policy_digest: renderPolicyDigest,
  };
  return { ...body, manifest_digest: deriveAtroposFanInManifestDigestV2(body) };
}

function finalRender() {
  const fanInManifest = fanIn();
  const body = {
    contract_version: 'HephaestusFinalRenderReceipt.v2' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: fanInManifest.factory_revision,
    fan_in_manifest_digest: fanInManifest.manifest_digest,
    status: 'ready' as const,
    output_artifact: artifact(null, 'video', 'final-reel.mp4', 'final-reel', 10000),
    output_url: 'https://cdn.example/final-reel.mp4',
    mechanical_qa_passed: true as const,
    rendered_at_utc: '2026-08-01T08:00:00Z',
  };
  return { ...body, receipt_digest: deriveHephaestusFinalRenderReceiptDigestV2(body) };
}

function factoryReceipt() {
  const factoryManifest = manifest();
  const setReceipt = artifactSet();
  const fanInManifest = fanIn();
  const render = finalRender();
  const body = {
    contract_version: 'ReelsFactoryReceipt.v2' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: factoryManifest.factory_revision,
    plan_digest: planDigest,
    factory_manifest_digest: factoryManifest.manifest_digest,
    beat_artifact_set_receipt_digest: setReceipt.receipt_digest,
    fan_in_manifest_digest: fanInManifest.manifest_digest,
    final_render_receipt: render,
    status: 'succeeded' as const,
    output_url: render.output_url,
    output_sha256: render.output_artifact.sha256,
  };
  return { ...body, receipt_digest: deriveReelsFactoryReceiptDigestV2(body) };
}

test('TypeScript mirror accepts the complete all-beat chain', () => {
  FactoryBeatManifestV1Schema.parse(manifest());
  BeatVideoRequestV1Schema.parse(request(0));
  BeatVideoReceiptV1Schema.parse(videoReceipt(0));
  BeatArtifactSetReceiptV1Schema.parse(artifactSet());
  AtroposFanInManifestV2Schema.parse(fanIn());
  HephaestusFinalRenderReceiptV2Schema.parse(finalRender());
  const result = ReelsFactoryReceiptV2Schema.parse(factoryReceipt());
  assert.equal(result.status, 'succeeded');
});

test('TypeScript mirror rejects gaps, partial fan-in, and output substitution', () => {
  const badManifest = manifest();
  badManifest.beats[1].beat_index = 2;
  badManifest.manifest_digest = deriveFactoryBeatManifestDigestV1(badManifest);
  assert.equal(FactoryBeatManifestV1Schema.safeParse(badManifest).success, false);

  const partial = artifactSet();
  partial.video_receipts = partial.video_receipts.slice(0, 1);
  partial.receipt_digest = deriveBeatArtifactSetReceiptDigestV1(partial);
  assert.equal(BeatArtifactSetReceiptV1Schema.safeParse(partial).success, false);

  const substituted = factoryReceipt();
  substituted.output_url = 'https://cdn.example/substituted.mp4';
  substituted.receipt_digest = deriveReelsFactoryReceiptDigestV2(substituted);
  assert.equal(ReelsFactoryReceiptV2Schema.safeParse(substituted).success, false);
});

test('Python-authoritative canonical digest vectors remain byte-identical', () => {
  assert.equal(
    manifest().manifest_digest,
    'sha256:1fcdf990fae5d519375562bf432291405e990a0f0b2d555b6d3d7e873ae3bb01',
  );
  assert.equal(
    factoryReceipt().receipt_digest,
    'sha256:e48552233e8955af1509e13824f1e5fc919ae7823cc14646b34eef84cc1553c7',
  );
});
