import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ParzifalIdentityAuthorityMaterialV1Schema,
  ParzifalIdentityAuthorityRecordV1Schema,
  ParzifalIdentityRecordRefV1Schema,
  deriveParzifalIdentityAuthorityMaterialPayloadDigestV1,
  deriveParzifalIdentityAuthorityRecordDigestV1,
} from './parzifal-identity-authority-v1.js';
import { deriveCharacterIdentityBindingDigestV1 } from './character-identity-v1.js';
import { sha256Digest } from './factory/digest.js';
import { deriveVoiceSpecDigestV1 } from './voice-spec-v1.js';

function recordBody(): Record<string, unknown> {
  return {
    id: 'parzifal-identity-1',
    version: 4,
    workspace_id: 'ws-1',
    run_id: 'run-1',
    status: 'sealed',
    emitted_at: '2026-07-26T01:02:03+00:00',
    identity_lock: {
      identity_source: 'parzifal',
      cast_status: 'sealed',
    },
    master_sheet: {
      identity: { name: '수영하는 엄마' },
      characters: {
        mom: {
          persona_id: 'mom',
          display_name: '수영하는 엄마',
          face_id: 'face-mom-1',
        },
      },
    },
    cast_sheets: {
      status: 'sealed',
      by_id: {
        mom: {
          kind: 'lead_link',
          links_to: 'parzifal_master_sheet',
          persona_id: 'mom',
          role: 'lead',
          on_screen: true,
          voice_id: 'voice-mom-1',
        },
      },
    },
  };
}

function record(): Record<string, unknown> {
  const body = recordBody();
  return {
    ...body,
    digest: deriveParzifalIdentityAuthorityRecordDigestV1(body),
  };
}

function sealedPayload(): Record<string, unknown> {
  return {
    identity_lock_digest: sha256Digest({ identity_lock: 'mom' }),
    cast_sheet_digest: sha256Digest({ cast_sheet: 'mom' }),
    speakers: [{
      role: 'lead',
      subject_id: 'mom',
      display_name: '수영하는 엄마',
      face_id: 'face-mom-1',
      voice_id: 'voice-mom-1',
      identity_binding_digest: deriveCharacterIdentityBindingDigestV1({
        subject_id: 'mom',
        face_id: 'face-mom-1',
        voice_id: 'voice-mom-1',
      }),
    }],
  };
}

function material(): Record<string, unknown> {
  const sealed_payload = sealedPayload();
  return {
    artifact_type: 'identity_lock',
    artifact_digest: sealed_payload.identity_lock_digest,
    payload_digest: deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(
      sealed_payload,
    ),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload,
  };
}

class NonJsonDocument {
  value = 'not-json';
}

class NonJsonVoiceSpec {
  contract_version: 'VoiceSpec.v1' = 'VoiceSpec.v1';
  subject_id = 'mom';
  rhythm = 'steady';
  vocabulary: string[] = [];
  forbidden_phrases: string[] = [];
  approved_examples = ['one', 'two', 'three'];
  voice_spec_digest: string;

  constructor() {
    this.voice_spec_digest = deriveVoiceSpecDigestV1(
      this as unknown as Record<string, unknown>,
    );
  }
}

class ForgingArray<T> extends Array<T> {
  static get [Symbol.species](): ArrayConstructor {
    return Array;
  }

  toJSON(): unknown[] {
    return ['forged'];
  }
}

function assertJsonIssue(
  result: { success: boolean; error?: { issues: Array<{ message: string }> } },
  message: string,
): void {
  assert.equal(result.success, false);
  if (!result.success) {
    assert.equal(
      result.error?.issues.some((issue) => issue.message.includes(message)),
      true,
    );
  }
}

function voiceSpec(): Record<string, unknown> {
  const value: Record<string, unknown> = {
    contract_version: 'VoiceSpec.v1',
    subject_id: 'mom',
    rhythm: 'steady',
    vocabulary: [],
    forbidden_phrases: [],
    approved_examples: ['one', 'two', 'three'],
  };
  value.voice_spec_digest = deriveVoiceSpecDigestV1(value);
  return value;
}

