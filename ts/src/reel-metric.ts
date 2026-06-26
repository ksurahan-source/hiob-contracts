/**
 * ReelMetric — 측정 계약 (Metis)
 *
 * 성과 → 창작 피드백 루프(해자).
 *
 * grounding: reel_metrics(brand_slug, run_id, source, metric_date, utm_content,
 * impressions, clicks, spend_krw, thruplays, leads, purchases, revenue_krw).
 * roas/ctr는 파생. 라이브러리·인테이크가 소비(과거 승자 훅을 brief에 seed).
 */

import { z } from 'zod';

/**
 * ReelMetric — 릴 측정 데이터
 */
export const ReelMetricSchema = z.object({
  brand_slug: z.string().min(1),
  run_id: z.string().min(1),
  source: z.string().default('meta'),
  metric_date: z.string().date().optional().nullable(),
  utm_content: z.string().optional().nullable(),
  impressions: z.number().int().nonnegative().default(0),
  clicks: z.number().int().nonnegative().default(0),
  spend_krw: z.number().nonnegative().default(0),
  thruplays: z.number().int().nonnegative().default(0),
  leads: z.number().int().nonnegative().default(0),
  purchases: z.number().int().nonnegative().default(0),
  revenue_krw: z.number().nonnegative().default(0),
}).strict();

export type ReelMetric = z.infer<typeof ReelMetricSchema>;

/**
 * ReelMetric에서 ROAS 계산 (파생 필드)
 * spend_krw <= 0이면 undefined
 */
export function calculateRoas(metric: ReelMetric): number | undefined {
  if (metric.spend_krw <= 0) {
    return undefined;
  }
  return Math.round((metric.revenue_krw / metric.spend_krw) * 1000) / 1000;
}

/**
 * ReelMetric에서 CTR 계산 (파생 필드)
 * impressions <= 0이면 undefined
 */
export function calculateCtr(metric: ReelMetric): number | undefined {
  if (metric.impressions <= 0) {
    return undefined;
  }
  return Math.round((metric.clicks / metric.impressions) * 10000) / 10000;
}

/**
 * ReelMetric 유효성 검사 함수
 * 인과 날조 금지: 데이터 없이 ROAS 주장 불가
 */
export function validateReelMetric(metric: ReelMetric): string[] {
  const errors: string[] = [];

  if (!metric.brand_slug) {
    errors.push('brand_slug 없음');
  }

  if (!metric.run_id) {
    errors.push('run_id 없음');
  }

  return errors;
}
