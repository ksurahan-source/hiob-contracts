/** Python-authoritative Ares XL V1 mirror and parity vectors. */
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AresApprovalBeginCommandV1Schema,
  AresApprovalCommandV1Schema,
  AresApprovalReceiptV1Schema,
  AresBeatPlanRevisionV1Schema,
  AresScriptRevisionV1Schema,
  BeatPlanV1Schema,
  ScriptPackageV1Schema,
  approvalCommandBindsRevisionV1,
  approvalReceiptAuthorizesV1,
  canonicalContractJsonV1,
  canonicalContractDigestV1,
  deriveAresG1SubjectDigestV1,
} from './ares-script-revision-v1.js';
import { sha256Digest } from './factory/digest.js';

const targetProfileDigest = sha256Digest({ target: 'mom' });
const identityLockDigest = sha256Digest({ identity: 'lead-v3' });
const workspaceId = '00000000-0000-4000-8000-000000000001';
const runId = '00000000-0000-4000-8000-000000000002';
const scriptRevisionId = '00000000-0000-4000-8000-000000000003';
const candidateId = '00000000-0000-4000-8000-000000000004';
const planRevisionId = '00000000-0000-4000-8000-000000000005';

function withDigest<T extends Record<string, unknown>>(body: T, field: string) {
  return { ...body, [field]: sha256Digest(body) };
}

function scriptPackageData() {
  return withDigest({
    contract_version: 'AresScriptPackage.v1',
    workspace_id: workspaceId,
    run_id: runId,
    revision_id: scriptRevisionId,
    candidate_id: candidateId,
    factory_revision: 7,
    master_sales_script: {
      title: '엄마를 위한 XL',
      positioning: '한 번에 이해되는 제품',
      hook: { line: '엄마, 이건 꼭 보세요.', register: '가십' },
      cta: { line: '지금 확인해 보세요.', action: '확인' },
      persona_cast: [{ role: 'lead', subject_id: 'mom' }],
      beats: [
        {
          beat_index: 0,
          text: '엄마, 이건 꼭 보세요.',
          direction: { shot: 'MCU', subject: '엄마', setting: '주방', overlay: '꼭 보세요' },
        },
        {
          beat_index: 1,
          text: '지금 확인해 보세요.',
          direction: { shot: 'CU', subject: '제품', setting: '테이블', overlay: '지금 확인' },
        },
      ],
      meta_copy: { headline: 'HIOB XL 👩‍👧' },
    },
    voice_script: [
      { beat_index: 0, text: '엄마, 이건 꼭 보세요.' },
      { beat_index: 1, text: '지금 확인해 보세요.' },
    ],
    caption_script: [
      { beat_index: 0, text: '엄마, 이건 꼭 보세요.' },
      { beat_index: 1, text: '지금 확인' },
    ],
    pronunciation_overrides: { HIOB: '하이옵', XL: '엑스엘' },
  }, 'package_digest');
}

function beatPlanData() {
  return withDigest({
    contract_version: 'AresBeatPlan.v1',
    workspace_id: workspaceId,
    run_id: runId,
    revision_id: planRevisionId,
    script_revision_id: scriptRevisionId,
    factory_revision: 7,
    script_package_digest: scriptPackageData().package_digest,
    beats: [
      {
        beat_index: 0,
        text: '엄마, 이건 꼭 보세요.',
        caption: '엄마, 이건 꼭 보세요.',
        scene_direction: { shot: 'MCU', subject: '엄마', setting: '주방', overlay: '꼭 보세요' },
      },
      {
        beat_index: 1,
        text: '지금 확인해 보세요.',
        caption: '지금 확인',
        scene_direction: { shot: 'CU', subject: '제품', setting: '테이블', overlay: '지금 확인' },
      },
    ],
    production_plan: {
      visual: { approved: true },
      sound: { music_vibe: 'warm' },
    },
  }, 'plan_digest');
}

function scriptRevisionData() {
  return withDigest({
    contract_version: 'AresScriptRevision.v1',
    workspace_id: workspaceId,
    run_id: runId,
    revision_id: scriptRevisionId,
    candidate_id: candidateId,
    factory_revision: 7,
    script_package: scriptPackageData(),
  }, 'revision_digest');
}

