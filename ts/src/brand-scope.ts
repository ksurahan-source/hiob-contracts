import { z } from 'zod';

function hasUnpairedSurrogate(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const low = value.charCodeAt(index + 1);
      if (!(low >= 0xdc00 && low <= 0xdfff)) return true;
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true;
    }
  }
  return false;
}

function hasControlCharacter(value: string): boolean {
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0;
    if (code <= 0x1f || (code >= 0x7f && code <= 0x9f)) {
      return true;
    }
  }
  return false;
}

export const CanonicalBrandSlugSchema = z
  .string()
  .refine(
    (value) => value.trim().length > 0,
    'brand_slug must not be blank',
  )
  .refine(
    (value) => value === value.trim(),
    'brand_slug must not have surrounding whitespace',
  )
  .refine(
    (value) => !hasUnpairedSurrogate(value),
    'brand_slug must contain valid Unicode scalar values',
  )
  .refine(
    (value) => !hasControlCharacter(value),
    'brand_slug must not contain control characters',
  );

export function canonicalBrandSlug(value: unknown): string {
  return CanonicalBrandSlugSchema.parse(value);
}
