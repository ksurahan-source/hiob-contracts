import assert from 'node:assert/strict';
import test from 'node:test';

import {
  deriveCharacterIdentityBindingDigestV1,
} from './character-identity-v1.js';
import {AresSpeakerSlotV2Schema} from './ares-create-script-v2.js';
import {characterIdentityBindingErrorV1} from './index.js';
import {
  VoiceSpecV1Schema,
  deriveVoiceSpecDigestV1,
} from './voice-spec-v1.js';

const identity = {
  subject_id: 'mom',
  face_id: 'face-mom-1',
  voice_id: 'tc_voice_mom_1',
};

test('character face and voice share the Python parity digest', () => {
  const digest = deriveCharacterIdentityBindingDigestV1(identity);
  assert.equal(
    digest,
    'sha256:04f2d67ea56831625cad4295b63cbf0f8995b458390a25cf7f2ad5a7439b02e3',
  );
  assert.equal(
    characterIdentityBindingErrorV1({
      ...identity,
      identity_binding_digest: digest,
    }),
    null,
  );
  assert.notEqual(
    characterIdentityBindingErrorV1({
      ...identity,
      identity_binding_digest: `sha256:${'0'.repeat(64)}`,
    }),
    null,
  );
});

test('VoiceSpec is bounded and shares the Python parity digest', () => {
  const payload = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: 'mom',
    rhythm: '짧게 끊고 마지막에 한 박자 쉰다',
    vocabulary: ['솔직히', '딱', '은근'],
    forbidden_phrases: ['혁신적인', '여러분 안녕하세요'],
    approved_examples: [
      '솔직히 이건 좀 놀랐어.',
      '딱 한 번만 해보면 감이 와.',
      '은근 이런 데서 차이가 나더라.',
    ],
  };
  const digest = deriveVoiceSpecDigestV1(payload);
  const sealed = {...payload, voice_spec_digest: digest};

  assert.equal(
    digest,
    'sha256:6b3142c797d09a984e8176374fab961fcc70b651cd24c293dca9b0b28d4cf26a',
  );
  assert.equal(VoiceSpecV1Schema.safeParse(sealed).success, true);
  assert.equal(
    deriveVoiceSpecDigestV1(
      Object.fromEntries(
        Object.entries(payload).filter(([key]) => key !== 'contract_version'),
      ),
    ),
    digest,
  );
  const parsed = VoiceSpecV1Schema.parse(sealed);
  assert.equal(Object.isFrozen(parsed), true);
  assert.equal(Object.isFrozen(parsed.approved_examples), true);
  assert.throws(() => {
    (parsed.approved_examples as string[]).push('mutated');
  }, TypeError);
  assert.equal(
    VoiceSpecV1Schema.safeParse({
      ...sealed,
      approved_examples: ['가'.repeat(501), '둘', '셋'],
      voice_spec_digest: deriveVoiceSpecDigestV1({
        ...payload,
        approved_examples: ['가'.repeat(501), '둘', '셋'],
      }),
    }).success,
    false,
  );
  assert.equal(
    VoiceSpecV1Schema.safeParse({
      ...sealed,
      approved_examples: ['하나', '둘'],
      voice_spec_digest: deriveVoiceSpecDigestV1({
        ...payload,
        approved_examples: ['하나', '둘'],
      }),
    }).success,
    false,
  );
});

test('AresSpeakerSlotV2 atomically consumes identity and matching VoiceSpec', () => {
  const voiceSpecBody = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: identity.subject_id,
    rhythm: '짧게 끊고 마지막에 한 박자 쉰다',
    vocabulary: ['솔직히', '딱', '은근'],
    forbidden_phrases: ['혁신적인', '여러분 안녕하세요'],
    approved_examples: [
      '솔직히 이건 좀 놀랐어.',
      '딱 한 번만 해보면 감이 와.',
      '은근 이런 데서 차이가 나더라.',
    ],
  };
  const voiceSpec = {
    ...voiceSpecBody,
    voice_spec_digest: deriveVoiceSpecDigestV1(voiceSpecBody),
  };
  const binding = deriveCharacterIdentityBindingDigestV1(identity);
  const speaker = {
    role: 'lead',
    display_name: '정원이',
    ...identity,
    identity_binding_digest: binding,
    voice_spec: voiceSpec,
  };

  assert.equal(AresSpeakerSlotV2Schema.safeParse(speaker).success, true);
  assert.equal(
    AresSpeakerSlotV2Schema.safeParse({
      ...speaker,
      identity_binding_digest: `sha256:${'0'.repeat(64)}`,
    }).success,
    false,
  );
  assert.equal(
    AresSpeakerSlotV2Schema.safeParse({
      ...speaker,
      voice_spec: {...voiceSpec, subject_id: 'someone-else'},
    }).success,
    false,
  );
});
