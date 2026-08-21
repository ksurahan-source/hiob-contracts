import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';

import {
  AresCreateScriptRequestV2Schema,
  AresCreateScriptResultV2Schema,
  AresCreativeConstraintsV2Schema,
  aresCreateScriptRequestSchemaDigest,
  aresCreateScriptResultSchemaDigest,
} from './ares-create-script-v2.js';
import { deriveCharacterIdentityBindingDigestV1 } from './character-identity-v1.js';
import { deriveVoiceSpecDigestV1 } from './voice-spec-v1.js';

function digest(value: unknown): string {
  const encoded = JSON.stringify(value);
  return `sha256:${createHash('sha256').update(encoded).digest('hex')}`;
}

const IDENTITY = digest({ identity: 'lead-v3' });
const PRODUCT = digest({ product: 'xl-serum' });

function sampleRequest() {
  const targetInput = {
    brand_slug: 'viewok',
    protagonist_name: '정원이',
    target_pain: '수영 공포',
  };
  return {
    contract_version: 'AresCreateScriptRequest.v2' as const,
    authority: {
      accepted_p2a_receipt: {
        receipt_id: 'rcpt-p2a-v2-1',
        edge_id: 'p2a',
        run_id: 'run-v2-1',
        factory_revision: 1,
        workspace_id: 'ws-v2-1',
        source_output_digests: [IDENTITY],
        target_contract: {
          name: 'AresScriptInput',
          version: 'v1',
          schema_digest: digest({ schema: 'ares_script_input.v1' }),
        },
        decision: 'accepted' as const,
        target_input: targetInput,
        target_input_digest: digest(targetInput),
        mapper: {
          planet: 'karma' as const,
          node_id: 'karma.edge.refine',
          revision: 'r1',
          policy_digest: digest({ policy: 'p2a.v1' }),
        },
        created_at: '2026-07-25T00:00:00Z',
      },
      identity_lock_digest: IDENTITY,
      product_truth_digest: PRODUCT,
    },
    identity: {
      identity_lock_digest: IDENTITY,
      cast_sheet_digest: digest({ cast: 'sheet-1' }),
      speakers: [
        {
          role: 'lead',
          subject_id: 'mom',
          display_name: '정원이',
        },
      ],
      locale: 'ko',
    },
    product_facts: {
      product_truth_digest: PRODUCT,
      brand_slug: 'viewok',
      brand_display_name: '뷰옥',
      product_name: 'XL 세럼',
    },
    evidence_and_claims: {
      evidence_bundle_digest: digest({ evidence: 'bundle-1' }),
      claims: [{ claim_id: 'c1', text: '빠른 흡수' }],
    },
    hook_directive: {
      directive_digest: digest({ hook: 'gossip-v1' }),
      archetype_id: 'gossip_reveal',
    },
    creative_constraints: {
      n_beats: 2,
    },
  };
}

function sampleVoiceSpec(subjectId = 'mom') {
  const value = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: subjectId,
    rhythm: 'short and quick',
    vocabulary: ['근데'],
    forbidden_phrases: ['혁신적인'],
    approved_examples: ['첫 문장', '둘째 문장', '셋째 문장'],
  };
  return { ...value, voice_spec_digest: deriveVoiceSpecDigestV1(value) };
}

function sampleResult() {
  const packageDigest = digest({ package: 'v2' });
  return {
    contract_version: 'AresCreateScriptResult.v2' as const,
    status: 'ok' as const,
    script_package: {
      contract_version: 'AresScriptPackage.v2' as const,
      master_sales_script: { title: 'one-beat script' },
      voice_script: [{ beat_index: 0, text: 'voice' }],
      caption_script: [{ beat_index: 0, text: 'caption' }],
      pronunciation_overrides: {},
      package_digest: packageDigest,
    },
    beat_plan: {
      contract_version: 'AresBeatPlan.v2' as const,
      script_package_digest: packageDigest,
      beats: [{
        beat_index: 0,
        text: 'voice',
        caption: 'caption',
        scene_direction: { shot: '', subject: '', setting: '', overlay: '' },
      }],
      beat_role_intents: [],
      plan_digest: digest({ plan: 'v2' }),
    },
    quality_findings: [],
    provenance: {
      producer: 'ares' as const,
      contract_version: 'AresCreateScriptResult.v2' as const,
      request_content_digest: digest({ request: 'v2' }),
    },
    usage: {},
    content_digest: digest({ result: 'v2' }),
    block_reason: null,
  };
}

test('request schema accepts sealed authority bundle', () => {
  const parsed = AresCreateScriptRequestV2Schema.parse(sampleRequest());
  assert.equal(parsed.contract_version, 'AresCreateScriptRequest.v2');
  assert.equal(parsed.authority.identity_lock_digest, IDENTITY);
});

test('creative constraints seal optional target duration within 1..180 seconds', () => {
  for (const targetDurationSec of [1, 4, 180]) {
    assert.equal(
      AresCreativeConstraintsV2Schema.parse({
        n_beats: 1,
        target_duration_sec: targetDurationSec,
      }).target_duration_sec,
      targetDurationSec,
    );
  }
  for (const targetDurationSec of [0, 181, 4.5, '4', true]) {
    assert.equal(
      AresCreativeConstraintsV2Schema.safeParse({
        n_beats: 1,
        target_duration_sec: targetDurationSec,
      }).success,
      false,
    );
  }
});

