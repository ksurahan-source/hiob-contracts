/** Python-authoritative parity and strictness tests for first-customer v2. */
import { createHash } from 'node:crypto';

import {
  CreativeOrderV2Schema,
  EditorApprovalReceiptV2Schema,
  PaidEffectAttemptV2Schema,
  PaidEffectIntentV2Schema,
  ScriptApprovalReceiptV2Schema,
  VerifiedRenderReceiptV2Schema,
  deriveCustomerOrderKeyV2,
  deriveEditorApprovalDigestV2,
  deriveEffectKeyV2,
  editorReceiptBindsScriptApproval,
  paidEffectAttemptBindsIntent,
  scriptReceiptBindsOrder,
  verifiedReceiptBindsEditorApproval,
  verifiedReceiptMatchesOutputBytes,
} from './overnight-first-customer-v2.js';
import { sha256Digest } from './factory/digest.js';

function test(name: string, fn: () => void) {
  try {
    fn();
    console.log(`✓ ${name}`);
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  ${err instanceof Error ? err.message : String(err)}`);
    process.exitCode = 1;
  }
}

function assert(condition: boolean, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

const PAYLOAD = { brief_id: 'brief-1', format: 'reel' };
const ORDER_DIGEST = sha256Digest(PAYLOAD);
const ORDER_KEY = deriveCustomerOrderKeyV2('ws-1', 'EXT-1');
const SCRIPT_DIGEST = 'sha256:f713d17db5aba230e0b9226632b19d9ea6c2e3f7d6e1b1a8ae7e16aab0e1e4a4';
const TIMELINE_DIGEST = 'sha256:94d192b3a326be1f019b71ef13ea5a367ffe939c5e9a88f1b270e53753d9569a';
const MEDIA_DIGEST = 'sha256:721c9525ade2ea8903d343ef25cf68b9bf4ab0aad56bb7b01fbe48d09bc7fcf4';
const POLICY_DIGEST = 'sha256:823412d1eacb67956220e532959f0104603057c88704863ca38e7cd188fda812';
const REQUEST_DIGEST = sha256Digest({ prompt: 'make hero visual' });
const QA_DIGEST = sha256Digest({ checker: 'qa-v2', result: 'PASS' });
const VIDEO_BYTES = Buffer.from('exact-customer-video-bytes', 'utf8');
const VIDEO_SHA256 = createHash('sha256').update(VIDEO_BYTES).digest('hex');

const orderData = () => ({
  contract_version: 'CreativeOrder.v2',
  customer_order_key: ORDER_KEY,
  workspace_id: 'ws-1',
  account_id: 'acct-1',
  brand_id: 'brand-1',
  product_or_listing_id: 'listing-1',
  customer_external_order_id: 'EXT-1',
  canonical_order_payload: { ...PAYLOAD },
  canonical_order_digest: ORDER_DIGEST,
  created_at_utc: '2026-07-16T00:00:00Z',
});

const scriptApprovalData = () => ({
  contract_version: 'ScriptApprovalReceipt.v2',
  approval_receipt_id: 'approval-1',
  customer_order_key: ORDER_KEY,
  workspace_id: 'ws-1',
  approval_kind: 'script',
  approver_account_id: 'acct-1',
  order_digest: ORDER_DIGEST,
  script_digest: SCRIPT_DIGEST,
  policy_digest: POLICY_DIGEST,
  approved_at_utc: '2026-07-16T00:01:00Z',
  transaction_audit_id: 'tx-approval-1',
});

const editorApprovalData = () => ({
  contract_version: 'EditorApprovalReceipt.v2',
  editor_approval_receipt_id: 'editor-approval-1',
  customer_order_key: ORDER_KEY,
  workspace_id: 'ws-1',
  editor_account_id: 'acct-1',
  approved_script_digest: SCRIPT_DIGEST,
  timeline_digest: TIMELINE_DIGEST,
  media_manifest_digest: MEDIA_DIGEST,
  render_policy_digest: POLICY_DIGEST,
  editor_approval_digest: deriveEditorApprovalDigestV2(
    ORDER_KEY, SCRIPT_DIGEST, TIMELINE_DIGEST, MEDIA_DIGEST, POLICY_DIGEST,
  ),
  approved_at_utc: '2026-07-16T00:02:00Z',
});

const effectIntentData = () => ({
  contract_version: 'PaidEffectIntent.v2',
  effect_key: deriveEffectKeyV2(ORDER_KEY, SCRIPT_DIGEST, 'visual', 'hero'),
  customer_order_key: ORDER_KEY,
  workspace_id: 'ws-1',
  approved_script_digest: SCRIPT_DIGEST,
  effect_kind: 'visual',
  asset_slot: 'hero',
  request_digest: REQUEST_DIGEST,
  spend_ceiling: 2.5,
  currency: 'USD',
  created_at_utc: '2026-07-16T00:03:00Z',
});

const effectAttemptData = () => ({
  contract_version: 'PaidEffectAttempt.v2',
  effect_key: effectIntentData().effect_key,
  customer_order_key: ORDER_KEY,
  workspace_id: 'ws-1',
  approved_script_digest: SCRIPT_DIGEST,
  effect_kind: 'visual',
  asset_slot: 'hero',
  attempt_id: 'attempt-1',
  attempt_number: 1,
  provider: 'fal',
  provider_idempotency_key: 'provider-key-1',
  provider_job_id: null,
  state: 'CLAIMED',
  lease_owner: 'worker-1',
  lease_expires_at_utc: '2026-07-16T00:08:00Z',
  fencing_token: 1,
  request_digest: REQUEST_DIGEST,
  spend_ceiling: 2.5,
  currency: 'USD',
  response_digest: null,
  cost_currency: null,
  cost_amount: null,
  last_reconciled_at_utc: null,
  created_at_utc: '2026-07-16T00:03:00Z',
  updated_at_utc: '2026-07-16T00:03:00Z',
});

const verifiedRenderData = () => ({
  contract_version: 'VerifiedRenderReceipt.v2',
  verified_render_receipt_id: 'render-receipt-1',
  customer_order_key: ORDER_KEY,
  workspace_id: 'ws-1',
  run_id: 'run-1',
  render_job_id: 'render-job-1',
  render_effect_key: deriveEffectKeyV2(ORDER_KEY, SCRIPT_DIGEST, 'render', 'final'),
  editor_approval_digest: editorApprovalData().editor_approval_digest,
  output_url: 'https://cdn.hi-ob.com/customer/final.mp4',
  storage_key: 'customer/final.mp4',
  output_sha256: VIDEO_SHA256,
  output_bytes: VIDEO_BYTES.length,
  duration_ms: 15000,
  video_codec: 'h264',
  audio_codec: 'aac',
  mechanical_checker_version: 'mechanical.v2',
  qa_checker_version: 'qa.v2',
  qa_verdict: 'PASS',
  qa_evidence_digest: QA_DIGEST,
  source_revisions: { 'hiob-star': 'abc123' },
  deployed_revisions: { modal: 'v616' },
  created_at_utc: '2026-07-16T00:10:00Z',
  transaction_audit_id: 'tx-render-1',
});

const strictCases = [
  [CreativeOrderV2Schema, orderData],
  [ScriptApprovalReceiptV2Schema, scriptApprovalData],
  [EditorApprovalReceiptV2Schema, editorApprovalData],
  [PaidEffectIntentV2Schema, effectIntentData],
  [PaidEffectAttemptV2Schema, effectAttemptData],
  [VerifiedRenderReceiptV2Schema, verifiedRenderData],
] as const;

test('v2 schemas accept exact objects and reject missing/extra/wrong-type/version', () => {
  for (const [schema, factory] of strictCases) {
    const value = factory() as Record<string, unknown>;
    assert(schema.safeParse(value).success, `${String(value.contract_version)} should parse`);

    const missing = { ...value };
    delete missing.workspace_id;
    assert(!schema.safeParse(missing).success, `${String(value.contract_version)} missing field must fail`);

    assert(!schema.safeParse({ ...value, unsealed_extra: true }).success, 'extra field must fail');
    assert(!schema.safeParse({ ...value, workspace_id: 123 }).success, 'wrong type must fail');
    assert(
      !schema.safeParse({ ...value, contract_version: String(value.contract_version).replace('.v2', '.v1') }).success,
      'wrong schema version must fail',
    );
  }
});

test('Python/TypeScript stable identity parity excludes runtime attempt identity', () => {
  assert(ORDER_DIGEST === 'sha256:235052d5f6e3ceb0cabdb7144e651c1c548eff5a3d896b9ab1975c4075c2d842', 'order digest parity');
  assert(ORDER_KEY === 'de0148e8df681a168f9bccf19c155e6f2f69d092377221cd23e66b8c4b23758a', 'order key parity');
  assert(effectIntentData().effect_key === '49f64ea6899239360a7b8b5e92d6c12fd40e3519d34c7d38e080a414d3675968', 'effect key parity');

  const changedPayload = { brief_id: 'brief-1', format: 'story' };
  const changedDigest = sha256Digest(changedPayload);
  assert(changedDigest !== ORDER_DIGEST, 'changed payload changes only the conflict digest');
  assert(deriveCustomerOrderKeyV2('ws-1', 'EXT-1') === ORDER_KEY, 'same external identity keeps one key');
  assert(CreativeOrderV2Schema.safeParse({
    ...orderData(), canonical_order_payload: changedPayload, canonical_order_digest: changedDigest,
  }).success, 'individual candidate is valid; persistence compares stored digest for conflict');

  for (const forbidden of ['run_id', 'attempt_id']) {
    const payload = { ...PAYLOAD, [forbidden]: 'ephemeral' };
    const digest = sha256Digest(payload);
    const bad = {
      ...orderData(),
      canonical_order_payload: payload,
      canonical_order_digest: digest,
      customer_order_key: deriveCustomerOrderKeyV2('ws-1', 'EXT-1'),
    };
    assert(!CreativeOrderV2Schema.safeParse(bad).success, `${forbidden} must not enter order identity`);
  }
});

test('approval receipts bind exact digests and editor receipt forbids future output', () => {
  const order = CreativeOrderV2Schema.parse(orderData());
  const script = ScriptApprovalReceiptV2Schema.parse(scriptApprovalData());
  const editor = EditorApprovalReceiptV2Schema.parse(editorApprovalData());
  assert(scriptReceiptBindsOrder(script, order, SCRIPT_DIGEST, POLICY_DIGEST), 'script receipt binds');
  assert(!scriptReceiptBindsOrder(script, order, TIMELINE_DIGEST, POLICY_DIGEST), 'script mismatch denied');
  assert(editorReceiptBindsScriptApproval(editor, script), 'editor receipt binds');
  assert(editor.editor_approval_digest === 'sha256:fbb0a245357cbcd3cbccaec9d513a0b202bf07f5814b2f1bcf86cc48fbd440d0', 'editor parity');
  assert(!EditorApprovalReceiptV2Schema.safeParse({ ...editorApprovalData(), output_sha256: VIDEO_SHA256 }).success, 'future output must be extra');
  assert(!ScriptApprovalReceiptV2Schema.safeParse({ ...scriptApprovalData(), approval_kind: 'editor' }).success, 'wrong approval kind');
});

test('paid effect intent and attempt share stable identity and enforce state enums', () => {
  const intent = PaidEffectIntentV2Schema.parse(effectIntentData());
  const attempt = PaidEffectAttemptV2Schema.parse(effectAttemptData());
  assert(paidEffectAttemptBindsIntent(attempt, intent), 'attempt binds intent');
  assert(!PaidEffectIntentV2Schema.safeParse({ ...effectIntentData(), effect_kind: 'unknown' }).success, 'effect enum');
  for (const badCap of [0, -0.01]) {
    assert(!PaidEffectIntentV2Schema.safeParse({ ...effectIntentData(), spend_ceiling: badCap }).success, 'positive spend ceiling');
  }
  assert(!PaidEffectIntentV2Schema.safeParse({ ...effectIntentData(), currency: 'usd' }).success, 'three-letter uppercase currency');
  assert(!PaidEffectAttemptV2Schema.safeParse({ ...effectAttemptData(), state: 'UNKNOWN' }).success, 'state enum');
  assert(!PaidEffectAttemptV2Schema.safeParse({ ...effectAttemptData(), state: 'PROVIDER_STARTED' }).success, 'started needs job id');
  assert(!PaidEffectAttemptV2Schema.safeParse({ ...effectAttemptData(), state: 'SUCCEEDED', provider_job_id: 'job-1' }).success, 'success needs response');
  assert(!PaidEffectAttemptV2Schema.safeParse({ ...effectAttemptData(), cost_currency: 'USD', cost_amount: 3 }).success, 'cost cannot exceed signed ceiling');

  const retry = PaidEffectAttemptV2Schema.parse({
    ...effectAttemptData(), attempt_id: 'attempt-2', attempt_number: 2,
    provider: 'piapi', provider_idempotency_key: 'provider-key-2', fencing_token: 2,
  });
  assert(retry.effect_key === intent.effect_key, 'attempt/provider do not change effect key');
});

test('verified receipt requires QA PASS, exact lowercase sha, and exact editor binding', () => {
  const editor = EditorApprovalReceiptV2Schema.parse(editorApprovalData());
  const receipt = VerifiedRenderReceiptV2Schema.parse(verifiedRenderData());
  assert(verifiedReceiptBindsEditorApproval(receipt, editor), 'receipt binds editor approval');
  assert(verifiedReceiptMatchesOutputBytes(receipt, VIDEO_BYTES), 'exact bytes match');
  assert(!verifiedReceiptMatchesOutputBytes(receipt, Buffer.from('different')), 'different bytes fail');
  assert(!VerifiedRenderReceiptV2Schema.safeParse({ ...verifiedRenderData(), qa_verdict: 'FAIL' }).success, 'FAIL is not a verified receipt');
  for (const badSha of ['A'.repeat(64), 'a'.repeat(63), `sha256:${'a'.repeat(64)}`]) {
    assert(!VerifiedRenderReceiptV2Schema.safeParse({ ...verifiedRenderData(), output_sha256: badSha }).success, 'bad sha shape');
  }
});
