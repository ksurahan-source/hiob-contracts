/**
 * Factory kernel TS tests — cross-language parity vs Python + invariant checks.
 *
 * Parity fixtures are the exact values Python `hiob_contracts.factory` produced
 * (computed 2026-07-14). If TS drifts from Python, these fail — that is the whole
 * point of a hash-linked edge chain crossing the Studio(JS)↔Planet(Python) seam.
 */
import { canonicalJson, sha256Digest, isDigest } from './digest.js';
import { buildPlanetOutput, verifyPlanetOutput, PlanetOutputSchema } from './planet-output.js';
import { deriveIdempotencyKey, KarmaEdgeReceiptSchema, receiptAuthorizes } from './karma-edge.js';
import { StageReceiptSchema, isStageSuccess } from './stage-receipt.js';
import { ApprovalReceiptSchema, approvalAuthorizes, DegradationReceiptSchema } from './approval.js';
import { FactoryState, canTransition } from './state.js';
import { isRegisteredEdge, getEdge, requiredEdges } from './edge-registry.js';

function test(name: string, fn: () => void) {
  try {
    fn();
    console.log(`✓ ${name}`);
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  }
}
function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

// ── Python-computed reference values (single source of truth) ──────────────────
const SCHEMA = 'sha256:4091ea94c4a9c64d1534caa9839530144023483fe6a25a8597be1bbf6c281b93';
const POLICY = 'sha256:d289baef8930ccf2337a7120b9a492e1fa869c36ed6a802c4bedc6e2003afbd0';

// ── digest parity ──────────────────────────────────────────────────────────
test('canonicalJson sorts keys recursively (parity)', () => {
  assert(canonicalJson({ a: 1, b: { y: 2, x: 1 } }) === '{"a":1,"b":{"x":1,"y":2}}', 'canonicalJson mismatch');
});
test('sha256Digest ASCII parity with Python', () => {
  assert(
    sha256Digest({ a: 1, b: { y: 2, x: 1 } }) ===
      'sha256:ca7a7c6cde8062a260c631854aab1e42e3510b86667e76b77ee42941495bdf07',
    'ascii digest mismatch'
  );
});
test('sha256Digest non-ASCII parity with Python (하이옵)', () => {
  assert(canonicalJson({ brand: '하이옵', n: 3 }) === '{"brand":"하이옵","n":3}', 'non-ascii canonicalJson mismatch');
  assert(
    sha256Digest({ brand: '하이옵', n: 3 }) ===
      'sha256:651285946cb8267e32e256f7e6f8151eac0f35732f0312ece1031fa4bb46d5c1',
    'non-ascii digest mismatch'
  );
});
test('sha256Digest array parity with Python', () => {
  assert(
    sha256Digest([1, 2, 3]) === 'sha256:a615eeaee21de5179de080de8c3052c8da901138406ba71c38c032845f7d54f4',
    'array digest mismatch'
  );
});

// ── idempotency key parity ──────────────────────────────────────────────────
test('deriveIdempotencyKey parity with Python (order-sensitive)', () => {
  const src1 = sha256Digest({ a: 1 });
  const src2 = sha256Digest({ a: 2 });
  assert(src1 === 'sha256:015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862', 'src1 mismatch');
  assert(src2 === 'sha256:7e8059f495589fcd981232cc11d00b00da3802c01d688fa1cf1f6bed6e5bb33c', 'src2 mismatch');
  const key = deriveIdempotencyKey({
    run_id: 'run-1', factory_revision: 0, edge_id: 'j2p',
    source_output_digests: [src1, src2], target_schema_digest: SCHEMA, policy_digest: POLICY,
  });
  assert(key === 'sha256:8d71c589494eecd5e91dd8ac924e81634f7f2478e6b1b999055fbfa2a18c3534', 'idempotency key mismatch');
  const swapped = deriveIdempotencyKey({
    run_id: 'run-1', factory_revision: 0, edge_id: 'j2p',
    source_output_digests: [src2, src1], target_schema_digest: SCHEMA, policy_digest: POLICY,
  });
  assert(key !== swapped, 'fan-in order must change the key');
});