test('Parzifal identity record reference and durable record match Python digest parity', () => {
  const value = record();
  const ref = ParzifalIdentityRecordRefV1Schema.parse({
    id: value.id,
    version: value.version,
    digest: value.digest,
  });
  const parsed = ParzifalIdentityAuthorityRecordV1Schema.parse(value);

  assert.deepEqual(ref, {
    id: 'parzifal-identity-1',
    version: 4,
    digest: 'sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3',
  });
  assert.equal(parsed.digest, ref.digest);
  assert.equal(
    parsed.digest,
    'sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3',
  );
  assert.equal(Object.isFrozen(parsed), true);
  assert.equal(Object.isFrozen(parsed.identity_lock), true);
});

test('Parzifal identity record rejects malformed references, drift, and mutable authority', () => {
  const invalidVersion = record();
  invalidVersion.version = true;
  assert.equal(ParzifalIdentityAuthorityRecordV1Schema.safeParse(invalidVersion).success, false);

  const invalidDigest = record();
  invalidDigest.digest = `sha256:${'A'.repeat(64)}`;
  assert.equal(ParzifalIdentityAuthorityRecordV1Schema.safeParse(invalidDigest).success, false);

  const extra = record();
  extra.record_id = 'alias-is-forbidden';
  assert.equal(ParzifalIdentityAuthorityRecordV1Schema.safeParse(extra).success, false);

  const drift = record();
  ((drift.cast_sheets as Record<string, unknown>).by_id as Record<string, Record<string, unknown>>)
    .mom.voice_id = 'voice-mom-2';
  assert.equal(ParzifalIdentityAuthorityRecordV1Schema.safeParse(drift).success, false);

  const noncanonicalUtc = record();
  noncanonicalUtc.emitted_at = '2026-07-26T01:02:03+0000';
  assert.equal(ParzifalIdentityAuthorityRecordV1Schema.safeParse(noncanonicalUtc).success, false);

  const yearZero = record();
  yearZero.emitted_at = '0000-01-01T00:00:00+00:00';
  assert.equal(ParzifalIdentityAuthorityRecordV1Schema.safeParse(yearZero).success, false);
});

test('Parzifal identity record preserves Python canonical BOM text for digest parity', () => {
  const value = recordBody();
  value.id = '\ufeffparzifal-identity-1';
  const parsed = ParzifalIdentityAuthorityRecordV1Schema.parse({
    ...value,
    digest: deriveParzifalIdentityAuthorityRecordDigestV1(value),
  });

  assert.equal(parsed.id, '\ufeffparzifal-identity-1');
  assert.equal(
    parsed.digest,
    'sha256:4c1f4cb807f8228105dbccab90a87af9742f2b26eb7f5d9d37d92c5245b1aa06',
  );
});

test('Parzifal record rejects RegExp and class objects but accepts frozen null-prototype JSON', () => {
  for (const invalid of [/not-json/, new NonJsonDocument()]) {
    const value = recordBody();
    (value.identity_lock as Record<string, unknown>).invalid = invalid;

    assert.throws(() => deriveParzifalIdentityAuthorityRecordDigestV1(value));
    assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse({
      ...value,
      digest: sha256Digest({ placeholder: 'digest' }),
    }), 'non-JSON object');
  }

  const nullPrototypeDocument = Object.assign(Object.create(null), {
    nested: Object.assign(Object.create(null), { source: 'parzifal' }),
  });
  const value = recordBody();
  value.identity_lock = nullPrototypeDocument;
  const parsed = ParzifalIdentityAuthorityRecordV1Schema.parse({
    ...value,
    digest: deriveParzifalIdentityAuthorityRecordDigestV1(value),
  });

  assert.equal(Object.isFrozen(parsed.identity_lock), true);
  assert.equal(Object.isFrozen((parsed.identity_lock as Record<string, unknown>).nested), true);
});