function planRevisionData() {
  return withDigest({
    contract_version: 'AresBeatPlanRevision.v1',
    workspace_id: workspaceId,
    run_id: runId,
    revision_id: planRevisionId,
    script_revision_id: scriptRevisionId,
    factory_revision: 7,
    approved_script_package_digest: scriptPackageData().package_digest,
    beat_plan: beatPlanData(),
  }, 'revision_digest');
}

function commandData(kind: 'script' | 'production_plan' = 'script') {
  const scriptPackageDigest = scriptPackageData().package_digest;
  const beatPlanDigest = beatPlanData().plan_digest;
  const g1SubjectDigest = deriveAresG1SubjectDigestV1(
    targetProfileDigest,
    identityLockDigest,
    scriptPackageDigest,
    beatPlanDigest,
  );
  return withDigest({
    contract_version: 'AresApprovalCommand.v1',
    command_id: `command-${kind}`,
    workspace_id: workspaceId,
    run_id: runId,
    revision_id: kind === 'script' ? scriptRevisionId : planRevisionId,
    approval_kind: kind,
    artifact_digest: kind === 'script' ? scriptPackageDigest : g1SubjectDigest,
    target_profile_digest: targetProfileDigest,
    identity_lock_digest: identityLockDigest,
    script_package_digest: scriptPackageDigest,
    beat_plan_digest: kind === 'script' ? null : beatPlanDigest,
    g1_subject_digest: kind === 'script' ? null : g1SubjectDigest,
    approver_account_id: 'account-1',
    policy_version: 'ares-approval.v1',
    factory_revision: 7,
    expected_state_revision: 10,
    issued_at_utc: '2026-07-23T01:02:03Z',
  }, 'command_digest');
}

function beginCommandData() {
  return withDigest({
    contract_version: 'AresApprovalBeginCommand.v1',
    command_id: 'command-begin-script',
    workspace_id: workspaceId,
    run_id: runId,
    candidate_id: candidateId,
    requester_account_id: 'account-1',
    policy_version: 'ares-approval.v1',
    factory_revision: 7,
    expected_state_revision: 0,
    issued_at_utc: '2026-07-23T01:02:02Z',
  }, 'command_digest');
}

function receiptData(kind: 'script' | 'production_plan' = 'script') {
  const command = commandData(kind);
  return withDigest({
    contract_version: 'AresApprovalReceipt.v1',
    receipt_id: 'receipt-script',
    command_id: command.command_id,
    command_digest: command.command_digest,
    workspace_id: command.workspace_id,
    run_id: command.run_id,
    revision_id: command.revision_id,
    approval_kind: command.approval_kind,
    artifact_digest: command.artifact_digest,
    target_profile_digest: command.target_profile_digest,
    identity_lock_digest: command.identity_lock_digest,
    script_package_digest: command.script_package_digest,
    beat_plan_digest: command.beat_plan_digest,
    g1_subject_digest: command.g1_subject_digest,
    approver_account_id: command.approver_account_id,
    decision: 'approved',
    policy_version: 'ares-approval.v1',
    factory_revision: 7,
    state_revision: 11,
    approved_at_utc: '2026-07-23T01:02:04Z',
    expires_at_utc: '2026-07-23T02:02:04Z',
    revoked_at_utc: null,
    transaction_audit_id: 'receipt-script',
  }, 'receipt_digest');
}

