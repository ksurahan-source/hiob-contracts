import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CharacterLockV1Schema,
  deriveCharacterLockDigestV1,
} from './character-lock-v1.js';

function payload(): Record<string, unknown> {
  const lockPayload = {
    contract_version: 'CharacterLock.v1' as const,
    workspace_id: '3c8102c6-ec84-4530-9606-1c977b090edc',
    brand_slug: 'viewok',
    subject_id: 'lead',
    version: 1,
    face_id: 'face-1',
    voice_id: 'voice-1',
    source_receipt_ref: 'parzifal-receipt-1',
    source_record_version: 1,
    source_receipt_digest: `sha256:${'1'.repeat(64)}`,
  };
  return {
    ...lockPayload,
    digest: deriveCharacterLockDigestV1(lockPayload),
  };
}

test('CharacterLock.v1 accepts one atomic identity version', () => {
  const parsed = CharacterLockV1Schema.parse(payload());

  assert.equal(parsed.face_id, 'face-1');
  assert.equal(parsed.voice_id, 'voice-1');
  assert.equal(parsed.version, 1);
  assert.equal(parsed.source_record_version, 1);
  assert.equal(
    parsed.digest,
    'sha256:56ce7a58420f437d3e3a61c53a4fb2137d19c4528981f35f23e97a29d28f77ed',
  );
});

test('CharacterLock.v1 rejects partial identity and digest drift', () => {
  for (const missing of ['face_id', 'voice_id', 'digest']) {
    const value = payload();
    delete value[missing];
    assert.equal(CharacterLockV1Schema.safeParse(value).success, false);
  }

  for (const field of ['workspace_id', 'brand_slug', 'face_id', 'voice_id']) {
    const value = payload();
    value[field] = field === 'workspace_id'
      ? '1cc18cfb-147d-4ad7-a4a1-f28e36ac2704'
      : 'changed';
    assert.equal(CharacterLockV1Schema.safeParse(value).success, false);
  }

  const sourceVersionDrift = payload();
  sourceVersionDrift.source_record_version = 2;
  assert.equal(
    CharacterLockV1Schema.safeParse(sourceVersionDrift).success,
    false,
  );
});

test('CharacterLock.v1 rejects blank scopes, unsafe versions, and extras', () => {
  const value = payload();
  value.brand_slug = ' ';
  value.version = Number.MAX_SAFE_INTEGER + 1;
  value.provider = 'seedream';

  assert.equal(CharacterLockV1Schema.safeParse(value).success, false);
});

test('CharacterLock.v1 accepts canonical text brand scope', () => {
  const value = payload();
  value.brand_slug = '히옵-마케팅';
  value.digest = deriveCharacterLockDigestV1(value);

  const parsed = CharacterLockV1Schema.parse(value);

  assert.equal(parsed.brand_slug, '히옵-마케팅');
});

test('CharacterLock.v1 forbids the brand_id alias', () => {
  const value = payload();
  value.brand_id = '2a86daca-f5f2-4a3d-a868-f283a0a57d84';

  assert.equal(CharacterLockV1Schema.safeParse(value).success, false);
});

test('CharacterLock.v1 rejects a non-positive version', () => {
  const value = payload();
  value.version = 0;

  assert.equal(CharacterLockV1Schema.safeParse(value).success, false);
});

test('CharacterLock.v1 rejects unpaired Unicode before hashing', () => {
  const value = payload();
  value.subject_id = '\ud800';

  assert.throws(() => deriveCharacterLockDigestV1(value));
  assert.equal(CharacterLockV1Schema.safeParse(value).success, false);
});

test('CharacterLock.v1 preserves valid Unicode scalar digest parity', () => {
  const value = payload();
  delete value.digest;
  value.subject_id = 'lead-😀';

  assert.equal(
    deriveCharacterLockDigestV1(value),
    'sha256:c4254b3b72b36051dc1a18d7ddbd6b9dab25e178a265e9a252e638437f83c351',
  );
});

test('CharacterLock.v1 parses to an immutable scalar record', () => {
  const parsed = CharacterLockV1Schema.parse(payload());

  assert.equal(Object.isFrozen(parsed), true);
  assert.throws(() => {
    (parsed as any).face_id = 'changed';
  }, TypeError);
  assert.equal(parsed.face_id, 'face-1');
});

test('CharacterLock.v1 digest helper rejects incomplete payloads', () => {
  const value = payload();
  delete value.digest;
  delete value.source_record_version;

  assert.throws(() => deriveCharacterLockDigestV1(value));
});
