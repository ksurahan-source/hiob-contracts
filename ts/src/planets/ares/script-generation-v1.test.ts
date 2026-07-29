import assert from 'node:assert/strict';
import test from 'node:test';

import * as PublicContracts from '../../index.js';
import {
  AresScriptGenerationInputV1Schema,
  deriveAresScriptGenerationInputDigestV1,
} from './script-generation-v1.js';
import {
  deriveCharacterIdentityBindingDigestV1,
} from '../../character-identity-v1.js';
import { deriveVoiceSpecDigestV1 } from '../../voice-spec-v1.js';

function payload(): Record<string, any> {
  const voice: Record<string, any> = {
    contract_version: 'VoiceSpec.v1',
    subject_id: 'lead',
    rhythm: '짧고 단정하게',
    vocabulary: ['진짜'],
    forbidden_phrases: ['무조건'],
    approved_examples: [
      '먼저 확인해 보세요.',
      '필요한 것만 담았습니다.',
      '지금 비교해 보세요.',
    ],
  };
  voice.voice_spec_digest = deriveVoiceSpecDigestV1(voice);
  const body = {
    contract_version: 'AresScriptGenerationInput.v1',
    workspace_id: '00000000-0000-4000-8000-000000000001',
    run_id: '00000000-0000-4000-8000-000000000002',
    script_revision_id: '00000000-0000-4000-8000-000000000003',
    plan_revision_id: '00000000-0000-4000-8000-000000000004',
    factory_revision: 7,
    character_lock: {
      persona_id: 'lead',
      face_id: 'face-lead-v1',
      voice_id: 'voice-lead-v1',
      identity_binding_digest: deriveCharacterIdentityBindingDigestV1({
        subject_id: 'lead',
        face_id: 'face-lead-v1',
        voice_id: 'voice-lead-v1',
      }),
    },
    voice_spec: voice,
    current_character: '차분하고 정확한 전문가',
    conflict: '과장 없이 차이를 증명한다',
    adjacent_beat_summaries: ['문제를 짧게 제시'],
    memories: [
      {
        text: '과장된 말투를 싫어함',
        provenance: 'approved_edit:rev-1',
      },
    ],
  };
  return {
    ...body,
    generation_input_digest:
      deriveAresScriptGenerationInputDigestV1(body),
  };
}

test('Ares generation output is exported from one planet namespace', () => {
  assert.equal(
    PublicContracts.AresScriptGenerationInputV1Schema,
    AresScriptGenerationInputV1Schema,
  );
});

test('Ares generation output validates exact bounded provider input', () => {
  const parsed = AresScriptGenerationInputV1Schema.parse(payload());
  assert.equal(parsed.character_lock.face_id, 'face-lead-v1');
  assert.equal(
    parsed.voice_spec.subject_id,
    parsed.character_lock.persona_id,
  );
  assert.deepEqual(parsed.adjacent_beat_summaries, ['문제를 짧게 제시']);
  assert.equal(Object.isFrozen(parsed), true);
});

test('Ares generation output rejects drift and extra authority', () => {
  const drift = payload();
  drift.current_character = 'changed';
  assert.equal(
    AresScriptGenerationInputV1Schema.safeParse(drift).success,
    false,
  );

  const extra = { ...payload(), production_plan: { unsealed: true } };
  assert.equal(
    AresScriptGenerationInputV1Schema.safeParse(extra).success,
    false,
  );
});

test('Ares generation output never synthesizes missing wire fields', () => {
  for (const missing of [
    'adjacent_beat_summaries',
    'memories',
    'voice_spec.contract_version',
  ]) {
    const value = payload();
    if (missing !== 'voice_spec.contract_version') {
      value[missing] = [];
    }
    const unsigned = { ...value };
    delete unsigned.generation_input_digest;
    value.generation_input_digest =
      deriveAresScriptGenerationInputDigestV1(unsigned);
    if (missing === 'voice_spec.contract_version') {
      delete value.voice_spec.contract_version;
    } else {
      delete value[missing];
    }
    assert.equal(
      AresScriptGenerationInputV1Schema.safeParse(value).success,
      false,
    );
  }
});

test('Ares generation Unicode bounds count code points like Python', () => {
  const value = payload();
  value.current_character = '😀'.repeat(500);
  const unsigned = { ...value };
  delete unsigned.generation_input_digest;
  value.generation_input_digest =
    deriveAresScriptGenerationInputDigestV1(unsigned);

  assert.equal(
    AresScriptGenerationInputV1Schema.safeParse(value).success,
    true,
  );
});

test('Ares generation rejects unpaired Unicode before hashing', () => {
  const value = payload();
  value.current_character = '\ud800';
  value.generation_input_digest = `sha256:${'0'.repeat(64)}`;
  const unsigned = { ...value };
  delete unsigned.generation_input_digest;

  assert.throws(
    () => deriveAresScriptGenerationInputDigestV1(unsigned),
    /Unicode scalar/,
  );
  assert.equal(
    AresScriptGenerationInputV1Schema.safeParse(value).success,
    false,
  );
});

test('Ares generation uses the frozen nonblank Unicode parity set', () => {
  for (const [text, accepted] of [
    ['\u0085', true],
    ['\uFEFF', false],
  ] as const) {
    const value = payload();
    value.current_character = text;
    const unsigned = { ...value };
    delete unsigned.generation_input_digest;
    value.generation_input_digest =
      deriveAresScriptGenerationInputDigestV1(unsigned);

    assert.equal(
      AresScriptGenerationInputV1Schema.safeParse(value).success,
      accepted,
    );
  }
});

test('Ares generation accepts JSON integer lexical parity', () => {
  for (const token of ['7.0', '7e0']) {
    const value = payload();
    const raw = JSON.stringify(value).replace(
      '"factory_revision":7',
      `"factory_revision":${token}`,
    );
    const parsed = AresScriptGenerationInputV1Schema.parse(JSON.parse(raw));
    assert.equal(parsed.factory_revision, 7);
  }
});

test('Ares generation digest matches the fixed Python vector', () => {
  const value = payload();
  assert.equal(
    value.generation_input_digest,
    'sha256:43b376a18dbdb3fda7035ce06bd36188dff58191a2f9cdb6edf1078a6aa21f3f',
  );
});
