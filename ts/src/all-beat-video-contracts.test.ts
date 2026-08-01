import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AtroposFanInManifestV2Schema,
  AtroposFanInManifestV3Schema,
  BeatArtifactSetReceiptV1Schema,
  BeatVideoReceiptV1Schema,
  BeatVideoRequestV1Schema,
  FactoryBeatManifestV1Schema,
  HephaestusFinalRenderReceiptV2Schema,
  ReelsFactoryReceiptV2Schema,
  beatVideoRequestBindsManifestV1,
  reelsFactoryReceiptBindsChainV2,
  deriveFactoryBeatManifestIdempotencyKeyV1,
  deriveAtroposFanInManifestDigestV2,
  deriveAtroposFanInManifestDigestV3,
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
const authorityDigest = sha256Digest({ authority: 'paid-all-beats' });

function artifact(
  beatIndex: number | null,
  kind: 'audio' | 'image' | 'video',
  artifactId: string,
  shaSeed: string,
  durationMs: number | null = null,
) {
  const isVideo = kind === 'video';
  const isAudio = kind === 'audio';
  return {
    artifact_id: artifactId,
    kind,
    uri: `factory-artifacts/${artifactId}`,
    sha256: sha256Digest({ artifact: shaSeed }),
    mime: isVideo ? 'video/mp4' : isAudio ? 'audio/mpeg' : 'image/png',
    bytes_len: 2048,
    duration_ms: durationMs,
    width: isAudio ? null : 1080,
    height: isAudio ? null : 1920,
    beat_index: beatIndex,
    producer_planet: isVideo ? 'hephaestus' : isAudio ? 'orpheus' : 'athena',
    producer_node_id: isVideo
      ? 'video.materialize'
      : isAudio
        ? 'voice.materialize'
        : 'image.materialize',
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
    paid_budget_authority_digest: authorityDigest,
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
  const withKey = { ...body, idempotency_key: deriveFactoryBeatManifestIdempotencyKeyV1(body) };
  return { ...withKey, manifest_digest: deriveFactoryBeatManifestDigestV1(withKey) };
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
    paid_budget_authority_digest: authorityDigest,
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
    paid_budget_authority_digest: authorityDigest,
    factory_manifest_digest: videoRequest.factory_manifest_digest,
    generation_nonce: videoRequest.generation_nonce,
    request_digest: videoRequest.request_digest,
    duration_ms: videoRequest.duration_ms,
    fps: videoRequest.fps,
    width: videoRequest.width,
    height: videoRequest.height,
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
    paid_budget_authority_digest: authorityDigest,
    factory_manifest_digest: factoryManifest.manifest_digest,
    expected_beat_count: factoryManifest.beats.length,
    video_receipts: [videoReceipt(0), videoReceipt(1)],
  };
  return { ...body, receipt_digest: deriveBeatArtifactSetReceiptDigestV1(body) };
}

function fanInV2() {
  const setReceipt = artifactSet();
  const body = {
    contract_version: 'AtroposFanInManifest.v2' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: setReceipt.factory_revision,
    plan_digest: planDigest,
    paid_budget_authority_digest: authorityDigest,
    factory_manifest_digest: setReceipt.factory_manifest_digest,
    beat_artifact_set_receipt: setReceipt,
    video_artifacts: setReceipt.video_receipts.map((receipt) => receipt.artifact),
    timeline_digest: timelineDigest,
    audio_mix_digest: audioMixDigest,
    render_policy_digest: renderPolicyDigest,
  };
  return { ...body, manifest_digest: deriveAtroposFanInManifestDigestV2(body) };
}

function fanInV3() {
  const setReceipt = artifactSet();
  const audioArtifacts = [0, 1].map((beatIndex) => (
    artifact(beatIndex, 'audio', `voice-${beatIndex}.mp3`, `audio-${beatIndex}`, 5000)
  ));
  const body = {
    contract_version: 'AtroposFanInManifest.v3' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: setReceipt.factory_revision,
    plan_digest: planDigest,
    paid_budget_authority_digest: authorityDigest,
    factory_manifest_digest: setReceipt.factory_manifest_digest,
    beat_artifact_set_receipt: setReceipt,
    video_artifacts: setReceipt.video_receipts.map((receipt) => receipt.artifact),
    audio_artifacts: audioArtifacts,
    timeline_digest: timelineDigest,
    audio_mix_digest: sha256Digest({ audio_artifacts: audioArtifacts }),
    render_policy_digest: renderPolicyDigest,
  };
  return { ...body, manifest_digest: deriveAtroposFanInManifestDigestV3(body) };
}

