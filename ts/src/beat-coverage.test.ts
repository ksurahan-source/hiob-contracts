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
    assert.equal(BeatCoverageV1Schema.safeParse(value).success, true);
    assert.equal(SerialFanInReceiptV1Schema.safeParse(value).success, true);
  }
});

test('coverage digest is deterministic and bound to payload', () => {
  const first = coverage();
  const second = coverage();
  assert.equal(first.coverage_digest, second.coverage_digest);
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
