import assert from 'node:assert/strict';
import test from 'node:test';

import {
  FactoryPaidBudgetAuthorityV1Schema,
  buildFactoryPaidBudgetAuthorityV1,
  deriveFactoryPaidBudgetApprovalSubjectDigestV1,
  deriveFactoryPaidBudgetAuthorityDigestV1,
  deriveFactoryPaidBudgetIdempotencyKeyV1,
} from './index.js';
import { sha256Digest } from './factory/digest.js';

const workspaceId = '00000000-0000-4000-8000-000000000001';
const runId = '00000000-0000-4000-8000-000000000002';
const approvalReceiptDigest = sha256Digest({ approval: 'paid-budget-v1' });

function authority(overrides: Record<string, unknown> = {}) {
  return buildFactoryPaidBudgetAuthorityV1({
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: 7,
    all_beat_count: 5,
    max_total_cost_microunits: 12_500_000,
    currency: 'USD',
    approval_receipt_id: 'approval-paid-budget-1',
    approval_receipt_digest: approvalReceiptDigest,
    ...overrides,
  });
}

test('mirror builds and validates every pre-script paid binding', () => {
  const value = FactoryPaidBudgetAuthorityV1Schema.parse(authority());
  assert.equal(
    value.approval_subject_digest,
    deriveFactoryPaidBudgetApprovalSubjectDigestV1(value),
  );
  assert.equal(
    value.idempotency_key,
    deriveFactoryPaidBudgetIdempotencyKeyV1(value),
  );
  assert.equal(
    value.authority_digest,
    deriveFactoryPaidBudgetAuthorityDigestV1(value),
  );
});

test('mirror rejects count, money, currency, approval, and legacy drift', () => {
  for (const allBeatCount of [0, 17, true, 1.5]) {
    assert.equal(
      FactoryPaidBudgetAuthorityV1Schema.safeParse(
        { ...authority(), all_beat_count: allBeatCount },
      ).success,
      false,
    );
  }
  for (const maxTotalCost of [0, -1, true, 1.5, '12500000']) {
    assert.equal(
      FactoryPaidBudgetAuthorityV1Schema.safeParse(
        { ...authority(), max_total_cost_microunits: maxTotalCost },
      ).success,
      false,
    );
  }
  assert.equal(
    FactoryPaidBudgetAuthorityV1Schema.safeParse(
      { ...authority(), exact: true },
    ).success,
    false,
  );
  const paidCallDrift = authority();
  paidCallDrift.paid_calls.video = 4;
  paidCallDrift.approval_subject_digest = (
    deriveFactoryPaidBudgetApprovalSubjectDigestV1(paidCallDrift)
  );
  paidCallDrift.idempotency_key = (
    deriveFactoryPaidBudgetIdempotencyKeyV1(paidCallDrift)
  );
  paidCallDrift.authority_digest = (
    deriveFactoryPaidBudgetAuthorityDigestV1(paidCallDrift)
  );
  assert.equal(
    FactoryPaidBudgetAuthorityV1Schema.safeParse(paidCallDrift).success,
    false,
  );
  const approvalDrift = {
    ...authority(),
    approval_receipt_digest: sha256Digest({ approval: 'other' }),
  };
  approvalDrift.authority_digest = deriveFactoryPaidBudgetAuthorityDigestV1(
    approvalDrift,
  );
  assert.equal(
    FactoryPaidBudgetAuthorityV1Schema.safeParse(approvalDrift).success,
    false,
  );
});

test('mirror parity vectors match Python authority', () => {
  const value = authority();
  assert.equal(
    value.approval_subject_digest,
    'sha256:0064203849c310151ff1e8b3ecc478e27d28294e4119b81366c568f8df25b9db',
  );
  assert.equal(
    value.idempotency_key,
    'sha256:53a29f902bce3f2777c0b4888c03eb3ddc99d604eba0c7d3516f03c8d7a49942',
  );
  assert.equal(
    value.authority_digest,
    'sha256:c4421ca6c74a7490a6c0ee3cd39ae0aea71018d5528ded5c2bda08d3adebbc8e',
  );
});