// ── PlanetOutput envelope parity ────────────────────────────────────────────
test('buildPlanetOutput digests parity with Python + verify', () => {
  const out = buildPlanetOutput({
    output_id: 'out-janus', run_id: 'run-1', factory_revision: 0, workspace_id: 'ws-1',
    trace_id: 'trace-1', execution_id: 'exec-1', attempt_no: 1,
    producer: { planet: 'janus', node_id: 'janus.node', revision: 'r1' },
    contract: { name: 'JanusBrief', version: 'v1', schema_digest: SCHEMA },
    payload: { brief: 'hello', n: 3 }, emitted_at: '2026-07-14T00:00:00Z',
  });
  assert(out.payload_digest === 'sha256:6d7b66e3e7ade28c02dd22f88193e9274e2f6a5488562fef7ef6ae776712b258', 'payload_digest parity mismatch');
  assert(out.output_digest === 'sha256:b1083d35620c3f5f582aecc2b9ce170fa0849ef34d5b62a1ce0f313e2c92924e', 'output_digest parity mismatch');
  assert(verifyPlanetOutput(out), 'verifyPlanetOutput should be true');
});
test('PlanetOutput tampered payload rejected', () => {
  const out = buildPlanetOutput({
    output_id: 'o', run_id: 'r', factory_revision: 0, workspace_id: 'w', trace_id: 't',
    execution_id: 'e', attempt_no: 1, producer: { planet: 'janus', node_id: 'n', revision: 'r' },
    contract: { name: 'X', version: 'v1', schema_digest: SCHEMA }, payload: { a: 1 },
    emitted_at: 't',
  });
  const bad = PlanetOutputSchema.safeParse({ ...out, payload: { a: 999 } });
  assert(!bad.success, 'tampered payload must fail');
});

// ── KarmaEdgeReceipt invariants ─────────────────────────────────────────────
function acceptedReceipt(targetInput: Record<string, unknown>) {
  return {
    receipt_id: 'r', edge_id: 'j2p', run_id: 'r', factory_revision: 0,
    source_output_digests: [sha256Digest({ a: 1 })],
    target_contract: { name: 'ParzifalTargetInput', version: 'v1', schema_digest: SCHEMA },
    decision: 'accepted' as const, target_input: targetInput,
    target_input_digest: sha256Digest(targetInput),
    mapper: { node_id: 'karma.edge.refine', revision: 'r1', policy_digest: POLICY },
    created_at: 't',
  };
}
test('accepted receipt authorizes matching digest only', () => {
  const ti = { target: 'value' };
  const r = KarmaEdgeReceiptSchema.parse(acceptedReceipt(ti));
  assert(receiptAuthorizes(r, sha256Digest(ti)), 'should authorize matching');
  assert(!receiptAuthorizes(r, sha256Digest({ other: 1 })), 'should reject mismatched');
});
test('accepted receipt without target_input rejected', () => {
  const bad = KarmaEdgeReceiptSchema.safeParse({
    receipt_id: 'r', edge_id: 'j2p', run_id: 'r', factory_revision: 0,
    source_output_digests: [sha256Digest({ a: 1 })],
    target_contract: { name: 'X', version: 'v1', schema_digest: SCHEMA }, decision: 'accepted',
    mapper: { node_id: 'k', revision: 'r', policy_digest: POLICY }, created_at: 't',
  });
  assert(!bad.success, 'accepted without target_input must fail');
});
test('accepted receipt with error-violation rejected', () => {
  const bad = KarmaEdgeReceiptSchema.safeParse({
    ...acceptedReceipt({ x: 1 }),
    violations: [{ code: 'E1', path: '/x', severity: 'error' }],
  });
  assert(!bad.success, 'accepted with error violation must fail');
});
for (const decision of ['blocked', 'needs_human'] as const) {
  test(`${decision} receipt must not carry target_input`, () => {
    const bad = KarmaEdgeReceiptSchema.safeParse({
      receipt_id: 'r', edge_id: 'j2p', run_id: 'r', factory_revision: 0,
      source_output_digests: [sha256Digest({ a: 1 })],
      target_contract: { name: 'X', version: 'v1', schema_digest: SCHEMA }, decision,
      target_input: { x: 1 }, target_input_digest: sha256Digest({ x: 1 }),
      mapper: { node_id: 'k', revision: 'r', policy_digest: POLICY }, created_at: 't',
    });
    assert(!bad.success, `${decision} with target_input must fail`);
  });
}

