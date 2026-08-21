import assert from 'node:assert/strict';
import test from 'node:test';

import { AudioClipSchema, validateAudioClip } from './audio-clip.js';
import { BeatPlanSchema, validateBeatPlan } from './beat-plan.js';
import { CanonicalBrandSlugSchema, canonicalBrandSlug, isContractBlank } from './brand-scope.js';
import {
  characterIdentityBindingErrorV1,
  characterIdentityBindingPayloadV1,
  deriveCharacterIdentityBindingDigestV1,
} from './character-identity-v1.js';
import { CharacterLockV1Schema, deriveCharacterLockDigestV1 } from './character-lock-v1.js';
import {
  CompositionSnapshotSchema,
  validateCompositionSnapshot,
} from './composition-snapshot.js';
import { assertRenderReady } from './gate.js';
import { answeredCount } from './janus-brief.js';
import { MediaArtifactSchema, validateMediaArtifact } from './media-artifact.js';
import {
  calculateCtr,
  calculateRoas,
  ReelMetricSchema,
  validateReelMetric,
} from './reel-metric.js';
import { assertStrictCanonicalValue, strictUtcMicros } from './strict-contract-value.js';
import {
  approvalAuthorizes,
  ApprovalReceiptSchema,
  DegradationReceiptSchema,
} from './factory/approval.js';
import {
  assertDigest,
  canonicalJson,
  DigestError,
  isDigest,
  sha256Digest,
} from './factory/digest.js';
import {
  isStageSuccess,
  isStageTerminal,
  StageReceiptSchema,
} from './factory/stage-receipt.js';
import { assertTransition, FactoryState } from './factory/state.js';

const DIGEST = `sha256:${'a'.repeat(64)}`;
const UUID = '00000000-0000-4000-8000-000000000001';

test('small media and beat helpers cover every explicit result', () => {
  const voice = AudioClipSchema.parse({
    track: 'voice', beat_index: 0, storage_key: 'voice.wav',
  });
  const music = AudioClipSchema.parse({ track: 'music', url: 'https://cdn.example/music.mp3' });
  assert.deepEqual(validateAudioClip(voice), []);
  assert.deepEqual(validateAudioClip({ track: 'sfx' } as never), [
    'sfx 클립에 beat_index 없음 (P1 침묵 위험)',
    'url/storage_key 둘 다 없음 (재생 불가)',
  ]);
  assert.equal(AudioClipSchema.safeParse({ track: 'voice', storage_key: 'voice.wav' }).success, false);
  assert.equal(AudioClipSchema.safeParse({ track: 'music' }).success, false);

  const still = MediaArtifactSchema.parse({ kind: 'still', beat_index: 0, storage_key: 'still.png' });
  assert.deepEqual(validateMediaArtifact(still), []);
  assert.deepEqual(validateMediaArtifact({ kind: 'still', beat_index: 0 } as never), [
    'url/storage_key 없음',
  ]);
  assert.equal(MediaArtifactSchema.safeParse({ kind: 'still', beat_index: 0 }).success, false);

  assert.deepEqual(validateBeatPlan(BeatPlanSchema.parse({})), []);
  assert.deepEqual(validateBeatPlan({ beats: [{ beat_index: 0 }, { beat_index: 0 }] } as never), [
    'beat_index 중복',
    'beat_index 연속성 깨짐(구멍)',
  ]);
  assert.deepEqual(validateBeatPlan({ beats: [{ beat_index: 0 }, { beat_index: 2 }] } as never), [
    'beat_index 연속성 깨짐(구멍)',
  ]);
  assert.deepEqual(validateBeatPlan({ beats: [{ beat_index: 2 }, { beat_index: 1 }] } as never), []);

  const ready = assertRenderReady(
    { beats: [{ beat_index: 0, text: '', caption: 'caption' }] },
    [voice, music],
    [still],
  );
  assert.equal(ready.ok, true);
  assert.deepEqual(ready.warnings, []);
  const broken = assertRenderReady(
    { beats: [{ beat_index: 0, text: '', caption: null }] },
    [{ track: 'voice', beat_index: null, storage_key: 'voice.wav' } as never],
    [{ kind: 'still', beat_index: null, storage_key: 'still.png' } as never],
  );
  assert.equal(broken.ok, false);
  assert.ok(broken.warnings.length > 0);
  assert.equal(assertRenderReady({ beats: [] }, [], []).ok, false);
});

