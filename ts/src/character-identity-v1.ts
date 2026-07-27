import { sha256Digest } from './factory/digest.js';

export type CharacterIdentityBindingInputV1 = {
  subject_id: string;
  face_id: string;
  voice_id: string;
};

function requiredText(value: string, field: string): string {
  const text = value.trim();
  if (!text) throw new Error(`${field} is required`);
  return text;
}

export function characterIdentityBindingPayloadV1(
  value: CharacterIdentityBindingInputV1,
): Record<string, string> {
  return {
    contract_version: 'CharacterIdentityBinding.v1',
    subject_id: requiredText(value.subject_id, 'subject_id'),
    face_id: requiredText(value.face_id, 'face_id'),
    voice_id: requiredText(value.voice_id, 'voice_id'),
  };
}

export function deriveCharacterIdentityBindingDigestV1(
  value: CharacterIdentityBindingInputV1,
): string {
  return sha256Digest(characterIdentityBindingPayloadV1(value));
}

export function characterIdentityBindingErrorV1(value: {
  subject_id: string;
  face_id?: string | null;
  voice_id?: string | null;
  identity_binding_digest?: string | null;
}): string | null {
  const faceId = value.face_id?.trim() ?? '';
  const voiceId = value.voice_id?.trim() ?? '';
  const bindingDigest = value.identity_binding_digest?.trim() ?? '';
  if (!faceId && !voiceId && !bindingDigest) return null;
  if (!faceId || !voiceId) return 'face_id and voice_id must be sealed together';
  if (!bindingDigest) {
    return 'identity_binding_digest is required for sealed face_id + voice_id';
  }
  const expected = deriveCharacterIdentityBindingDigestV1({
    subject_id: value.subject_id,
    face_id: faceId,
    voice_id: voiceId,
  });
  return bindingDigest === expected
    ? null
    : 'identity_binding_digest does not match subject_id + face_id + voice_id';
}
