import assert from 'node:assert/strict';
import test from 'node:test';

import {
  FactoryPaidBudgetAuthorityV1Schema,
  FactoryPaidBudgetApprovalReceiptV1Schema,
  VerifiedFactoryPaidBudgetAuthorityV1,
  factoryPaidBudgetApprovalReceiptAuthorizesV1,
  factoryPaidBudgetAuthorityFromVerifiedV1,
  buildFactoryPaidBudgetAuthorityV1,
  deriveFactoryPaidBudgetApprovalSubjectDigestV1,
  deriveFactoryPaidBudgetApprovalReceiptDigestV1,
  deriveFactoryPaidBudgetAuthorityDigestV1,
  deriveFactoryPaidBudgetIdempotencyKeyV1,
  factoryBeatManifestBindsPaidAuthorityV1,
  factoryBeatManifestStructurallyBindsPaidAuthorityV1,
  requireFactoryBeatManifestPaidAuthorityV1,
} from './index.js';
import { sha256Digest } from './factory/digest.js';

const workspaceId = '00000000-0000-4000-8000-000000000001';
const runId = '00000000-0000-4000-8000-000000000002';
const costProfileDigest = sha256Digest({ pricing: 'fal-kling-2026-08-01' });
let resolvedIdentity: Record<string, unknown> | null = null;
const resolver = { isCurrentApproval: (identity: Record<string, unknown>) => {
  resolvedIdentity = identity;
  return true;
} };

function approvalReceipt(overrides: Record<string, unknown> = {}) {
  const body = {
    contract_version: 'FactoryPaidBudgetApprovalReceipt.v1' as const,
    receipt_id: 'approval-paid-budget-1', workspace_id: workspaceId,
    run_id: runId, factory_revision: 7, all_beat_count: 5,
    paid_calls: { script: 1 as const, image: 5, video: 5, voice: 5, render: 1 as const, retries: 0 as const, fallbacks: 0 as const, character_lock: 0 as const },
    max_total_cost_microunits: 12_500_000, currency: 'USD',
    cost_profile_digest: costProfileDigest, pricing_policy_revision: 3,
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
    cost_profile_digest: costProfileDigest,
    pricing_policy_revision: 3,
    approval_receipt: receipt,
    at_utc: '2026-08-01T08:00:00Z',
    resolver,
  }).authority;
}

function verifiedAuthority() {
  const receipt = approvalReceipt();
  return factoryPaidBudgetAuthorityFromVerifiedV1(
    authority(), receipt, '2026-08-01T08:00:00Z', resolver,
  );
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

test('verified authority is non-serializable and is the only manifest capability', () => {
  const verified = verifiedAuthority();
  assert.equal(verified instanceof VerifiedFactoryPaidBudgetAuthorityV1, true);
  assert.throws(() => JSON.stringify(verified));
  assert.throws(
    () => new VerifiedFactoryPaidBudgetAuthorityV1(authority(), Symbol('fake')),
    /only be minted/,
  );
  assert.equal(Object.isFrozen(VerifiedFactoryPaidBudgetAuthorityV1), true);
  assert.equal(Object.isFrozen(VerifiedFactoryPaidBudgetAuthorityV1.prototype), true);
  const manifest = {
    workspace_id: workspaceId, run_id: runId, factory_revision: 7,
    beats: Array.from({ length: 5 }, () => ({})),
    paid_budget_authority_digest: authority().authority_digest,
  };
  assert.equal(factoryBeatManifestBindsPaidAuthorityV1(manifest as never, verified), true);
  assert.equal(factoryBeatManifestBindsPaidAuthorityV1(manifest as never, authority() as never), false);
  assert.equal(
    factoryBeatManifestStructurallyBindsPaidAuthorityV1(manifest as never, authority()),
    true,
  );
  assert.equal(requireFactoryBeatManifestPaidAuthorityV1(manifest as never, verified), verified);
  assert.throws(
    () => requireFactoryBeatManifestPaidAuthorityV1(manifest as never, authority()),
    /VerifiedFactoryPaidBudgetAuthority/,
  );
  assert.equal(Object.isFrozen(verified.authority), true);
  assert.equal(Object.isFrozen(verified.authority.paid_calls), true);
  assert.throws(() => { verified.authority.paid_calls.video = 99; });

  const forged = Object.setPrototypeOf(
    { ...authority(), authority: authority() },
    VerifiedFactoryPaidBudgetAuthorityV1.prototype,
  );
  assert.equal(factoryBeatManifestBindsPaidAuthorityV1(manifest as never, forged), false);
  assert.throws(
    () => requireFactoryBeatManifestPaidAuthorityV1(manifest as never, forged),
    /VerifiedFactoryPaidBudgetAuthority/,
  );
});

test('cost profile and current pricing revision bind resolver identity', () => {
  const receipt = approvalReceipt();
  const parsed = authority();
  assert.equal(parsed.cost_profile_digest, costProfileDigest);
  assert.equal(parsed.pricing_policy_revision, 3);
  assert.equal(factoryPaidBudgetApprovalReceiptAuthorizesV1(
    receipt, parsed, '2026-08-01T08:00:00Z', resolver,
  ), true);
  assert.equal(resolvedIdentity?.cost_profile_digest, costProfileDigest);
  assert.equal(resolvedIdentity?.pricing_policy_revision, 3);
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
  const paidCallDrift = structuredClone(authority());
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
  for (const drift of [
    { cost_profile_digest: sha256Digest({ pricing: 'other' }) },
    { pricing_policy_revision: 4 },
  ]) {
    const changed = { ...authority(), ...drift };
    changed.authority_digest = deriveFactoryPaidBudgetAuthorityDigestV1(changed);
    assert.equal(FactoryPaidBudgetAuthorityV1Schema.safeParse(changed).success, false);
  }
});

test('mirror parity vectors match Python authority', () => {
  const value = authority();
  assert.equal(
    value.approval_subject_digest,
    'sha256:860647e42e99dec7d580e5a323207e617f1351bfe5d20b20b99e77edc4cc55a4',
  );
  assert.equal(
    value.idempotency_key,
    'sha256:692f716bcad148945500ca48292ab1aee705bf128de1f2515a2d9449e1308ba1',
  );
  assert.equal(
    value.authority_digest,
    'sha256:c2cdbc6b4111fbba80ff3bea160d8391f4461eb1ae364f29c5bed3e8a2721e8b',
  );
});