test('Parzifal fractional timestamps have one Python parity form and digest', () => {
  const vectors = [
    ['.0', '2026-07-26T01:02:03+00:00', 'sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3'],
    ['.00', '2026-07-26T01:02:03+00:00', 'sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3'],
    ['.000000', '2026-07-26T01:02:03+00:00', 'sha256:db12f62b6d8c3671ad49acc8d1cca60ad4f2ab3b7ec63a6563b68dd1a58f33a3'],
    ['.1', '2026-07-26T01:02:03.100000+00:00', 'sha256:10315ed874540d33dd3ab64998c480658a5e13d5e07e751aeef25de053c9224a'],
    ['.12', '2026-07-26T01:02:03.120000+00:00', 'sha256:112cbb6371b10a700db45ffbffa6944372dd8e8395ddf5e200e76b55ea037766'],
    ['.123', '2026-07-26T01:02:03.123000+00:00', 'sha256:082d7d04483c4566832e0678c77fcb8aba6190f95da9ea26d7c9bd0103938703'],
    ['.1234', '2026-07-26T01:02:03.123400+00:00', 'sha256:eae1e99ea7f84294a72482bc5c78c0f887c6414e2ee6da2f2e4acd0f487e0161'],
    ['.12345', '2026-07-26T01:02:03.123450+00:00', 'sha256:78b7987c6fccb205dd787008f9d88dcf05211eca4c3ed63da436cb2706a49e6c'],
    ['.123456', '2026-07-26T01:02:03.123456+00:00', 'sha256:7336fb5886675c0257428efdaf677356f2d94ac857018f6df9484a6cfc318a93'],
  ] as const;

  for (const [fraction, canonicalTimestamp, digest] of vectors) {
    for (const utcSuffix of ['Z', '+00:00']) {
      const value = recordBody();
      value.emitted_at = `2026-07-26T01:02:03${fraction}${utcSuffix}`;
      const parsed = ParzifalIdentityAuthorityRecordV1Schema.parse({
        ...value,
        digest: deriveParzifalIdentityAuthorityRecordDigestV1(value),
      });

      assert.equal(parsed.emitted_at, canonicalTimestamp);
      assert.equal(parsed.digest, digest);
    }
  }
});

test('Parzifal record rejects symbol keys and sparse JSON document arrays', () => {
  const symbolKey = Symbol('not-json');
  const symbolValue = recordBody();
  Object.defineProperty(symbolValue.identity_lock as object, symbolKey, {
    enumerable: true,
    value: 'hidden',
  });

  assert.throws(
    () => deriveParzifalIdentityAuthorityRecordDigestV1(symbolValue),
    /symbol-keyed/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse({
    ...symbolValue,
    digest: sha256Digest({ placeholder: 'digest' }),
  }), 'symbol-keyed');

  const sparseValue = recordBody();
  const sparseArray = new Array<string>(2);
  sparseArray[1] = 'present';
  (sparseValue.identity_lock as Record<string, unknown>).sparse = sparseArray;

  assert.throws(
    () => deriveParzifalIdentityAuthorityRecordDigestV1(sparseValue),
    /sparse array/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse({
    ...sparseValue,
    digest: sha256Digest({ placeholder: 'digest' }),
  }), 'sparse array');
});

test('Parzifal record and material reject Array subclasses before serialization can forge them', () => {
  const forgedRecordValues = new ForgingArray<string>();
  forgedRecordValues.push('actual');
  assert.deepEqual([...forgedRecordValues], ['actual']);
  assert.deepEqual(forgedRecordValues.map((value) => value), ['actual']);
  assert.equal(JSON.stringify(forgedRecordValues), '["forged"]');

  const recordValue = recordBody();
  (recordValue.identity_lock as Record<string, unknown>).values = forgedRecordValues;
  assert.throws(
    () => deriveParzifalIdentityAuthorityRecordDigestV1(recordValue),
    /non-JSON array/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse({
    ...recordValue,
    digest: sha256Digest({ placeholder: 'digest' }),
  }), 'non-JSON array');

  const materialPayload = sealedPayload();
  const forgedSpeakers = new ForgingArray<Record<string, unknown>>();
  forgedSpeakers.push(
    (materialPayload.speakers as Array<Record<string, unknown>>)[0],
  );
  materialPayload.speakers = forgedSpeakers;
  assert.throws(
    () => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(materialPayload),
    /non-JSON array/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityMaterialV1Schema.safeParse({
    artifact_type: 'identity_lock',
    artifact_digest: materialPayload.identity_lock_digest,
    payload_digest: sha256Digest({ placeholder: 'digest' }),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: materialPayload,
  }), 'non-JSON array');
});

