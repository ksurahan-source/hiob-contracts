import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ParzifalIdentityBindingV1Schema,
  StrategyApprovalBundleV1Schema,
  StrategyApprovalReceiptV2Schema,
  deriveParzifalIdentityBindingIdV1,
  strategyApprovalBundleDigestV1,
  strategyApprovalStrategyDigestV1,
  validateParzifalIdentityBindingV1,
  validateStrategyApprovalEvidenceV2,
} from './strategy-approval-v2.js';
import { canonicalContractDigestV1 } from './ares-script-revision-v1.js';
import * as packageRoot from './index.js';

const RUN_ID = '11111111-1111-4111-8111-111111111111';
const WORKSPACE_ID = '22222222-2222-4222-8222-222222222222';
const APPROVAL_ID = '33333333-3333-4333-8333-333333333333';
const TARGET_PROFILE = { persona: { pain: '반복 실패', role: '창업자' } };
const MASTER_SHEET = { status: 'identity_sealed', identity: { name: '대표' } };
const CAST_SHEETS = { status: 'sealed', lead: { persona_id: 'target' } };

if (false) {
  const readonlyContract = StrategyApprovalBundleV1Schema.parse(bundleData());
  // @ts-expect-error parsed contract roots are readonly
  readonlyContract.run_id = RUN_ID;
  // @ts-expect-error nested immutable JSON snapshots are readonly
  readonlyContract.strategy.audience = '변조';
}

function bundleData(): Record<string, unknown> {
  return {
    contract_version: 'StrategyApprovalBundle.v1',
    run_id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    strategy: {
      audience: '창업자',
      beats: [{ index: 0, claim: '빠른 검증' }],
    },
    brief_patch: { strategy_full: { audience: '창업자' } },
    attributes_patch: {
      strategy_status: 'approved',
      identity_source: 'parzifal',
      target_profile: TARGET_PROFILE,
      parzifal_master_sheet: MASTER_SHEET,
      parzifal_cast_sheets: CAST_SHEETS,
    },
  };
}

function receiptData(bundle = bundleData()): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    contract_version: 'StrategyApprovalReceipt.v2',
    approval_id: APPROVAL_ID,
    claim_id: '44444444-4444-4444-8444-444444444444',
    run_id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    strategy_input_revision: 0,
    approval_revision: 1,
    source_digest: `sha256:${'a'.repeat(64)}`,
    strategy_digest: canonicalContractDigestV1(
      bundle.strategy as Record<string, unknown>,
    ),
    bundle_digest: canonicalContractDigestV1(bundle),
    approved_by_account_id: '66666666-6666-4666-8666-666666666666',
    approved_at: '2026-07-24T01:02:03.123456Z',
  };
  payload.receipt_digest = canonicalContractDigestV1(payload);
  return payload;
}

function bindingData(
  bundle = bundleData(),
  receipt = receiptData(bundle),
): Record<string, unknown> {
  const patch = bundle.attributes_patch as Record<string, unknown>;
  const targetProfile = patch.target_profile as Record<string, unknown>;
  const masterSheet = patch.parzifal_master_sheet as Record<string, unknown>;
  const castSheets = patch.parzifal_cast_sheets as Record<string, unknown>;
  const payload: Record<string, unknown> = {
    contract_version: 'ParzifalIdentityBinding.v1',
    binding_id: deriveParzifalIdentityBindingIdV1(
      receipt.receipt_digest as string,
    ),
    binding_revision: 1,
    workspace_id: WORKSPACE_ID,
    run_id: RUN_ID,
    strategy_approval_id: APPROVAL_ID,
    strategy_digest: receipt.strategy_digest,
    strategy_bundle_digest: receipt.bundle_digest,
    strategy_receipt_digest: receipt.receipt_digest,
    target_profile: targetProfile,
    target_profile_digest: canonicalContractDigestV1(targetProfile),
    master_sheet: masterSheet,
    master_sheet_digest: canonicalContractDigestV1(masterSheet),
    cast_sheets: castSheets,
    cast_sheets_digest: canonicalContractDigestV1(castSheets),
    identity_source: 'parzifal',
    source_node: 'parzifal.identity.bind',
    source_revision: 'parzifal.identity.bind.v1',
    created_at: receipt.approved_at,
    created_by_account_id: receipt.approved_by_account_id,
  };
  payload.binding_digest = canonicalContractDigestV1(payload);
  return payload;
}