function finalRender(
  fanInManifest: ReturnType<typeof fanInV2> | ReturnType<typeof fanInV3> = fanInV3(),
) {
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

function factoryReceipt(
  fanInManifest: ReturnType<typeof fanInV2> | ReturnType<typeof fanInV3> = fanInV3(),
) {
  const factoryManifest = manifest();
  const setReceipt = artifactSet();
  const render = finalRender(fanInManifest);
  const body = {
    contract_version: 'ReelsFactoryReceipt.v2' as const,
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: factoryManifest.factory_revision,
    plan_digest: planDigest,
    paid_budget_authority_digest: authorityDigest,
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
  const parsedManifest = FactoryBeatManifestV1Schema.parse(manifest());
  BeatVideoRequestV1Schema.parse(request(0));
  BeatVideoReceiptV1Schema.parse(videoReceipt(0));
  BeatArtifactSetReceiptV1Schema.parse(artifactSet());
  AtroposFanInManifestV3Schema.parse(fanInV3());
  HephaestusFinalRenderReceiptV2Schema.parse(finalRender());
  const parsedSet = BeatArtifactSetReceiptV1Schema.parse(artifactSet());
  const parsedFanIn = AtroposFanInManifestV3Schema.parse(fanInV3());
  const result = ReelsFactoryReceiptV2Schema.parse(factoryReceipt());
  assert.equal(result.status, 'succeeded');
  assert.deepEqual(parsedFanIn.audio_artifacts.map((item) => item.beat_index), [0, 1]);
  assert.equal(reelsFactoryReceiptBindsChainV2(result, parsedManifest, parsedSet, parsedFanIn), true);
});

test('stored V2 fan-in and factory receipt remain byte-compatible', () => {
  const fanInManifest = AtroposFanInManifestV2Schema.parse(fanInV2());
  const result = ReelsFactoryReceiptV2Schema.parse(factoryReceipt(fanInV2()));
  assert.equal(
    fanInManifest.manifest_digest,
    'sha256:5898d7f56f6cf323fc099e3a3bc1181caf4adf203927541a0ec0a2784417b268',
  );
  assert.equal(
    result.receipt_digest,
    'sha256:8aaa8f391e121cffe978c0c2026ef3b10b0ebd06fefd520da440c437447bbd6f',
  );
  assert.equal(reelsFactoryReceiptBindsChainV2(
    result,
    FactoryBeatManifestV1Schema.parse(manifest()),
    BeatArtifactSetReceiptV1Schema.parse(artifactSet()),
    fanInManifest,
  ), true);
  assert.equal(AtroposFanInManifestV2Schema.safeParse({
    ...fanInV2(), audio_artifacts: fanInV3().audio_artifacts,
  }).success, false);
});

test('mirror rejects a rehashed request that drifts from its manifest beat', () => {
  const parsedManifest = FactoryBeatManifestV1Schema.parse(manifest());
  const drifted = request(0);
  drifted.prompt = 'independently valid but unauthorized prompt';
  drifted.request_digest = deriveBeatVideoRequestDigestV1(drifted);
  const parsedRequest = BeatVideoRequestV1Schema.parse(drifted);
  assert.equal(beatVideoRequestBindsManifestV1(parsedRequest, parsedManifest), false);
});

test('mirror rejects unsafe canonical values and impossible UTC dates', () => {
  assert.throws(() => deriveFactoryBeatManifestDigestV1({ unsafe: Number.MAX_SAFE_INTEGER + 1 }));
  assert.throws(() => deriveFactoryBeatManifestDigestV1({ surrogate: '\ud800' }));
  const surrogateRequest = request(0);
  surrogateRequest.prompt = '\ud800';
  assert.doesNotThrow(() => BeatVideoRequestV1Schema.safeParse(surrogateRequest));
  assert.equal(BeatVideoRequestV1Schema.safeParse(surrogateRequest).success, false);
  const sparse: unknown[] = [];
  sparse[1] = 'x';
  assert.throws(() => deriveFactoryBeatManifestDigestV1({ sparse }));
  const render = finalRender();
  render.rendered_at_utc = '2026-02-31T08:00:00Z';
  render.receipt_digest = deriveHephaestusFinalRenderReceiptDigestV2(render);
  assert.equal(HephaestusFinalRenderReceiptV2Schema.safeParse(render).success, false);
  for (const outputUrl of ['https:///missing-host.mp4', 'https://user:pass@cdn.example/out.mp4']) {
    const invalidUrl = finalRender();
    invalidUrl.output_url = outputUrl;
    invalidUrl.receipt_digest = deriveHephaestusFinalRenderReceiptDigestV2(invalidUrl);
    assert.equal(HephaestusFinalRenderReceiptV2Schema.safeParse(invalidUrl).success, false);
  }
});

test('manifest accepts revision zero and caps all-beat count at sixteen', () => {
  const revisionZero = manifest();
  revisionZero.factory_revision = 0;
  revisionZero.idempotency_key = deriveFactoryBeatManifestIdempotencyKeyV1(revisionZero);
  revisionZero.manifest_digest = deriveFactoryBeatManifestDigestV1(revisionZero);
  assert.equal(FactoryBeatManifestV1Schema.parse(revisionZero).factory_revision, 0);
  const tooMany = manifest();
  tooMany.beats = Array.from({ length: 17 }, (_, index) => ({
    ...structuredClone(tooMany.beats[0]), beat_index: index,
    generation_nonce: `00000000-0000-4000-8000-${index.toString().padStart(12, '0')}`,
    reference_artifacts: [{ ...structuredClone(tooMany.beats[0].reference_artifacts[0]), beat_index: index }],
  }));
  tooMany.idempotency_key = deriveFactoryBeatManifestIdempotencyKeyV1(tooMany);
  tooMany.manifest_digest = deriveFactoryBeatManifestDigestV1(tooMany);
  assert.equal(FactoryBeatManifestV1Schema.safeParse(tooMany).success, false);
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

test('TypeScript mirror rejects invalid or misbound V3 fan-in audio artifacts', () => {
  for (const mutate of [
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts[0].kind = 'video'; },
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts[0].mime = 'application/octet-stream'; },
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts[0].mime = 'audio/ '; },
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts[0].bytes_len = 0; },
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts[0].duration_ms = 0; },
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts[0].width = 1; },
    (value: ReturnType<typeof fanInV3>) => { value.audio_artifacts.reverse(); },
    (value: ReturnType<typeof fanInV3>) => {
      value.audio_artifacts[1].artifact_id = value.audio_artifacts[0].artifact_id;
    },
    (value: ReturnType<typeof fanInV3>) => {
      value.audio_artifacts[1].sha256 = value.audio_artifacts[0].sha256;
    },
    (value: ReturnType<typeof fanInV3>) => {
      value.audio_artifacts[1].uri = value.audio_artifacts[0].uri;
    },
  ]) {
    const invalid = fanInV3();
    mutate(invalid);
    invalid.audio_mix_digest = sha256Digest({ audio_artifacts: invalid.audio_artifacts });
    invalid.manifest_digest = deriveAtroposFanInManifestDigestV3(invalid);
    assert.equal(AtroposFanInManifestV3Schema.safeParse(invalid).success, false);
  }
});

test('TypeScript mirror binds audio_mix_digest to ordered audio artifacts', () => {
  const invalid = fanInV3();
  invalid.audio_mix_digest = sha256Digest({ audio_artifacts: [] });
  invalid.manifest_digest = deriveAtroposFanInManifestDigestV3(invalid);
  assert.equal(AtroposFanInManifestV3Schema.safeParse(invalid).success, false);
});

test('Python-authoritative canonical digest vectors remain byte-identical', () => {
  assert.equal(
    manifest().manifest_digest,
    'sha256:9afbef2bb2fe6ef1ecb8d168e0a5c3441c90ad73f9a69cc5f4bee74d2c3b1acd',
  );
  assert.equal(
    factoryReceipt().receipt_digest,
    'sha256:02811fe85bebbef85965088d8361527579c8d0eb6b8100c1601be3f6c142db6d',
  );
  assert.equal(
    factoryReceipt(fanInV2()).receipt_digest,
    'sha256:8aaa8f391e121cffe978c0c2026ef3b10b0ebd06fefd520da440c437447bbd6f',
  );
});
