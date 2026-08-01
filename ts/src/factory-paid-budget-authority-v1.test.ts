import assert from 'node:assert/strict';
import test from 'node:test';

import {
  FactoryPaidBudgetAuthorityV1Schema,
  FactoryPaidBudgetApprovalReceiptV1Schema,
  factoryPaidBudgetApprovalReceiptAuthorizesV1,
  factoryPaidBudgetAuthorityFromVerifiedV1,
  buildFactoryPaidBudgetAuthorityV1,
  deriveFactoryPaidBudgetApprovalSubjectDigestV1,
  deriveFactoryPaidBudgetApprovalReceiptDigestV1,
  deriveFactoryPaidBudgetAuthorityDigestV1,
  deriveFactoryPaidBudgetIdempotencyKeyV1,
} from './index.js';
import { sha256Digest } from './factory/digest.js';

const workspaceId = '00000000-0000-4000-8000-000000000001';
const runId = '00000000-0000-4000-8000-000000000002';
const resolver = { isCurrentApproval: () => true };

function approvalReceipt(overrides: Record<string, unknown> = {}) {
  const body = {
    contract_version: 'FactoryPaidBudgetApprovalReceipt.v1' as const,
    receipt_id: 'approval-paid-budget-1', workspace_id: workspaceId,
    run_id: runId, factory_revision: 7, all_beat_count: 5,
    paid_calls: { script: 1 as const, image: 5, video: 5, voice: 5, render: 1 as const, retries: 0 as const, fallbacks: 0 as const, character_lock: 0 as const },
    max_total_cost_microunits: 12_500_000, currency: 'USD',
    approver_account_id: 'account-owner', decision: 'approved' as const,
    policy_version: 'paid-budget-policy-v1', state_revision: 1,
    approved_at_utc: '2026-08-01T07:00:00Z', expires_at_utc: '2026-08-01T09:00:00Z',
    revoked_at_utc: null, transaction_audit_id: 'approval-paid-budget-1',
    ...overrides,
  };
  const withSubject = { ...body, approval_subject_digest: deriveFactoryPaidBudgetApprovalSubjectDigestV1(body) };
  return FactoryPaidBudgetApprovalReceiptV1Schema.parse({
    ...withSubject, receipt_digest: deriveFactoryPaidBudgetApprovalReceiptDigestV1(withSubject),
  });
}

function authority(overrides: Record<string, unknown> = {}) {
  const receipt = approvalReceipt(overrides);
  return buildFactoryPaidBudgetAuthorityV1({
    workspace_id: workspaceId,
    run_id: runId,
    factory_revision: 7,
    all_beat_count: 5,
    max_total_cost_microunits: 12_500_000,
    currency: 'USD',
    approval_receipt: receipt,
    at_utc: '2026-08-01T08:00:00Z',
    resolver,
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

test('structural receipt is not bearer authority without current resolver state', () => {
  const receipt = approvalReceipt();
  const staleResolver = { isCurrentApproval: () => false };
  assert.equal(factoryPaidBudgetApprovalReceiptAuthorizesV1(
    receipt, authority(), '2026-08-01T08:00:00Z', staleResolver,
  ), false);
  assert.throws(() => factoryPaidBudgetAuthorityFromVerifiedV1(
    authority(), receipt, '2026-08-01T08:00:00Z', staleResolver,
  ));
});

test('approval receipt safeParse rejects impossible UTC without throwing', () => {
  const receipt = approvalReceipt();
  const invalid = { ...receipt, expires_at_utc: '2026-02-31T09:00:00Z' };
  assert.doesNotThrow(() => FactoryPaidBudgetApprovalReceiptV1Schema.safeParse(invalid));
  assert.equal(FactoryPaidBudgetApprovalReceiptV1Schema.safeParse(invalid).success, false);
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
    'sha256:83f4b2491567bbea3b86b971f1bd4613a5ebc2ee3d96060dcac9301689e0063a',
  );
  assert.equal(
    value.authority_digest,
    'sha256:57bf474f67bddce6272f5540dd45cdf1cb4cd7cfa0119c274f22d8ce8b7899af',
  );
});