test('Parzifal record rejects hidden and accessor JSON document properties', () => {
  const hiddenValue = recordBody();
  Object.defineProperty(hiddenValue.identity_lock as object, 'hidden', {
    enumerable: false,
    value: 'not-json',
  });

  assert.throws(
    () => deriveParzifalIdentityAuthorityRecordDigestV1(hiddenValue),
    /non-enumerable own string property/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse({
    ...hiddenValue,
    digest: sha256Digest({ placeholder: 'digest' }),
  }), 'non-enumerable own string property');

  const accessorValue = recordBody();
  Object.defineProperty(accessorValue.identity_lock as object, 'computed', {
    enumerable: true,
    get: () => 'not-json',
  });

  assert.throws(
    () => deriveParzifalIdentityAuthorityRecordDigestV1(accessorValue),
    /accessor property/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse({
    ...accessorValue,
    digest: sha256Digest({ placeholder: 'digest' }),
  }), 'accessor property');
});

test('Parzifal record helper rejects root accessors before reading a field', () => {
  const value = recordBody();
  const id = value.id;
  let getterCalls = 0;
  delete value.id;
  Object.defineProperty(value, 'id', {
    enumerable: true,
    get: () => {
      getterCalls += 1;
      return id;
    },
  });
  Object.defineProperty(value, 'digest', {
    enumerable: true,
    value: sha256Digest({ placeholder: 'digest' }),
  });

  assert.throws(
    () => deriveParzifalIdentityAuthorityRecordDigestV1(value),
    /accessor property/,
  );
  assert.equal(getterCalls, 0);
  assertJsonIssue(ParzifalIdentityAuthorityRecordV1Schema.safeParse(value), 'accessor property');
  assert.equal(getterCalls, 0);
});

test('Parzifal authority material is the exact fully sealed Python parity wrapper', () => {
  const parsed = ParzifalIdentityAuthorityMaterialV1Schema.parse(material());

  assert.deepEqual(Object.keys(parsed).sort(), [
    'artifact_digest',
    'artifact_type',
    'payload_digest',
    'receipt_id',
    'sealed_payload',
  ]);
  assert.equal(parsed.artifact_digest, parsed.sealed_payload.identity_lock_digest);
  assert.equal(
    parsed.payload_digest,
    'sha256:461b3934f5abcf907d65424121b431a67a36cfdad0c3916da22a5d13cd3a4571',
  );
  assert.equal(parsed.sealed_payload.voice_spec, null);
  assert.equal(parsed.sealed_payload.locale, 'ko');
  assert.equal(parsed.sealed_payload.audience_lock, null);
  assert.equal(Object.isFrozen(parsed), true);
  assert.equal(Object.isFrozen(parsed.sealed_payload), true);
});

test('Parzifal authority material rejects wrapper and speaker drift', () => {
  for (const mutate of [
    (value: Record<string, any>) => { value.artifact_type = 'product_truth'; },
    (value: Record<string, any>) => { value.artifact_digest = sha256Digest({ other: 1 }); },
    (value: Record<string, any>) => { value.payload_digest = sha256Digest({ other: 2 }); },
    (value: Record<string, any>) => { value.record_ref = { id: 'must-not-leak' }; },
    (value: Record<string, any>) => { delete value.sealed_payload.speakers[0].voice_id; },
    (value: Record<string, any>) => {
      value.sealed_payload.speakers[0].identity_binding_digest = sha256Digest({ wrong: true });
    },
  ]) {
    const value = structuredClone(material());
    mutate(value);
    assert.equal(ParzifalIdentityAuthorityMaterialV1Schema.safeParse(value).success, false);
  }
});

test('Parzifal identity authority payload digest rejects an unsealed speaker', () => {
  const value = sealedPayload();
  const speaker = (value.speakers as Array<Record<string, unknown>>)[0];
  delete speaker.face_id;
  delete speaker.voice_id;
  delete speaker.identity_binding_digest;

  assert.throws(() => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(value));
});