test('Python and TypeScript canonical digest golden vectors match', () => {
  assert.equal(packageRoot.StrategyApprovalBundleV1Schema, StrategyApprovalBundleV1Schema);
  assert.equal(packageRoot.ParzifalIdentityBindingV1Schema, ParzifalIdentityBindingV1Schema);
  const bundle = StrategyApprovalBundleV1Schema.parse(bundleData());
  const receipt = StrategyApprovalReceiptV2Schema.parse(receiptData());
  const binding = ParzifalIdentityBindingV1Schema.parse(bindingData());
  assert.equal(
    strategyApprovalStrategyDigestV1(bundle),
    'sha256:663d4eabb6338116bfb922a00a517b83bc2dadb6e99ef58b967d061d3d3fc9ca',
  );
  assert.equal(
    strategyApprovalBundleDigestV1(bundle),
    'sha256:8d9e3a6766f5bd9e3244891aaf3f0b626121b8f76242718b875d9c0f45fc6355',
  );
  assert.equal(
    receipt.receipt_digest,
    'sha256:4cdeb2ee6af0f7ddc2cdf7f1ddf28c77bad29392252031793086e30e69dc82e7',
  );
  assert.equal(
    binding.binding_digest,
    'sha256:885903ee232604a8eb69afbd6f90e5a03ae8c6557a1464941884ccfab686a1d9',
  );
});

test('evidence and binding validate exact scope and immutable snapshots', () => {
  const bundle = bundleData();
  const receipt = receiptData(bundle);
  const evidence = validateStrategyApprovalEvidenceV2(bundle, receipt);
  const binding = validateParzifalIdentityBindingV1(
    bindingData(bundle, receipt),
    evidence,
  );
  assert.equal(binding.strategy_approval_id, evidence.receipt.approval_id);
  assert.throws(() => {
    (binding.target_profile as { forged?: boolean }).forged = true;
  }, TypeError);
});

