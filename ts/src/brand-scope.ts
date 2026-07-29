import { z } from 'zod';

const CONTRACT_WHITESPACE = new Set([
  '\u0009',
  '\u000A',
  '\u000B',
  '\u000C',
  '\u000D',
  '\u0020',
  '\u00A0',
  '\u1680',
  '\u2000',
  '\u2001',
  '\u2002',
  '\u2003',
  '\u2004',
  '\u2005',
  '\u2006',
  '\u2007',
  '\u2008',
  '\u2009',
  '\u200A',
  '\u2028',
  '\u2029',
  '\u202F',
  '\u205F',
  '\u3000',
  '\uFEFF',
]);

function hasSurroundingContractWhitespace(value: string): boolean {
  return value.length > 0
    && (
      CONTRACT_WHITESPACE.has(value[0] ?? '')
      || CONTRACT_WHITESPACE.has(value[value.length - 1] ?? '')
    );
}

export function isContractBlank(value: string): boolean {
  return value.length === 0
    || [...value].every((char) => CONTRACT_WHITESPACE.has(char));
}

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
    (value) => value.length > 0 && ![...value].every(
      (char) => CONTRACT_WHITESPACE.has(char),
    ),
    'brand_slug must not be blank',
  )
  .refine(
    (value) => !hasSurroundingContractWhitespace(value),
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