// ── StageReceipt invariants ─────────────────────────────────────────────────
test('succeeded stage requires output + completed', () => {
  const ok = StageReceiptSchema.parse({
    operation_id: 'op', stage_id: 's', planet: 'athena', node_id: 'n', producer_revision: 'r',
    contract_version: 'v1', output_digests: [sha256Digest({ a: 1 })], status: 'succeeded',
    attempt_no: 1, started_at: 't0', completed_at: 't1',
  });
  assert(isStageSuccess(ok), 'should be success');
  const bad = StageReceiptSchema.safeParse({
    operation_id: 'op', stage_id: 's', planet: 'a', node_id: 'n', producer_revision: 'r',
    contract_version: 'v1', status: 'succeeded', attempt_no: 1, started_at: 't0', completed_at: 't1',
  });
  assert(!bad.success, 'succeeded without output must fail');
});
test('accepted/running stage forbids completed_at (spawn ≠ success)', () => {
  const bad = StageReceiptSchema.safeParse({
    operation_id: 'op', stage_id: 's', planet: 'a', node_id: 'n', producer_revision: 'r',
    contract_version: 'v1', status: 'running', attempt_no: 1, started_at: 't0', completed_at: 't1',
  });
  assert(!bad.success, 'running with completed_at must fail');
});

// ── ApprovalReceipt ─────────────────────────────────────────────────────────
test('approval authorizes exact digest, rejects revoked/expired/rejected', () => {
  const d = sha256Digest({ snapshot: 'final' });
  const a = ApprovalReceiptSchema.parse({
    approval_id: 'ap', kind: 'composition_snapshot', run_id: 'r', factory_revision: 1,
    target_id: 't', target_digest: d, decision: 'approved', approved_by: 'u', approved_at: 't',
    policy_version: 'v1',
  });
  assert(approvalAuthorizes(a, d), 'should authorize');
  assert(!approvalAuthorizes(a, sha256Digest({ snapshot: 'other' })), 'should reject mismatch');
  const revoked = ApprovalReceiptSchema.parse({ ...a, revoked_at: 't2' });
  assert(!approvalAuthorizes(revoked, d), 'revoked must not authorize');
  const expired = ApprovalReceiptSchema.parse({ ...a, expires_at: '2026-01-01T00:00:00Z' });
  assert(!approvalAuthorizes(expired, d, '2026-07-14T00:00:00Z'), 'expired must not authorize');
});

// ── DegradationReceipt ──────────────────────────────────────────────────────
test('degradation requires impact + recovery + approver', () => {
  const bad = DegradationReceiptSchema.safeParse({
    degradation_id: 'dg', run_id: 'r', factory_revision: 0, omitted_stage: 'x',
    omitted_artifact_kind: 'sfx', plan_digest: sha256Digest({ p: 1 }), user_impact: '   ',
    authorized_by: 'p', recovery_action: 'y', created_at: 't',
  });
  assert(!bad.success, 'blank impact must fail');
});

// ── FactoryState ────────────────────────────────────────────────────────────
test('state transitions match Python', () => {
  assert(canTransition(FactoryState.CREATED, FactoryState.PLANNING), 'linear allowed');
  assert(!canTransition(FactoryState.CREATED, FactoryState.MEDIA_PLANNING), 'skip disallowed');
  assert(!canTransition(FactoryState.SUCCEEDED, FactoryState.PLANNING), 'terminal no reopen');
  assert(canTransition(FactoryState.MATERIALIZING, FactoryState.BLOCKED), 'exception allowed');
  assert(canTransition(FactoryState.BLOCKED, FactoryState.MATERIALIZING), 'resume allowed');
  assert(canTransition(FactoryState.WAITING_SCRIPT_APPROVAL, FactoryState.PLANNING), 'reject loop');
});

// ── edge registry ───────────────────────────────────────────────────────────
test('edge registry matches Python', () => {
  assert(isRegisteredEdge('janus', 'parzifal'), 'j2p registered');
  assert(isRegisteredEdge('athena', 'atropos'), 'fan-in athena');
  assert(isRegisteredEdge('apollo', 'atropos'), 'fan-in apollo');
  assert(!isRegisteredEdge('janus', 'hephaestus'), 'unregistered rejected');
  assert(getEdge('a2apollo')!.criticality === 'optional', 'apollo optional');
  assert(requiredEdges().some((e) => e.edge_id === 'j2p'), 'j2p required');
  assert(!requiredEdges().some((e) => e.edge_id === 'a2apollo'), 'apollo not required');
});

console.log('\nAll factory kernel tests passed!');
