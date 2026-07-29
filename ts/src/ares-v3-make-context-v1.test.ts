import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import test from 'node:test';

import * as PublicContracts from './index.js';
import {
  AresV3MakeContextV1Schema,
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
  'subject_id',
  'workspace_id',
  'run_id',
];

function payload(): Record<string, any> {
  const makeContext = {
    contract_version: 'AresV3MakeContext.v1' as const,
    workspace_id: '4d2b4b89-77de-4f6a-8b3c-8abdafc1e2f1',
    run_id: '7bdf3494-b232-4f15-93ea-b4a99625ba9c',
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

test('Star make context is one exact atomic authority snapshot', () => {
  const parsed = AresV3MakeContextV1Schema.parse(payload());

  assert.deepEqual(Object.keys(parsed).sort(), [...expectedKeys].sort());
  assert.equal(
    parsed.make_context_digest,
    'sha256:9c04fa8a7f7152b3ab51bf3fa45d394426a432e1bb003ef171ffb4fe7038ca07',
  );
  assert.equal(parsed.subject_id, 'lead');
});

test('Star make context is the only public make-ready contract', () => {
  for (const name of [
    'StarMakeReadyRequestV1Schema',
    'StarMakeReadyReceiptV1Schema',
    'deriveStarMakeReadyRequestDigestV1',
    'deriveStarMakeReadyCommandIdV1',
    'deriveStarMakeReadyReceiptDigestV1',
    'starMakeReadyReceiptAuthorizesV1',
  ]) {
    assert.equal(name in PublicContracts, false);
  }
  assert.equal(
    existsSync(new URL('./star-make-ready-v1.js', import.meta.url)),
    false,
  );
});

test('Star make context rejects non-UUID DB scope after rehash', () => {
  for (const field of ['workspace_id', 'run_id', 'brand_id']) {
    const value = payload();
    value[field] = 'not-a-db-uuid';
    value.make_context_digest = deriveAresV3MakeContextDigestV1(value);
    assert.equal(AresV3MakeContextV1Schema.safeParse(value).success, false);
  }
});

test('Star make context rejects authority drift', () => {
  const validUuidDrift: Record<string, string> = {
    workspace_id: '11111111-1111-4111-8111-111111111111',
    run_id: '22222222-2222-4222-8222-222222222222',
    brand_id: '33333333-3333-4333-8333-333333333333',
  };
  for (const field of [
    'workspace_id',
    'run_id',
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
        : validUuidDrift[field] ?? 'changed';
    assert.equal(AresV3MakeContextV1Schema.safeParse(value).success, false);
  }
});

test('Star make context excludes command, receipt, and provider authority', () => {
  for (const field of [
    'run_revision',
    'command_id',
    'request_digest',
    'receipt_digest',
    'provider_call',
    'dispatch',
    'make_ready_receipt',
    'scope',
    'operation_id',
    'idempotency_key',
  ]) {
    const value = payload();
    value[field] = 'client-owned';
    assert.equal(AresV3MakeContextV1Schema.safeParse(value).success, false);
  }
});

test('Star make context is immutable and helper rejects omissions', () => {
  const parsed = AresV3MakeContextV1Schema.parse(payload());
  assert.throws(() => {
    (parsed as any).subject_id = 'mutated';
  });

  const incomplete = payload();
  delete incomplete.product_lock_digest;
  assert.throws(() => deriveAresV3MakeContextDigestV1(incomplete));
});
