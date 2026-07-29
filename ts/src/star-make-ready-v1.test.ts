import assert from 'node:assert/strict';
import test from 'node:test';

import {
  StarMakeReadyReceiptV1Schema,
  deriveParzifalIdentityReceiptPayloadDigestV1,
  deriveStarMakeReadyReceiptDigestV1,
} from './star-make-ready-v1.js';
import {
  deriveCharacterIdentityBindingDigestV1,
} from './character-identity-v1.js';

function payload(): Record<string, unknown> {
  const identityBindingDigest = deriveCharacterIdentityBindingDigestV1({
    subject_id: 'subject-1',
    face_id: 'face-1',
    voice_id: 'voice-1',
  });
  const parzifalPayload = {
    contract_version: 'ParzifalIdentityReceipt.v1' as const,
    receipt_id: 'parzifal-receipt-1',
    workspace_id: 'workspace-1',
    run_id: 'run-1',
    subject_id: 'subject-1',
    face_id: 'face-1',
    voice_id: 'voice-1',
    identity_binding_digest: identityBindingDigest,
    element_lock_digest: `sha256:${'1'.repeat(64)}`,
  };
  const parzifalReceipt = {
    ...parzifalPayload,
    payload_digest:
      deriveParzifalIdentityReceiptPayloadDigestV1(parzifalPayload),
  };
  const makeReadyPayload = {
    contract_version: 'StarMakeReadyReceipt.v1' as const,
    workspace_id: 'workspace-1',
    run_id: 'run-1',
    parzifal_record_ref: {
      id: parzifalReceipt.receipt_id,
      version: 1,
      digest: parzifalReceipt.payload_digest,
    },
    parzifal_receipt: parzifalReceipt,
    current_element_lock_digest: parzifalReceipt.element_lock_digest,
    provider_call: 'none' as const,
  };
  return {
    ...makeReadyPayload,
    receipt_digest: deriveStarMakeReadyReceiptDigestV1(makeReadyPayload),
  };
}

test('Star make-ready receipt accepts exact record, scope, lock, and identity bindings', () => {
  const parsed = StarMakeReadyReceiptV1Schema.parse(payload());

  assert.equal(
    parsed.parzifal_record_ref.id,
    parsed.parzifal_receipt.receipt_id,
  );
  assert.equal(
    parsed.parzifal_record_ref.digest,
    parsed.parzifal_receipt.payload_digest,
  );
  assert.equal(parsed.provider_call, 'none');
});

test('Star make-ready receipt fails closed on record or lock drift', () => {
  const wrongRecord = payload() as any;
  wrongRecord.parzifal_record_ref.id = 'other-receipt';
  assert.equal(StarMakeReadyReceiptV1Schema.safeParse(wrongRecord).success, false);

  const wrongLock = payload() as any;
  wrongLock.current_element_lock_digest = `sha256:${'2'.repeat(64)}`;
  assert.equal(StarMakeReadyReceiptV1Schema.safeParse(wrongLock).success, false);

  const providerArgument = payload() as any;
  providerArgument.dispatch = { provider: 'seedream' };
  assert.equal(
    StarMakeReadyReceiptV1Schema.safeParse(providerArgument).success,
    false,
  );
});
