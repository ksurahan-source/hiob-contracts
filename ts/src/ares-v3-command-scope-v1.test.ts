import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AresV3CommandScopeV1Schema,
  deriveAresV3MakeContextDigestV1,
} from './ares-create-script-v3.js';

const expectedKeys = [
  'artemis_approval_receipt_digest',
  'artemis_approval_receipt_id',
  'artemis_approval_state_revision',
  'brand_id',
  'character_lock_digest',
  'character_lock_version',
  'contract_version',
  'make_context_digest',
  'product_id',
  'product_lock_digest',
  'scope',
  'subject_id',
];

function payload(): Record<string, any> {
  const makeContext = {
    contract_version: 'AresV3CommandScope.v1' as const,
    scope: {
      workspace_id: 'ws-v3-1',
      run_id: 'run-v3-1',
      operation_id: 'op-script-v3-1',
      idempotency_key:
        'ares-script-v3:ws-v3-1:run-v3-1:op-script-v3-1',
    },
    brand_id: '2a86daca-f5f2-4a3d-a868-f283a0a57d84',
    subject_id: 'lead',
    product_id: 'c4404dda-a191-4bd3-942d-21a45f202554',
    character_lock_digest: `sha256:${'1'.repeat(64)}`,
    character_lock_version: 3,
    product_lock_digest: `sha256:${'4'.repeat(64)}`,
    artemis_approval_receipt_id: 'artemis-approval-1',
    artemis_approval_receipt_digest: `sha256:${'5'.repeat(64)}`,
    artemis_approval_state_revision: 4,
  };
  return {
    ...makeContext,
    make_context_digest: deriveAresV3MakeContextDigestV1(makeContext),
  };
}

test('Star command scope is one exact atomic make context', () => {
  const parsed = AresV3CommandScopeV1Schema.parse(payload());

  assert.deepEqual(Object.keys(parsed).sort(), expectedKeys);
  assert.equal(
    parsed.make_context_digest,
    'sha256:e99651e95596a97ce408a82e53bbe041a8e7e981bf8503d43ab4a090abd87b3e',
  );
  assert.equal(parsed.subject_id, 'lead');
});

test('Star command scope rejects make-context and scope drift', () => {
  for (const field of [
    'brand_id',
    'subject_id',
    'product_id',
    'character_lock_digest',
    'character_lock_version',
    'product_lock_digest',
    'artemis_approval_receipt_id',
    'artemis_approval_receipt_digest',
    'artemis_approval_state_revision',
  ]) {
    const value = payload();
    value[field] = typeof value[field] === 'number'
      ? value[field] + 1
      : field.endsWith('digest')
        ? `sha256:${'9'.repeat(64)}`
        : 'changed';
    assert.equal(AresV3CommandScopeV1Schema.safeParse(value).success, false);
  }

  const scopeDrift = payload();
  scopeDrift.scope.workspace_id = 'other-workspace';
  assert.equal(
    AresV3CommandScopeV1Schema.safeParse(scopeDrift).success,
    false,
  );
});

test('make-context digest excludes command execution identity', () => {
  const value = payload();
  value.scope.operation_id = 'other-operation';
  value.scope.idempotency_key = 'other-idempotency-key';

  const parsed = AresV3CommandScopeV1Schema.parse(value);

  assert.equal(parsed.make_context_digest, payload().make_context_digest);
});

test('Star command scope excludes legacy receipt and provider authority', () => {
  for (const field of [
    'run_revision',
    'command_id',
    'request_digest',
    'receipt_digest',
    'provider_call',
    'dispatch',
    'make_ready_receipt',
  ]) {
    const value = payload();
    value[field] = 'client-owned';
    assert.equal(AresV3CommandScopeV1Schema.safeParse(value).success, false);
  }
});

test('Star command scope is deeply immutable and helper rejects omissions', () => {
  const parsed = AresV3CommandScopeV1Schema.parse(payload());
  assert.throws(() => {
    (parsed.scope as any).operation_id = 'mutated';
  });

  const incomplete = payload();
  delete incomplete.product_lock_digest;
  assert.throws(() => deriveAresV3MakeContextDigestV1(incomplete));
});