test('Python parity vectors for artifacts and G1 subject', () => {
  const packageValue = ScriptPackageV1Schema.parse(scriptPackageData());
  const plan = BeatPlanV1Schema.parse(beatPlanData());
  const scriptRevision = AresScriptRevisionV1Schema.parse(scriptRevisionData());
  const planRevision = AresBeatPlanRevisionV1Schema.parse(planRevisionData());
  const command = AresApprovalCommandV1Schema.parse(commandData());
  const beginCommand = AresApprovalBeginCommandV1Schema.parse(beginCommandData());
  const receipt = AresApprovalReceiptV1Schema.parse(receiptData());
  assert.equal(packageValue.package_digest, 'sha256:8c0be4e08ea3065be5552473e5edad1751d4eef5536ee03413a41d95b9d52ebf');
  assert.equal(plan.plan_digest, 'sha256:55af05b50381f9bdd3635fd98950a4047a66fad0e9b679ae664f7471987784d3');
  assert.equal(scriptRevision.revision_digest, 'sha256:4f49dc5b80f1f243a4d6239b5b428e8c776a2b8346e4529db03cb4958144e4ed');
  assert.equal(planRevision.revision_digest, 'sha256:18e253e8eb493b67c6f7a23bb1c436267088c1e0911510fcd8205b3617e510e3');
  assert.equal(command.command_digest, 'sha256:fd6c3661bcc63b4d541b77514a2d2bf8577245db9de1d465bc27bcae87166925');
  assert.equal(beginCommand.command_digest, 'sha256:6bd123c8be716cd99eddb4a4a95e11f294b0e7c3f03f4477060cfe51701fd3b0');
  assert.equal(receipt.receipt_digest, 'sha256:64156cc4a48413bd95c4a975315e7a77c90aac6cb1e9b797b7acf1d969b48d92');
  assert.equal(
    deriveAresG1SubjectDigestV1(
      targetProfileDigest,
      identityLockDigest,
      packageValue.package_digest,
      plan.plan_digest,
    ),
    'sha256:b5e00fd8b06fe21a705ec9dbd11d23f11567301b1830c395048bfef53407b128',
  );
  assert.equal(canonicalContractDigestV1(scriptPackageData(), ['package_digest']), packageValue.package_digest);
});

test('mirror validates split revisions and rejects segment/scene drift', () => {
  AresScriptRevisionV1Schema.parse(scriptRevisionData());
  AresBeatPlanRevisionV1Schema.parse(planRevisionData());
  const badPackage = scriptPackageData();
  badPackage.voice_script = [
    { beat_index: 1, text: 'a' },
    { beat_index: 0, text: 'b' },
  ];
  badPackage.package_digest = canonicalContractDigestV1(badPackage, ['package_digest']);
  assert.equal(ScriptPackageV1Schema.safeParse(badPackage).success, false);

  const badPlan = beatPlanData();
  badPlan.beats[0].scene_direction.overlay = '변조';
  assert.equal(BeatPlanV1Schema.safeParse(badPlan).success, false);
});

test('receipt is not bearer authority and requires current resolver', () => {
  const receipt = AresApprovalReceiptV1Schema.parse(receiptData());
  const command = AresApprovalCommandV1Schema.parse(commandData());
  const revision = AresScriptRevisionV1Schema.parse(scriptRevisionData());
  assert.equal(approvalReceiptAuthorizesV1(
    receipt,
    command,
    revision,
    '2026-07-23T01:30:00Z',
    { isCurrentApproval: () => true },
  ), true);
  assert.equal(approvalReceiptAuthorizesV1(
    receipt,
    command,
    revision,
    '2026-07-23T01:30:00Z',
    { isCurrentApproval: () => false },
  ), false);
});

test('receipt CAS metadata must match the signed command', () => {
  const command = AresApprovalCommandV1Schema.parse(commandData());
  const revision = AresScriptRevisionV1Schema.parse(scriptRevisionData());
  for (const [field, value] of [
    ['policy_version', 'ares-approval.v2'],
    ['factory_revision', 8],
    ['state_revision', 12],
  ] as const) {
    const payload = { ...receiptData(), [field]: value };
    payload.receipt_digest = canonicalContractDigestV1(payload, ['receipt_digest']);
    const receipt = AresApprovalReceiptV1Schema.parse(payload);
    assert.equal(approvalReceiptAuthorizesV1(
      receipt,
      command,
      revision,
      '2026-07-23T01:30:00Z',
      { isCurrentApproval: () => true },
    ), false);
  }
});

