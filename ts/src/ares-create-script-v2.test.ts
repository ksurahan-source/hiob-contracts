import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';

import {
  AresCreateScriptRequestV2Schema,
  AresCreateScriptResultV2Schema,
  aresCreateScriptRequestSchemaDigest,
  aresCreateScriptResultSchemaDigest,
} from './ares-create-script-v2.js';
import {deriveVoiceSpecDigestV1} from './voice-spec-v1.js';
import {deriveCharacterIdentityBindingDigestV1} from './character-identity-v1.js';

function digest(value: unknown): string {
  const encoded = JSON.stringify(value);
  return `sha256:${createHash('sha256').update(encoded).digest('hex')}`;
}

const IDENTITY = digest({ identity: 'lead-v3' });
const PRODUCT = digest({ product: 'xl-serum' });

function sampleRequest() {
  const faceId = 'face_mom_1';
  const voiceId = 'tc_voice_1';
  const voiceSpecBody = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: 'mom',
    rhythm: '짧고 솔직하게',
    vocabulary: ['솔직히', '딱'],
    forbidden_phrases: ['혁신적인'],
    approved_examples: [
      '솔직히 이건 좀 놀랐어.',
      '딱 한 번이면 감이 와.',
      '은근 이런 데서 차이가 나.',
    ],
  };
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
          face_id: faceId,
          voice_id: voiceId,
          identity_binding_digest: deriveCharacterIdentityBindingDigestV1({
            subject_id: 'mom',
            face_id: faceId,
            voice_id: voiceId,
          }),
          voice_spec: {
            ...voiceSpecBody,
            voice_spec_digest: deriveVoiceSpecDigestV1(voiceSpecBody),
          },
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

test('request schema accepts sealed authority bundle', () => {
  const parsed = AresCreateScriptRequestV2Schema.parse(sampleRequest());
  assert.equal(parsed.contract_version, 'AresCreateScriptRequest.v2');
  assert.equal(parsed.authority.identity_lock_digest, IDENTITY);
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

test('request schema rejects absent or mismatched speaker identity seal', () => {
  const absent = sampleRequest();
  const absentSpeaker = absent.identity.speakers[0] as Record<string, unknown>;
  absentSpeaker.face_id = null;
  absentSpeaker.voice_id = null;
  absentSpeaker.identity_binding_digest = null;
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(absent).success, false);

  const mismatch = sampleRequest();
  mismatch.identity.speakers[0].identity_binding_digest =
    `sha256:${'0'.repeat(64)}`;
  assert.equal(AresCreateScriptRequestV2Schema.safeParse(mismatch).success, false);
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