test('brand and identity helpers reject every malformed text boundary', () => {
  assert.equal(isContractBlank(''), true);
  assert.equal(isContractBlank('\u3000'), true);
  assert.equal(isContractBlank('brand'), false);
  for (const value of [' brand', 'brand ', '\ud800', '\udc00', 'brand\u0000']) {
    assert.equal(CanonicalBrandSlugSchema.safeParse(value).success, false);
  }
  assert.equal(CanonicalBrandSlugSchema.safeParse('').success, false);
  assert.equal(canonicalBrandSlug('브랜드😀'), '브랜드😀');

  assert.throws(
    () => characterIdentityBindingPayloadV1({ subject_id: ' ', face_id: 'face', voice_id: 'voice' }),
    /subject_id is required/,
  );
  const identity = { subject_id: 'subject', face_id: 'face', voice_id: 'voice' };
  const bindingDigest = deriveCharacterIdentityBindingDigestV1(identity);
  assert.equal(characterIdentityBindingErrorV1({ subject_id: 'subject' }), null);
  assert.match(
    characterIdentityBindingErrorV1({ subject_id: 'subject', face_id: 'face' }) ?? '',
    /sealed together/,
  );
  assert.match(
    characterIdentityBindingErrorV1({ ...identity }) ?? '',
    /identity_binding_digest is required/,
  );
  assert.equal(characterIdentityBindingErrorV1({ ...identity, identity_binding_digest: bindingDigest }), null);
  assert.match(
    characterIdentityBindingErrorV1({ ...identity, identity_binding_digest: DIGEST }) ?? '',
    /does not match/,
  );

  const lockSource = {
    contract_version: 'CharacterLock.v1',
    workspace_id: UUID,
    brand_slug: 'brand',
    subject_id: 'subject',
    version: 1,
    face_id: 'face',
    voice_id: 'voice',
    source_receipt_ref: 'receipt',
    source_record_version: 1,
    source_receipt_digest: DIGEST,
  };
  const lockDigest = deriveCharacterLockDigestV1(lockSource);
  assert.equal(CharacterLockV1Schema.safeParse({ ...lockSource, digest: lockDigest }).success, true);
  assert.equal(CharacterLockV1Schema.safeParse({ ...lockSource, digest: DIGEST }).success, false);
  assert.equal(CharacterLockV1Schema.safeParse({ ...lockSource, subject_id: '\udc00', digest: DIGEST }).success, false);
});

test('snapshot, intake, and metric helpers cover valid and invalid results', () => {
  assert.equal(CompositionSnapshotSchema.safeParse({ run_id: 'run' }).success, true);
  assert.equal(
    CompositionSnapshotSchema.safeParse({ run_id: 'run', render_status: 'rendering', gate_passed: false }).success,
    false,
  );
  assert.equal(
    CompositionSnapshotSchema.safeParse({ run_id: 'run', render_status: 'completed', gate_passed: true }).success,
    false,
  );
  const completed = CompositionSnapshotSchema.parse({
    run_id: 'run', render_status: 'completed', gate_passed: true, output_url: 'https://cdn.example/video.mp4',
  });
  assert.deepEqual(validateCompositionSnapshot(completed), []);
  assert.deepEqual(
    validateCompositionSnapshot({ run_id: '', render_status: 'completed', gate_passed: false } as never),
    [
      'run_id 없음',
      'gate_passed=False인데 렌더 진행 (invariant 미증명)',
      'completed인데 output_url 없음 (WS06 배송 다리 끊김)',
    ],
  );

  assert.equal(answeredCount({ identity: ' yes ', usp: '', proof: null }), 1);
  const metric = ReelMetricSchema.parse({ brand_slug: 'brand', run_id: 'run', spend_krw: 100, revenue_krw: 250, impressions: 200, clicks: 5 });
  assert.equal(calculateRoas(metric), 2.5);
  assert.equal(calculateCtr(metric), 0.025);
  assert.equal(calculateRoas({ ...metric, spend_krw: 0 }), undefined);
  assert.equal(calculateCtr({ ...metric, impressions: 0 }), undefined);
  assert.deepEqual(validateReelMetric(metric), []);
  assert.deepEqual(validateReelMetric({ ...metric, brand_slug: '', run_id: '' }), [
    'brand_slug 없음', 'run_id 없음',
  ]);
});