test('production approval binds all four G1 subject digests', () => {
  const command = AresApprovalCommandV1Schema.parse(
    commandData('production_plan'),
  );
  const receipt = AresApprovalReceiptV1Schema.parse(
    receiptData('production_plan'),
  );
  const revision = AresBeatPlanRevisionV1Schema.parse(planRevisionData());
  const scriptRevision = AresScriptRevisionV1Schema.parse(scriptRevisionData());

  assert.equal(command.artifact_digest, command.g1_subject_digest);
  assert.notEqual(command.artifact_digest, command.beat_plan_digest);
  assert.equal(
    approvalReceiptAuthorizesV1(
      receipt,
      command,
      revision,
      '2026-07-23T01:30:00Z',
      { isCurrentApproval: () => true },
      scriptRevision,
    ),
    true,
  );
  assert.equal(
    approvalReceiptAuthorizesV1(
      receipt,
      command,
      revision,
      '2026-07-23T01:30:00Z',
      { isCurrentApproval: () => true },
    ),
    false,
  );

  const substituted = commandData('production_plan');
  substituted.target_profile_digest = sha256Digest({ target: 'other' });
  substituted.g1_subject_digest = deriveAresG1SubjectDigestV1(
    substituted.target_profile_digest,
    substituted.identity_lock_digest,
    substituted.script_package_digest,
    substituted.beat_plan_digest as string,
  );
  substituted.artifact_digest = substituted.g1_subject_digest;
  substituted.command_digest = canonicalContractDigestV1(
    substituted,
    ['command_digest'],
  );
  const substitutedCommand = AresApprovalCommandV1Schema.parse(substituted);
  assert.equal(
    approvalReceiptAuthorizesV1(
      receipt,
      substitutedCommand,
      revision,
      '2026-07-23T01:30:00Z',
      { isCurrentApproval: () => true },
      scriptRevision,
    ),
    false,
  );
});

test('production approval rejects a rehashed plan that drifts from approved script', () => {
  const scriptRevision = AresScriptRevisionV1Schema.parse(scriptRevisionData());
  const driftedPayload = planRevisionData();
  driftedPayload.beat_plan.beats[0].text = '변조된 대사';
  driftedPayload.beat_plan.plan_digest = canonicalContractDigestV1(
    driftedPayload.beat_plan,
    ['plan_digest'],
  );
  driftedPayload.revision_digest = canonicalContractDigestV1(
    driftedPayload,
    ['revision_digest'],
  );
  const driftedRevision = AresBeatPlanRevisionV1Schema.parse(driftedPayload);

  const commandPayload = commandData('production_plan');
  commandPayload.beat_plan_digest = driftedRevision.beat_plan.plan_digest;
  commandPayload.g1_subject_digest = deriveAresG1SubjectDigestV1(
    commandPayload.target_profile_digest,
    commandPayload.identity_lock_digest,
    commandPayload.script_package_digest,
    commandPayload.beat_plan_digest,
  );
  commandPayload.artifact_digest = commandPayload.g1_subject_digest;
  commandPayload.command_digest = canonicalContractDigestV1(
    commandPayload,
    ['command_digest'],
  );
  const command = AresApprovalCommandV1Schema.parse(commandPayload);

  assert.equal(
    approvalCommandBindsRevisionV1(
      command,
      driftedRevision,
      scriptRevision,
    ),
    false,
  );
});

test('contract digest matches Python for astral and integer-like keys', () => {
  assert.equal(canonicalContractJsonV1({ '\ue000': 1, '😀': 2 }), '{"":1,"😀":2}');
  assert.equal(
    canonicalContractDigestV1({ '\ue000': 1, '😀': 2 }),
    'sha256:871954531859c7572c6279f90eb83a594ddc3a289e8bdc28d2a84ffb8c1a1703',
  );
  assert.equal(
    canonicalContractDigestV1({ 10: 1, 2: 2 }),
    'sha256:4489ac68dd5e0c9eb21f0e6c3294139a7d51b793c0e2e515bdf6c12948537df1',
  );
});

test('contract digest rejects cross-language unsafe numbers', () => {
  for (const value of [-0, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => canonicalContractDigestV1({ value }), /safe integer/);
  }
});

