import assert from 'node:assert/strict';
import test from 'node:test';

import { sha256Digest } from './factory/digest.js';
import {
  ParzifalVoiceEnvelopeV1Schema,
  deriveParzifalVoiceEnvelopeDigestV1,
} from './parzifal-voice-envelope-v1.js';

function payload() {
  return {
    contract_version: 'ParzifalVoiceEnvelope.v1' as const,
    workspace_id: 'ws-1',
    run_id: 'run-1',
    subject_id: 'mom',
    voice_id: 'tc_voice_mom_1',
    identity_binding_digest: sha256Digest({ identity: 'mom' }),
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
    'sha256:eb9664e3aa2865e06daaf7c1cb36b90942389fc59704a0aa6a7db62955487345',
  );
  assert.equal(ParzifalVoiceEnvelopeV1Schema.safeParse(envelope).success, true);
  assert.equal(
    ParzifalVoiceEnvelopeV1Schema.safeParse({
      ...envelope,
      voice_id: 'tc_changed',
    }).success,
    false,
  );
});