test('tamper, extra fields, cross-scope, and noncanonical values fail closed', () => {
  const extra = { ...bundleData(), extra: true };
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(extra).success, false);

  const tamperedReceipt = receiptData();
  tamperedReceipt.receipt_digest = `sha256:${'0'.repeat(64)}`;
  assert.equal(StrategyApprovalReceiptV2Schema.safeParse(tamperedReceipt).success, false);

  const tamperedBinding = bindingData();
  (tamperedBinding.target_profile as Record<string, unknown>).persona = {
    pain: '변조',
  };
  assert.equal(ParzifalIdentityBindingV1Schema.safeParse(tamperedBinding).success, false);

  const foreignReceipt = receiptData();
  foreignReceipt.run_id = '77777777-7777-4777-8777-777777777777';
  const { receipt_digest: ignored, ...foreignBody } = foreignReceipt;
  void ignored;
  foreignReceipt.receipt_digest = canonicalContractDigestV1(foreignBody);
  assert.throws(
    () => validateStrategyApprovalEvidenceV2(bundleData(), foreignReceipt),
    /run_id scope mismatch/,
  );

  const forgedBinding = bindingData();
  forgedBinding.strategy_approval_id = '88888888-8888-4888-8888-888888888888';
  const { binding_digest: ignoredBinding, ...forgedBody } = forgedBinding;
  void ignoredBinding;
  forgedBinding.binding_digest = canonicalContractDigestV1(forgedBody);
  assert.throws(
    () => validateParzifalIdentityBindingV1(
      forgedBinding,
      { bundle: bundleData(), receipt: receiptData() },
    ),
    /strategy_approval_id/,
  );

  const approvedBundle = bundleData();
  const approvedReceipt = receiptData(approvedBundle);
  const forgedSnapshot = bindingData(approvedBundle, approvedReceipt);
  forgedSnapshot.target_profile = { persona: { pain: '공격자' } };
  forgedSnapshot.target_profile_digest = canonicalContractDigestV1(
    forgedSnapshot.target_profile as Record<string, unknown>,
  );
  const { binding_digest: ignoredSnapshotDigest, ...forgedSnapshotBody } = forgedSnapshot;
  void ignoredSnapshotDigest;
  forgedSnapshot.binding_digest = canonicalContractDigestV1(forgedSnapshotBody);
  assert.throws(
    () => validateParzifalIdentityBindingV1(
      forgedSnapshot,
      { bundle: approvedBundle, receipt: approvedReceipt },
    ),
    /does not match approved bundle/,
  );

  const forgedMetadata = bindingData(approvedBundle, approvedReceipt);
  forgedMetadata.created_by_account_id = '99999999-9999-4999-8999-999999999999';
  const { binding_digest: ignoredMetadataDigest, ...forgedMetadataBody } = forgedMetadata;
  void ignoredMetadataDigest;
  forgedMetadata.binding_digest = canonicalContractDigestV1(forgedMetadataBody);
  assert.throws(
    () => validateParzifalIdentityBindingV1(
      forgedMetadata,
      { bundle: approvedBundle, receipt: approvedReceipt },
    ),
    /created_by_account_id/,
  );
  assert.throws(
    () => deriveParzifalIdentityBindingIdV1(`SHA256:${'0'.repeat(64)}`),
    /lowercase sha256/,
  );

  const upperUuid = bundleData();
  upperUuid.run_id = 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA';
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(upperUuid).success, false);

  const offsetTimestamp = receiptData();
  offsetTimestamp.approved_at = '2026-07-24T01:02:03+00:00';
  assert.equal(StrategyApprovalReceiptV2Schema.safeParse(offsetTimestamp).success, false);

  const whitespaceSource = bindingData();
  whitespaceSource.source_revision = ' 5cbcbcf ';
  assert.equal(ParzifalIdentityBindingV1Schema.safeParse(whitespaceSource).success, false);

  const nonUuidApprover = receiptData();
  nonUuidApprover.approved_by_account_id = 'not-a-uuid';
  const { receipt_digest: ignoredApproverDigest, ...nonUuidApproverBody } = nonUuidApprover;
  void ignoredApproverDigest;
  nonUuidApprover.receipt_digest = canonicalContractDigestV1(nonUuidApproverBody);
  assert.equal(StrategyApprovalReceiptV2Schema.safeParse(nonUuidApprover).success, false);

  const cyclic: Record<string, unknown> = {};
  cyclic.self = cyclic;
  const cyclicBundle = bundleData();
  cyclicBundle.strategy = cyclic;
  assert.doesNotThrow(() => StrategyApprovalBundleV1Schema.safeParse(cyclicBundle));
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(cyclicBundle).success, false);

  const hugeSparse: unknown[] = [];
  hugeSparse.length = 0xFFFF_FFFF;
  const sparseBundle = bundleData();
  sparseBundle.strategy = { beats: hugeSparse };
  assert.doesNotThrow(() => StrategyApprovalBundleV1Schema.safeParse(sparseBundle));
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(sparseBundle).success, false);

  const inheritedRoot = Object.create(bundleData()) as Record<string, unknown>;
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(inheritedRoot).success, false);

  const symbolRoot = bundleData();
  Object.defineProperty(symbolRoot, Symbol('forged'), {
    enumerable: true,
    value: true,
  });
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(symbolRoot).success, false);

  const accessorRoot = bundleData();
  Object.defineProperty(accessorRoot, 'run_id', {
    enumerable: true,
    get: () => RUN_ID,
  });
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(accessorRoot).success, false);

  const hiddenRoot = bundleData();
  Object.defineProperty(hiddenRoot, 'hidden', {
    enumerable: false,
    value: true,
  });
  assert.equal(StrategyApprovalBundleV1Schema.safeParse(hiddenRoot).success, false);
});
