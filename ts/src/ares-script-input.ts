/**
 * AresScriptInput — TS mirror of factory/ares_script_input.py
 *
 * Karma-refined target input for Ares (p2a edge).
 * This is the canonical target_input schema that Karma produces when refining
 * Parzifal's outputs for Ares's ares.script.build node.
 *
 * ⚠️ AUTHORITY: Python. Round-trip to/from dict, digest parity with Python.
 */
import { z } from 'zod';

export const AresScriptInputSchema = z
  .object({
    brand_slug: z.string(),
    brand_identity: z.string().nullable().default(null),
    brand_usp: z.string().nullable().default(null),
    brand_voice_tone: z.string().nullable().default(null),
    brand_regulation: z.string().nullable().default(null),
    protagonist_id: z.string().nullable().default(null),
    protagonist_name: z.string().nullable().default(null),
    protagonist_age: z.number().int().nullable().default(null),
    protagonist_age_band: z.string().nullable().default(null),
    protagonist_gender: z.string().nullable().default(null),
    protagonist_region: z.string().nullable().default(null),
    protagonist_role: z.string().nullable().default(null),
    protagonist_voice_persona: z.string().nullable().default(null),
    target_pain: z.string().nullable().default(null),
    target_jtbd: z.string().nullable().default(null),
    target_context: z.string().nullable().default(null),
    target_blocker: z.string().nullable().default(null),
    target_objection: z.string().nullable().default(null),
    voc_real_quotes: z.array(z.string()).default([]),
    voc_core_pain: z.string().nullable().default(null),
    product_slug: z.string().nullable().default(null),
    listing_slug: z.string().nullable().default(null),
    listing_pitch: z.string().nullable().default(null),
    locale: z.string().default('ko'),
    style: z.string().nullable().default(null),
    reel_mode: z.string().nullable().default(null),
  })
  .strict();

export type AresScriptInput = z.infer<typeof AresScriptInputSchema>;

export function validateAresScriptInput(input: AresScriptInput): string[] {
  const errs: string[] = [];
  if (!input.brand_slug) {
    errs.push('AresScriptInput.brand_slug 필수');
  }
  if (!input.protagonist_name) {
    errs.push('AresScriptInput.protagonist_name 필수 (casting anchor)');
  }
  const groundingFacts = [input.voc_core_pain, input.target_pain, input.target_jtbd];
  if (!groundingFacts.some((f) => f)) {
    errs.push('AresScriptInput: 최소 1개의 grounding fact 필요 (pain/jtbd/voc_core_pain)');
  }
  return errs;
}
