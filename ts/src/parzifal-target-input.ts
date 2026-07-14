/**
 * ParzifalTargetInput — TS mirror of factory/parzifal_target_input.py
 *
 * Karma-refined target input for Parzifal (j2p edge).
 * This is the canonical target_input schema that Karma produces when refining
 * JanusBrief for Parzifal's parzifal.target.consolidate node.
 *
 * ⚠️ AUTHORITY: Python. Round-trip to/from dict, digest parity with Python.
 */
import { z } from 'zod';

export const ParzifalTargetInputSchema = z
  .object({
    brand_slug: z.string(),
    brand_identity: z.string().nullable().default(null),
    brand_usp: z.string().nullable().default(null),
    brand_voice_tone: z.string().nullable().default(null),
    brand_regulation: z.string().nullable().default(null),
    brand_price: z.string().nullable().default(null),
    brand_history: z.string().nullable().default(null),
    target_audience: z.string().nullable().default(null),
    target_jtbd: z.string().nullable().default(null),
    target_pain: z.string().nullable().default(null),
    target_blocker: z.string().nullable().default(null),
    target_price_sensitivity: z.string().nullable().default(null),
    target_objection: z.string().nullable().default(null),
    voc_core_pain: z.string().nullable().default(null),
    voc_real_reviews: z.array(z.string()).default([]),
    voc_evidence_source: z.string().nullable().default(null),
    product_slug: z.string().nullable().default(null),
    listing_slug: z.string().nullable().default(null),
    listing_url: z.string().nullable().default(null),
    locale: z.string().default('ko'),
    vertical_mode: z.string().nullable().default(null),
    protagonist: z.string().nullable().default(null),
    style: z.string().nullable().default(null),
    reel_mode: z.string().nullable().default(null),
  })
  .strict();

export type ParzifalTargetInput = z.infer<typeof ParzifalTargetInputSchema>;

export function validateParzifalTargetInput(input: ParzifalTargetInput): string[] {
  const errs: string[] = [];
  if (!input.brand_slug) {
    errs.push('ParzifalTargetInput.brand_slug 필수');
  }
  const targetFacts = [
    input.target_audience,
    input.target_jtbd,
    input.target_pain,
    input.target_blocker,
    input.voc_core_pain,
  ];
  if (!targetFacts.some((f) => f)) {
    errs.push('ParzifalTargetInput: 최소 1개의 target fact 필요 (audience/jtbd/pain/blocker/voc_core_pain)');
  }
  return errs;
}
