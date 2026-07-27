import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AresIdentitySealedV2Schema,
  AresSpeakerSlotV2Schema,
  aresCreateScriptRequestSchemaDescriptorV2,
  aresCreateScriptRequestSchemaDigest,
} from './ares-create-script-v2.js';
import {
  aresCreateScriptRequestV3SchemaDescriptor,
  aresCreateScriptRequestV3SchemaDigest,
} from './ares-create-script-v3.js';
import { sha256Digest } from './factory/digest.js';
import {
  ParzifalVoiceEnvelopeV1Schema,
  deriveParzifalVoiceEnvelopeDigestV1,
} from './parzifal-voice-envelope-v1.js';
import {
  VoiceSpecV1Schema,
  deriveVoiceSpecDigestV1,
} from './voice-spec-v1.js';

const speakerFields = [
  'display_name',
  'face_id',
  'identity_binding_digest',
  'role',
  'subject_id',
  'voice_id',
];
const identityInvariants = [
  'speaker_face_voice_atomic_binding',
  'speaker_roles_unique',
  'voice_spec_requires_exactly_one_speaker',
  'voice_spec_subject_matches_speaker',
];

test('V2 and V3 descriptors bind speaker fields and identity invariants', () => {
  const v2 = aresCreateScriptRequestSchemaDescriptorV2();
  const v3 = aresCreateScriptRequestV3SchemaDescriptor();

  assert.deepEqual(v2.speaker_fields, speakerFields);
  assert.deepEqual(v3.speaker_fields, speakerFields);
  assert.deepEqual(v2.identity_invariants, identityInvariants);
  assert.deepEqual(v3.identity_invariants, identityInvariants);
  assert.equal(aresCreateScriptRequestSchemaDigest(), sha256Digest(v2));
  assert.equal(aresCreateScriptRequestV3SchemaDigest(), sha256Digest(v3));
  assert.equal(
    aresCreateScriptRequestSchemaDigest(),
    'sha256:85c65dc8b323daecbd5abc8e982fec7460c574abc7f3267e4f0bfafbc4c36a6d',
  );
  assert.equal(
    aresCreateScriptRequestV3SchemaDigest(),
    'sha256:e3043b68c15ecdc9c560912067c8b7c6b7f25cdce3bce6dfb0facf20204be8b6',
  );
});

test('V2 rejects duplicate roles without requiring a VoiceSpec', () => {
  const speaker = {
    role: 'lead',
    subject_id: 'mom',
    display_name: '엄마',
  };
  assert.equal(
    AresIdentitySealedV2Schema.safeParse({
      identity_lock_digest: sha256Digest({ identity: 'mom' }),
      cast_sheet_digest: sha256Digest({ cast: 'mom' }),
      speakers: [speaker, { ...speaker, subject_id: 'other' }],
    }).success,
    false,
  );
});

test('NonBlank schemas validate whitespace without trimming bytes', () => {
  const speaker = AresSpeakerSlotV2Schema.parse({
    role: ' lead ',
    subject_id: ' mom ',
    display_name: ' 엄마 ',
  });
  assert.equal(speaker.subject_id, ' mom ');

  const voiceSpecPayload = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: ' mom ',
    rhythm: ' 짧게 ',
    vocabulary: [' 딱 '],
    forbidden_phrases: [],
    approved_examples: [' 하나 ', ' 둘 ', ' 셋 '],
  };
  const voiceSpec = VoiceSpecV1Schema.parse({
    ...voiceSpecPayload,
    voice_spec_digest: deriveVoiceSpecDigestV1(voiceSpecPayload),
  });
  assert.equal(voiceSpec.rhythm, ' 짧게 ');

  const envelopePayload = {
    contract_version: 'ParzifalVoiceEnvelope.v1' as const,
    workspace_id: ' ws-1 ',
    run_id: ' run-1 ',
    subject_id: ' mom ',
    face_id: ' face-1 ',
    voice_id: ' voice-1 ',
    identity_binding_digest: sha256Digest({
      contract_version: 'CharacterIdentityBinding.v1',
      subject_id: 'mom',
      face_id: 'face-1',
      voice_id: 'voice-1',
    }),
    voice_spec_digest: voiceSpec.voice_spec_digest,
  };
  const envelope = ParzifalVoiceEnvelopeV1Schema.parse({
    ...envelopePayload,
    envelope_digest: deriveParzifalVoiceEnvelopeDigestV1(envelopePayload),
  });
  assert.equal(envelope.workspace_id, ' ws-1 ');
});
