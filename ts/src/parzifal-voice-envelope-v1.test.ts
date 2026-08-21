import assert from 'node:assert/strict';
import test from 'node:test';

import { sha256Digest } from './factory/digest.js';
import {
  ParzifalVoiceEnvelopeV1Schema,
  deriveParzifalVoiceEnvelopeDigestV1,
} from './parzifal-voice-envelope-v1.js';
import { deriveCharacterIdentityBindingDigestV1 } from './character-identity-v1.js';

function payload() {
  return {
    contract_version: 'ParzifalVoiceEnvelope.v1' as const,
    workspace_id: 'ws-1',
    run_id: 'run-1',
    subject_id: 'mom',
    face_id: 'face-mom-1',
    voice_id: 'tc_voice_mom_1',
    identity_binding_digest: deriveCharacterIdentityBindingDigestV1({
      subject_id: 'mom',
      face_id: 'face-mom-1',
      voice_id: 'tc_voice_mom_1',
    }),
    voice_spec_digest: sha256Digest({ voice_spec: 'mom' }),
  };
}

test('ParzifalVoiceEnvelopeV1 matches the Python digest contract', () => {
  const body = payload();
  const envelope = {
    ...body,
    envelope_digest: deriveParzifalVoiceEnvelopeDigestV1(body),
  };

  assert.equal(
    envelope.envelope_digest,
    'sha256:f5b3231832c1c93715e1786eb679158494a3ad242f7c2b72069150296c2e49f7',
  );
  assert.equal(ParzifalVoiceEnvelopeV1Schema.safeParse(envelope).success, true);
  assert.equal(
    ParzifalVoiceEnvelopeV1Schema.safeParse({
      ...envelope,
      voice_id: 'tc_changed',
      envelope_digest: deriveParzifalVoiceEnvelopeDigestV1({
        ...envelope,
        voice_id: 'tc_changed',
      }),
    }).success,
    false,
  );
  assert.equal(
    ParzifalVoiceEnvelopeV1Schema.safeParse({
      ...envelope,
      envelope_digest: sha256Digest({ wrong: 'envelope' }),
    }).success,
    false,
  );
});