test('parsed contracts are deeply immutable at runtime', () => {
  const packageValue = ScriptPackageV1Schema.parse(scriptPackageData());
  const master = packageValue.master_sales_script as Record<string, unknown>;
  const beats = master.beats as Array<Record<string, unknown>>;
  assert.equal(Object.isFrozen(packageValue), true);
  assert.equal(Object.isFrozen(master), true);
  assert.equal(Object.isFrozen(beats), true);
  assert.equal(Object.isFrozen(beats[0]), true);
  assert.throws(() => {
    beats[0].text = '변조';
  }, TypeError);
});

test('beat text preserves nonblank surrounding whitespace', () => {
  const payload = beatPlanData();
  payload.beats[0].text = '  엄마, 이건 꼭 보세요.  ';
  payload.plan_digest = canonicalContractDigestV1(payload, ['plan_digest']);
  const plan = BeatPlanV1Schema.parse(payload);
  assert.equal(plan.beats[0].text, '  엄마, 이건 꼭 보세요.  ');
});

test('UTC timestamps reject normalized impossible calendar dates', () => {
  const command = commandData();
  command.issued_at_utc = '2026-02-31T01:02:03Z';
  command.command_digest = canonicalContractDigestV1(command, ['command_digest']);
  assert.equal(AresApprovalCommandV1Schema.safeParse(command).success, false);
});