test('strict canonical and digest helpers execute all JSON types', () => {
  for (const value of [null, true, 'text😀', 1, [1, 'two'], { nested: [false] }]) {
    assert.doesNotThrow(() => assertStrictCanonicalValue(value));
  }
  for (const value of ['\ud800', '\udc00', Number.MAX_SAFE_INTEGER + 1, () => undefined]) {
    assert.throws(() => assertStrictCanonicalValue(value));
  }
  assert.throws(() => strictUtcMicros('invalid'), /strict UTC/);
  assert.throws(() => strictUtcMicros('2026-02-30T00:00:00Z'), /real UTC/);
  assert.equal(strictUtcMicros('2026-01-02T03:04:05.123456Z'), 1767323045123456);
  assert.equal(canonicalJson({ b: 1, a: [2] }), '{"a":[2],"b":1}');
  assert.throws(() => canonicalJson({ value: Number.POSITIVE_INFINITY }), DigestError);
  assert.equal(isDigest(DIGEST), true);
  assert.equal(isDigest(null), false);
  assert.equal(assertDigest(DIGEST), DIGEST);
  assert.throws(() => assertDigest('bad', 'field'), DigestError);
});

test('approval, degradation, stage, and transition helpers cover terminal paths', () => {
  const approval = ApprovalReceiptSchema.parse({
    approval_id: 'approval', kind: 'script', run_id: 'run', factory_revision: 1,
    target_id: 'target', target_digest: DIGEST, decision: 'approved', approved_by: 'founder',
    approved_at: '2026-01-01T00:00:00Z', policy_version: 'v1',
  });
  assert.equal(approvalAuthorizes(approval, DIGEST), true);
  assert.equal(approvalAuthorizes({ ...approval, decision: 'rejected' }, DIGEST), false);
  assert.equal(approvalAuthorizes({ ...approval, expires_at: '2026-01-02T00:00:00Z' }, DIGEST), true);
  assert.equal(approvalAuthorizes({ ...approval, expires_at: '2026-01-02T00:00:00Z' }, DIGEST, '2026-01-01T00:00:00Z'), true);
  assert.equal(approvalAuthorizes({ ...approval, expires_at: '2026-01-02T00:00:00Z' }, DIGEST, '2026-01-03T00:00:00Z'), false);

  const degradation = {
    degradation_id: 'degradation', run_id: 'run', factory_revision: 1,
    omitted_stage: 'stage', omitted_artifact_kind: 'artifact', plan_digest: DIGEST,
    user_impact: 'visible impact', authorized_by: 'founder', recovery_action: 'restore',
    created_at: '2026-01-01T00:00:00Z',
  };
  assert.equal(DegradationReceiptSchema.safeParse(degradation).success, true);
  for (const field of ['user_impact', 'authorized_by', 'recovery_action'] as const) {
    assert.equal(DegradationReceiptSchema.safeParse({ ...degradation, [field]: ' ' }).success, false);
  }

  const stage = {
    operation_id: 'operation', stage_id: 'stage', planet: 'ares', node_id: 'node',
    producer_revision: 'revision', contract_version: 'v1', status: 'succeeded', attempt_no: 1,
    started_at: '2026-01-01T00:00:00Z', completed_at: '2026-01-01T00:00:01Z',
    output_digests: [DIGEST],
  };
  const succeeded = StageReceiptSchema.parse(stage);
  assert.equal(isStageTerminal(succeeded), true);
  assert.equal(isStageSuccess(succeeded), true);
  assert.equal(StageReceiptSchema.safeParse({ ...stage, completed_at: null }).success, false);
  assert.equal(StageReceiptSchema.safeParse({ ...stage, output_digests: [] }).success, false);
  assert.equal(StageReceiptSchema.safeParse({ ...stage, error: { code: 'x', retryable: false } }).success, false);
  assert.equal(StageReceiptSchema.safeParse({ ...stage, status: 'running' }).success, false);
  assert.equal(StageReceiptSchema.safeParse({ ...stage, status: 'failed', error: null }).success, false);
  const failed = StageReceiptSchema.parse({
    ...stage, status: 'failed', output_digests: [], error: { code: 'failed', retryable: false },
  });
  assert.equal(isStageTerminal(failed), true);
  assert.equal(isStageSuccess(failed), false);

  assert.doesNotThrow(() => assertTransition(FactoryState.CREATED, FactoryState.PLANNING));
  assert.throws(() => assertTransition(FactoryState.CREATED, FactoryState.RENDERING));
  assert.notEqual(sha256Digest({ one: 1 }), sha256Digest({ two: 2 }));
});
