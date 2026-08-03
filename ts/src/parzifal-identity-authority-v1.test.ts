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