test('safeParse rejects unsafe JSON numbers without throwing', () => {
  for (const value of [-0, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    const payload = scriptPackageData();
    payload.master_sales_script = (
      { unsafe: value } as unknown as typeof payload.master_sales_script
    );
    assert.doesNotThrow(() => ScriptPackageV1Schema.safeParse(payload));
    assert.equal(ScriptPackageV1Schema.safeParse(payload).success, false);
  }
});

test('safeParse never throws for malformed production digests or receipt timestamps', () => {
  const command = commandData('production_plan');
  command.target_profile_digest = 'not-a-digest';
  assert.doesNotThrow(() => AresApprovalCommandV1Schema.safeParse(command));
  assert.equal(AresApprovalCommandV1Schema.safeParse(command).success, false);

  const receipt = receiptData('production_plan');
  receipt.approved_at_utc = 'not-a-timestamp';
  assert.doesNotThrow(() => AresApprovalReceiptV1Schema.safeParse(receipt));
  assert.equal(AresApprovalReceiptV1Schema.safeParse(receipt).success, false);
});

test('pronunciation keys normalize exactly like Python', () => {
  const payload = scriptPackageData();
  payload.pronunciation_overrides = (
    { ' XL ': ' 엑스엘 ' } as unknown as typeof payload.pronunciation_overrides
  );
  payload.package_digest = canonicalContractDigestV1({
    ...payload,
    pronunciation_overrides: { XL: '엑스엘' },
  }, ['package_digest']);
  const parsed = ScriptPackageV1Schema.parse(payload);
  assert.deepEqual({ ...parsed.pronunciation_overrides }, { XL: '엑스엘' });

  const duplicate = scriptPackageData();
  duplicate.pronunciation_overrides = (
    { ' XL ': 'first', XL: 'second' } as unknown as typeof duplicate.pronunciation_overrides
  );
  duplicate.package_digest = canonicalContractDigestV1({
    ...duplicate,
    pronunciation_overrides: { XL: 'second' },
  }, ['package_digest']);
  assert.equal(ScriptPackageV1Schema.safeParse(duplicate).success, false);

  const numericDuplicate = scriptPackageData();
  numericDuplicate.pronunciation_overrides = (
    { ' 1 ': 'first', 1: 'second' } as unknown as typeof numericDuplicate.pronunciation_overrides
  );
  numericDuplicate.package_digest = canonicalContractDigestV1({
    ...numericDuplicate,
    pronunciation_overrides: { 1: 'second' },
  }, ['package_digest']);
  assert.equal(ScriptPackageV1Schema.safeParse(numericDuplicate).success, false);
});

test('JSON contract preserves __proto__ and rejects non-JSON object classes', () => {
  const value = JSON.parse('{"__proto__":{"safe":1},"plain":2}') as Record<string, unknown>;
  assert.equal(
    canonicalContractJsonV1(value),
    '{"__proto__":{"safe":1},"plain":2}',
  );

  const payload = scriptPackageData();
  payload.master_sales_script = value as typeof payload.master_sales_script;
  payload.package_digest = canonicalContractDigestV1(payload, ['package_digest']);
  const parsed = ScriptPackageV1Schema.parse(payload);
  assert.equal(
    Object.prototype.hasOwnProperty.call(parsed.master_sales_script, '__proto__'),
    true,
  );

  for (const invalid of [new Date(), new Map(), new Set(), /xl/]) {
    assert.throws(() => canonicalContractJsonV1({ invalid }), /non-JSON/);
    assert.throws(
      () => canonicalContractDigestV1(invalid as unknown as Record<string, unknown>),
      /non-JSON/,
    );
  }

  const symbolRoot = { [Symbol('xl')]: 1 };
  assert.throws(() => canonicalContractDigestV1(symbolRoot), /symbol/);

  const accessorRoot = Object.defineProperty({}, 'xl', {
    enumerable: true,
    get: () => 1,
  });
  assert.throws(() => canonicalContractDigestV1(accessorRoot), /data property/);
});

test('canonical JSON rejects sparse arrays', () => {
  for (const sparse of [new Array(1), new Array(2)]) {
    assert.throws(() => canonicalContractJsonV1({ sparse }), /sparse array/);
    const payload = scriptPackageData();
    payload.master_sales_script = (
      { sparse } as unknown as typeof payload.master_sales_script
    );
    assert.equal(ScriptPackageV1Schema.safeParse(payload).success, false);
  }

  const accessor = [0];
  Object.defineProperty(accessor, '0', {
    enumerable: true,
    get: () => 1,
  });
  assert.throws(() => canonicalContractJsonV1({ accessor }), /data property/);
});

test('DB UUID, int4, audit identity, year zero, and digest newline fail closed', () => {
  const badUuid = scriptPackageData();
  badUuid.workspace_id = 'not-a-uuid';
  badUuid.package_digest = canonicalContractDigestV1(badUuid, ['package_digest']);
  assert.equal(ScriptPackageV1Schema.safeParse(badUuid).success, false);

  const badRevision = scriptPackageData();
  badRevision.factory_revision = 2_147_483_648;
  badRevision.package_digest = canonicalContractDigestV1(badRevision, ['package_digest']);
  assert.equal(ScriptPackageV1Schema.safeParse(badRevision).success, false);

  const overflowingState = commandData();
  overflowingState.expected_state_revision = 2_147_483_647;
  overflowingState.command_digest = canonicalContractDigestV1(
    overflowingState,
    ['command_digest'],
  );
  assert.equal(
    AresApprovalCommandV1Schema.safeParse(overflowingState).success,
    false,
  );

  const badAudit = receiptData();
  badAudit.transaction_audit_id = 'different-audit-id';
  badAudit.receipt_digest = canonicalContractDigestV1(badAudit, ['receipt_digest']);
  assert.equal(AresApprovalReceiptV1Schema.safeParse(badAudit).success, false);

  const yearZero = commandData();
  yearZero.issued_at_utc = '0000-01-01T00:00:00Z';
  yearZero.command_digest = canonicalContractDigestV1(yearZero, ['command_digest']);
  assert.equal(AresApprovalCommandV1Schema.safeParse(yearZero).success, false);

  assert.throws(
    () => deriveAresG1SubjectDigestV1(
      `${targetProfileDigest}\n`,
      identityLockDigest,
      scriptPackageData().package_digest,
      beatPlanData().plan_digest,
    ),
    /sha256/,
  );
});

test('begin command binds selected candidate and initial CAS state', () => {
  const valid = AresApprovalBeginCommandV1Schema.parse(beginCommandData());
  assert.equal(valid.candidate_id, candidateId);

  const badState = beginCommandData();
  badState.expected_state_revision = 1;
  badState.command_digest = canonicalContractDigestV1(badState, ['command_digest']);
  assert.equal(AresApprovalBeginCommandV1Schema.safeParse(badState).success, false);

  const changedCandidate = beginCommandData();
  changedCandidate.candidate_id = '00000000-0000-4000-8000-000000000099';
  assert.equal(
    AresApprovalBeginCommandV1Schema.safeParse(changedCandidate).success,
    false,
  );
});
