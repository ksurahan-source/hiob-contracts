import assert from 'node:assert/strict';
import test from 'node:test';

import { VoiceSpecV1Schema, deriveVoiceSpecDigestV1 } from './voice-spec-v1.js';

test('VoiceSpecV1 is bounded and digest sealed', () => {
  const payload = {
    contract_version: 'VoiceSpec.v1' as const,
    subject_id: 'mom',
    rhythm: '짧고 빠른 호흡',
    vocabulary: ['근데', '솔직히'],
    forbidden_phrases: ['혁신적인'],
    approved_examples: ['첫 문장입니다', '둘째 문장입니다', '셋째 문장입니다'],
  };
  const sealed = {
    ...payload,
    voice_spec_digest: deriveVoiceSpecDigestV1(payload),
  };
  assert.equal(VoiceSpecV1Schema.safeParse(sealed).success, true);
  assert.equal(
    VoiceSpecV1Schema.safeParse({
      ...sealed,
      approved_examples: [...sealed.approved_examples, '넷', '다섯', '여섯'],
    }).success,
    false,
  );
  assert.equal(
    VoiceSpecV1Schema.safeParse({ ...sealed, voice_spec_digest: deriveVoiceSpecDigestV1({ wrong: true }) })
      .success,
    false,
  );
  assert.equal(
    VoiceSpecV1Schema.safeParse({
      ...sealed,
      approved_examples: ['가'.repeat(501), '둘째 문장입니다', '셋째 문장입니다'],
      voice_spec_digest: deriveVoiceSpecDigestV1({
        ...payload,
        approved_examples: ['가'.repeat(501), '둘째 문장입니다', '셋째 문장입니다'],
      }),
    }).success,
    false,
  );
});