test('Parzifal material rejects a nested class instance but freezes null-prototype JSON', () => {
  const classPayload = sealedPayload();
  classPayload.voice_spec = new NonJsonVoiceSpec();

  assert.throws(() => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(classPayload));
  assertJsonIssue(ParzifalIdentityAuthorityMaterialV1Schema.safeParse({
    artifact_type: 'identity_lock',
    artifact_digest: classPayload.identity_lock_digest,
    payload_digest: sha256Digest({ placeholder: 'digest' }),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: classPayload,
  }), 'non-JSON object');

  const nullPrototypePayload = Object.assign(Object.create(null), sealedPayload());
  const parsed = ParzifalIdentityAuthorityMaterialV1Schema.parse({
    artifact_type: 'identity_lock',
    artifact_digest: nullPrototypePayload.identity_lock_digest,
    payload_digest: deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(
      nullPrototypePayload,
    ),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: nullPrototypePayload,
  });

  assert.equal(Object.isFrozen(parsed.sealed_payload), true);
});

test('Parzifal material rejects symbol keys and sparse arrays in nested voice spec', () => {
  const symbolPayload = sealedPayload();
  const symbolVoiceSpec = voiceSpec();
  Object.defineProperty(symbolVoiceSpec, Symbol('not-json'), {
    enumerable: true,
    value: 'hidden',
  });
  symbolPayload.voice_spec = symbolVoiceSpec;

  assert.throws(
    () => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(symbolPayload),
    /symbol-keyed/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityMaterialV1Schema.safeParse({
    artifact_type: 'identity_lock',
    artifact_digest: symbolPayload.identity_lock_digest,
    payload_digest: sha256Digest({ placeholder: 'digest' }),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: symbolPayload,
  }), 'symbol-keyed');

  const sparsePayload = sealedPayload();
  const sparseVoiceSpec = voiceSpec();
  const sparseVocabulary = new Array<string>(2);
  sparseVocabulary[1] = 'present';
  sparseVoiceSpec.vocabulary = sparseVocabulary;
  sparsePayload.voice_spec = sparseVoiceSpec;

  assert.throws(
    () => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(sparsePayload),
    /sparse array/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityMaterialV1Schema.safeParse({
    artifact_type: 'identity_lock',
    artifact_digest: sparsePayload.identity_lock_digest,
    payload_digest: sha256Digest({ placeholder: 'digest' }),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: sparsePayload,
  }), 'sparse array');
});

test('Parzifal material rejects hidden and accessor properties in nested voice spec', () => {
  const hiddenPayload = sealedPayload();
  const hiddenVoiceSpec = voiceSpec();
  Object.defineProperty(hiddenVoiceSpec, 'hidden', {
    enumerable: false,
    value: () => 'not-json',
  });
  hiddenPayload.voice_spec = hiddenVoiceSpec;

  assert.throws(
    () => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(hiddenPayload),
    /non-enumerable own string property/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityMaterialV1Schema.safeParse({
    artifact_type: 'identity_lock',
    artifact_digest: hiddenPayload.identity_lock_digest,
    payload_digest: sha256Digest({ placeholder: 'digest' }),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: hiddenPayload,
  }), 'non-enumerable own string property');

  const accessorPayload = sealedPayload();
  const accessorVoiceSpec = voiceSpec();
  delete accessorVoiceSpec.rhythm;
  Object.defineProperty(accessorVoiceSpec, 'rhythm', {
    enumerable: true,
    get: () => 'steady',
  });
  accessorPayload.voice_spec = accessorVoiceSpec;

  assert.throws(
    () => deriveParzifalIdentityAuthorityMaterialPayloadDigestV1(accessorPayload),
    /accessor property/,
  );
  assertJsonIssue(ParzifalIdentityAuthorityMaterialV1Schema.safeParse({
    artifact_type: 'identity_lock',
    artifact_digest: accessorPayload.identity_lock_digest,
    payload_digest: sha256Digest({ placeholder: 'digest' }),
    receipt_id: 'parzifal:identity_lock:receipt-1',
    sealed_payload: accessorPayload,
  }), 'accessor property');
});
