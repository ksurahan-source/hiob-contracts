import assert from 'node:assert/strict';
import test from 'node:test';

import {
  BeatCoverageV1Schema,
  DEFAULT_BEAT_COVERAGE_LANES_V1,
  SerialFanInReceiptV1Schema,
  createBeatCoverageV1,
  createBeatLaneTerminalReceiptV1,
} from './beat-coverage.js';
import { sha256Digest } from './factory/digest.js';

const RUN_ID = 'run-coverage-1';
const WORKSPACE_ID = 'workspace-1';
const PACKAGE_DIGEST = sha256Digest({ package: 'p1' });
const PLAN_DIGEST = sha256Digest({ plan: 'p1' });

function lanes(n = 6) {
  return Array.from({ length: n }, (_, beatIndex) => DEFAULT_BEAT_COVERAGE_LANES_V1.map((lane) => (
    createBeatLaneTerminalReceiptV1({
      run_id: RUN_ID,
      workspace_id: WORKSPACE_ID,
      package_digest: PACKAGE_DIGEST,
      plan_digest: PLAN_DIGEST,
      beat_index: beatIndex,
      lane,
      output_digest: sha256Digest({ beat_index: beatIndex, lane }),
    })
  ))).flat();
}

function coverage(n = 6) {
  return createBeatCoverageV1({
    run_id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    package_digest: PACKAGE_DIGEST,
    plan_digest: PLAN_DIGEST,
    expected_n_beats: n,
    expected_beat_indices: Array.from({ length: n }, (_, index) => index),
    lane_receipts: lanes(n),
  });
}

test('six and twelve beat coverage parses and round-trips as serial fan-in', () => {
  for (const n of [6, 12]) {
    const value = coverage(n);
    const parsed = BeatCoverageV1Schema.safeParse(value);
    assert.equal(parsed.success, true);
    assert.equal(SerialFanInReceiptV1Schema.safeParse(value).success, true);
  }
});

test('coverage digest is deterministic and bound to payload', () => {
  const first = coverage();
  const second = coverage();
  assert.equal(first.coverage_digest, second.coverage_digest);
  // Python/TypeScript parity vector; lane completion order is canonicalized.
  assert.equal(first.coverage_digest, 'sha256:7252864e3f9091ff6d3bb3d2a381cfc11ae67f4f88cef2c4f6e90c0067ebd536');
  assert.equal(BeatCoverageV1Schema.safeParse({ ...first, workspace_id: 'other' }).success, false);
});

test('exact indices, duplicate, missing, foreign, failed, and out-of-range lanes reject', () => {
  const value = coverage();
  assert.equal(BeatCoverageV1Schema.safeParse({
    ...value,
    expected_beat_indices: [0, 1, 3, 4, 5, 6],
  }).success, false);
  assert.equal(BeatCoverageV1Schema.safeParse({
    ...value,
    lane_receipts: [...value.lane_receipts, value.lane_receipts[0]],
  }).success, false);
  assert.equal(BeatCoverageV1Schema.safeParse({
    ...value,
    lane_receipts: value.lane_receipts.slice(0, -1),
  }).success, false);
  assert.equal(BeatCoverageV1Schema.safeParse({
    ...value,
    lane_receipts: [{ ...value.lane_receipts[0], run_id: 'other-run' }, ...value.lane_receipts.slice(1)],
  }).success, false);
  assert.equal(BeatCoverageV1Schema.safeParse({
    ...value,
    lane_receipts: [{ ...value.lane_receipts[0], status: 'failed' }, ...value.lane_receipts.slice(1)],
  }).success, false);
  assert.equal(BeatCoverageV1Schema.safeParse({
    ...value,
    lane_receipts: [{ ...value.lane_receipts[0], beat_index: 6 }, ...value.lane_receipts.slice(1)],
  }).success, false);
});

test('strict boundaries reject malformed, unknown, and coercible coverage values without crashing', () => {
  const value = coverage();
  for (const candidate of [
    null,
    [],
    coverage(17),
    { ...value, expected_n_beats: '6' },
    { ...value, unexpected: 'key' },
    { ...value, lane_receipts: 'not-an-array' },
  ]) {
    assert.doesNotThrow(() => BeatCoverageV1Schema.safeParse(candidate));
    assert.equal(BeatCoverageV1Schema.safeParse(candidate).success, false);
  }
});

test('constructors return valid coverage or fail closed', () => {
  assert.throws(() => createBeatLaneTerminalReceiptV1({
    run_id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    package_digest: PACKAGE_DIGEST,
    plan_digest: PLAN_DIGEST,
    beat_index: 0,
    lane: 'athena',
    status: 'failed',
  }));
  assert.throws(() => createBeatCoverageV1({
    ...coverage(17),
    unexpected: 'key',
  } as never));
});