test('speaker atomically binds face and voice', () => {
  const request = sampleRequest();
  const speaker = request.identity.speakers[0] as Record<string, unknown>;
  speaker.face_id = 'face-mom-1';
  speaker.voice_id = 'voice-mom-1';
  speaker.identity_binding_digest = deriveCharacterIdentityBindingDigestV1({
    subject_id: 'mom',
    face_id: 'face-mom-1',
    voice_id: 'voice-mom-1',
  });
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(request).success, true);

  delete speaker.identity_binding_digest;
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(request).success, false);
});

test('speaker rejects a mismatched face and voice binding', () => {
  const request = sampleRequest();
  const speaker = request.identity.speakers[0] as Record<string, unknown>;
  speaker.face_id = 'face-mom-1';
  speaker.voice_id = 'voice-mom-1';
  speaker.identity_binding_digest = digest({ wrong: true });
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(request).success, false);
});

test('identity accepts one matching VoiceSpec and rejects subject drift', () => {
  const request = sampleRequest();
  const identity = request.identity as Record<string, any>;
  identity.voice_spec = sampleVoiceSpec();
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(request).success, true);
  identity.voice_spec.subject_id = 'other';
  identity.voice_spec.voice_spec_digest = deriveVoiceSpecDigestV1(
    identity.voice_spec,
  );
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(request).success, false);
});

test('request schema rejects job_status extra field', () => {
  const bad = { ...sampleRequest(), job_status: 'running' };
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(bad).success, false);
});

test('request schema rejects blocked receipt', () => {
  const body = sampleRequest() as Record<string, unknown>;
  const authority = body.authority as Record<string, unknown>;
  const receipt = {
    ...(authority.accepted_p2a_receipt as Record<string, unknown>),
    decision: 'blocked',
    target_input: null,
    target_input_digest: null,
  };
  authority.accepted_p2a_receipt = receipt;
  body.authority = authority;
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(body).success, false);
});

test('result schema rejects package on blocked status', () => {
  const body = {
    contract_version: 'AresCreateScriptResult.v2' as const,
    status: 'blocked' as const,
    script_package: {
      contract_version: 'AresScriptPackage.v2' as const,
      master_sales_script: { title: 'x' },
      voice_script: [{ beat_index: 0, text: 'hi' }],
      caption_script: [{ beat_index: 0, text: 'hi' }],
      pronunciation_overrides: {},
      package_digest: digest({ p: 1 }),
    },
    beat_plan: null,
    quality_findings: [],
    provenance: {
      producer: 'ares' as const,
      contract_version: 'AresCreateScriptResult.v2' as const,
      request_content_digest: digest({ r: 1 }),
    },
    usage: {},
    content_digest: digest({ c: 1 }),
    block_reason: 'missing authority',
  };
  assert.equal(AresCreateScriptResultV2Schema.safeParse(body).success, false);
});

test('schema digests are stable and distinct', () => {
  const a = aresCreateScriptRequestSchemaDigest();
  const b = aresCreateScriptResultSchemaDigest();
  assert.match(a, /^sha256:[0-9a-f]{64}$/);
  assert.match(b, /^sha256:[0-9a-f]{64}$/);
  assert.equal(a, aresCreateScriptRequestSchemaDigest());
  assert.notEqual(a, b);
});

test('authority, identity, and product bindings reject each independent drift', () => {
  const mutations: Array<(value: ReturnType<typeof sampleRequest>) => void> = [
    value => { value.authority.accepted_p2a_receipt.edge_id = 'j2p'; },
    value => { value.authority.accepted_p2a_receipt.target_contract.name = 'OtherInput'; },
    value => { value.authority.accepted_p2a_receipt.source_output_digests = [digest({ other: 'identity' })]; },
    value => { value.identity.identity_lock_digest = digest({ other: 'identity' }); },
    value => { value.product_facts.product_truth_digest = digest({ other: 'product' }); },
  ];
  for (const mutate of mutations) {
    const request = sampleRequest();
    mutate(request);
    assert.equal(AresCreateScriptRequestV2Schema.safeParse(request).success, false);
  }
});

test('identity rejects duplicate roles and a VoiceSpec spanning multiple speakers', () => {
  const duplicateRoles = sampleRequest();
  duplicateRoles.identity.speakers.push({
    role: 'lead',
    subject_id: 'guest',
    display_name: 'Guest',
  });
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(duplicateRoles).success, false);

  const multiSpeakerVoice = sampleRequest();
  multiSpeakerVoice.identity.speakers.push({
    role: 'guest',
    subject_id: 'guest',
    display_name: 'Guest',
  });
  (multiSpeakerVoice.identity as Record<string, unknown>).voice_spec = sampleVoiceSpec();
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(multiSpeakerVoice).success, false);
});

test('result terminal states enforce package, plan, binding, and block reason', () => {
  const valid = sampleResult();
  assert.equal(AresCreateScriptResultV2Schema.safeParse(valid).success, true);
  assert.equal(AresCreateScriptResultV2Schema.safeParse({
    ...valid,
    script_package: null,
    beat_plan: null,
  }).success, false);
  assert.equal(AresCreateScriptResultV2Schema.safeParse({
    ...valid,
    beat_plan: { ...valid.beat_plan, script_package_digest: digest({ other: 'package' }) },
  }).success, false);
  assert.equal(AresCreateScriptResultV2Schema.safeParse({
    ...valid,
    block_reason: 'must be absent',
  }).success, false);

  const blocked = {
    ...valid,
    status: 'blocked' as const,
    script_package: null,
    beat_plan: null,
    block_reason: 'authority unavailable',
  };
  assert.equal(AresCreateScriptResultV2Schema.safeParse(blocked).success, true);
  assert.equal(AresCreateScriptResultV2Schema.safeParse({
    ...blocked,
    block_reason: null,
  }).success, false);
});
