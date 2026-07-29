import assert from 'node:assert/strict';
import test from 'node:test';

import {
  StarMakeReadyReceiptV1Schema,
  StarMakeReadyRequestV1Schema,
  deriveStarMakeReadyCommandIdV1,
  deriveStarMakeReadyReceiptDigestV1,
  deriveStarMakeReadyRequestDigestV1,
  starMakeReadyReceiptAuthorizesV1,
} from './star-make-ready-v1.js';

const workspaceId = '3c8102c6-ec84-4530-9606-1c977b090edc';
const runId = 'af459458-e7aa-4c03-b263-702112e61c15';

function request(): Record<string, unknown> {
  const value = {
    contract_version: 'StarMakeReadyRequest.v1' as const,
    workspace_id: workspaceId,
    run_id: runId,
    run_revision: 7,
  };
  return {
    ...value,
    request_digest: deriveStarMakeReadyRequestDigestV1(value),
  };
}

function receipt(): Record<string, unknown> {
  const requestValue = request();
  const value: Record<string, unknown> = {
    contract_version: 'StarMakeReadyReceipt.v1' as const,
    workspace_id: workspaceId,
    run_id: runId,
    run_revision: 7,
    request_digest: requestValue.request_digest,
    character_lock_digest: `sha256:${'1'.repeat(64)}`,
    character_lock_version: 3,
    product_lock_digest: `sha256:${'2'.repeat(64)}`,
    artemis_approval_receipt_id: 'artemis-approval-1',
    artemis_approval_receipt_digest: `sha256:${'3'.repeat(64)}`,
    artemis_approval_state_revision: 4,
    state: 'succeeded',
    provider_call: 'none',
  };
  value.command_id = deriveStarMakeReadyCommandIdV1(value);
  return {
    ...value,
    receipt_digest: deriveStarMakeReadyReceiptDigestV1(value),
  };
}

function authority(value: Record<string, unknown>) {
  return Object.fromEntries([
    'command_id',
    'workspace_id',
    'run_id',
    'run_revision',
    'character_lock_digest',
    'character_lock_version',
    'product_lock_digest',
    'artemis_approval_receipt_id',
    'artemis_approval_receipt_digest',
    'artemis_approval_state_revision',
  ].map((field) => [field, value[field]]));
}

test('make-ready request and receipt bind current lock authority', () => {
  const parsedRequest = StarMakeReadyRequestV1Schema.parse(request());
  const parsedReceipt = StarMakeReadyReceiptV1Schema.parse(receipt());

  assert.equal(parsedReceipt.request_digest, parsedRequest.request_digest);
  assert.equal(parsedReceipt.character_lock_version, 3);
  assert.equal(parsedReceipt.artemis_approval_state_revision, 4);
  assert.equal(parsedReceipt.provider_call, 'none');
  assert.equal(
    parsedRequest.request_digest,
    'sha256:a1920ab5b142cbf0f2ecc88dc08f301035bd299c486a5bdaf005dc3c03b765b9',
  );
  assert.equal(
    parsedReceipt.command_id,
    'sha256:c31ef5061b88f66e3692a6e97a8b6f7b878bb40fe9eefbbcf6c25644edbf6da6',
  );
  assert.equal(
    parsedReceipt.receipt_digest,
    'sha256:ca36a7df54b138225b205542af832a52b74f209adc7693e99054c9e23ff497be',
  );
  assert.equal(
    starMakeReadyReceiptAuthorizesV1(parsedReceipt, {
      isCurrentMakeReady: (candidate) => (
        JSON.stringify(candidate) === JSON.stringify(authority(receipt()))
      ),
    }),
    true,
  );
});

test('make-ready receipt rejects scope or authority drift', () => {
  for (const field of [
    'workspace_id',
    'run_id',
    'run_revision',
    'character_lock_digest',
    'character_lock_version',
    'product_lock_digest',
    'artemis_approval_receipt_digest',
    'artemis_approval_state_revision',
  ]) {
    const value = receipt();
    value[field] = typeof value[field] === 'number'
      ? (value[field] as number) + 1
      : field.endsWith('digest')
        ? `sha256:${'9'.repeat(64)}`
        : 'changed';
    assert.equal(StarMakeReadyReceiptV1Schema.safeParse(value).success, false);
  }
});

test('make-ready rejects provider and client authority fields', () => {
  const value = receipt();
  value.provider_call = 'seedream';
  value.parzifal_receipt = { face_id: 'client-face' };
  value.dispatch = { provider: 'seedream' };

  assert.equal(StarMakeReadyReceiptV1Schema.safeParse(value).success, false);
});

test('make-ready safeParse rejects malformed values without throwing', () => {
  const unsafeRevision = receipt();
  unsafeRevision.run_revision = Number.MAX_SAFE_INTEGER + 1;
  assert.doesNotThrow(() => StarMakeReadyReceiptV1Schema.safeParse(unsafeRevision));
  assert.equal(
    StarMakeReadyReceiptV1Schema.safeParse(unsafeRevision).success,
    false,
  );

  const invalidReceiptId = receipt();
  invalidReceiptId.artemis_approval_receipt_id = '\ud800';
  assert.doesNotThrow(() => StarMakeReadyReceiptV1Schema.safeParse(invalidReceiptId));
  assert.equal(
    StarMakeReadyReceiptV1Schema.safeParse(invalidReceiptId).success,
    false,
  );
});

test('make-ready digest helpers reject incomplete payloads', () => {
  const value = receipt();
  delete value.receipt_digest;
  delete value.product_lock_digest;

  assert.throws(() => deriveStarMakeReadyCommandIdV1(value));
  assert.throws(() => deriveStarMakeReadyReceiptDigestV1(value));
});

test('fully rehashed fabrication is not current authority', () => {
  const canonical = receipt();
  const fabricated = receipt();
  fabricated.character_lock_digest = `sha256:${'8'.repeat(64)}`;
  fabricated.command_id = deriveStarMakeReadyCommandIdV1(fabricated);
  fabricated.receipt_digest = deriveStarMakeReadyReceiptDigestV1(fabricated);

  const structurallyValid = StarMakeReadyReceiptV1Schema.parse(fabricated);

  assert.equal(
    starMakeReadyReceiptAuthorizesV1(structurallyValid, {
      isCurrentMakeReady: (candidate) => (
        JSON.stringify(candidate) === JSON.stringify(authority(canonical))
      ),
    }),
    false,
  );
});

test('make-ready resolver requires literal synchronous true', () => {
  const parsed = StarMakeReadyReceiptV1Schema.parse(receipt());

  assert.equal(
    starMakeReadyReceiptAuthorizesV1(parsed, {
      isCurrentMakeReady: (() => ({ accepted: true })) as any,
    }),
    false,
  );
  assert.equal(
    starMakeReadyReceiptAuthorizesV1(parsed, {
      isCurrentMakeReady: (() => Promise.resolve(true)) as any,
    }),
    false,
  );
});
