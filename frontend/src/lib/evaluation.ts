export interface EvaluationMetric {
  score: number
  reason?: string
}

export interface CustomEvaluationMetric {
  score: number
  details?: Record<string, boolean>
  reason?: string
}

export interface EvaluationError {
  error: string
}

export type BuiltinEvaluationResult = Record<string, EvaluationMetric> | EvaluationError

export interface EvaluationResult {
  builtin?: BuiltinEvaluationResult
  custom?: Record<string, CustomEvaluationMetric>
  marketing_quality?: Record<string, number | string>
  foundry_portal_url?: string
  error?: string
}

export interface EvaluationRecord {
  version: number
  round: number
  createdAt: string
  result: EvaluationResult
}

export interface EvaluationDeltaItem {
  key: string
  labelKey: string
  section: 'builtin' | 'marketing' | 'custom'
  current: number
  previous: number
  delta: number
  max: number
}

export interface EvaluationDetailChange {
  metricKey: string
  metricLabelKey: string
  item: string
  current: boolean
  previous: boolean
}

const MARKETING_KEYS = ['appeal', 'differentiation', 'kpi_validity', 'brand_tone', 'overall'] as const

function average(values: number[]): number {
  if (values.length === 0) return -1
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

export function hasBuiltinMetrics(builtin: BuiltinEvaluationResult | undefined): builtin is Record<string, EvaluationMetric> {
  return builtin !== undefined && !('error' in builtin)
}

export function cloneEvaluationResult(result: EvaluationResult): EvaluationResult {
  return JSON.parse(JSON.stringify(result)) as EvaluationResult
}

export function cloneEvaluationRecord(record: EvaluationRecord): EvaluationRecord {
  return {
    ...record,
    result: cloneEvaluationResult(record.result),
  }
}

export function getLatestEvaluation(evaluations: EvaluationRecord[]): EvaluationRecord | null {
  return evaluations.length > 0 ? evaluations[evaluations.length - 1] : null
}

function getBuiltinAverage(result: EvaluationResult): number {
  if (!hasBuiltinMetrics(result.builtin)) return -1

  const scores = Object.values(result.builtin)
    .map(metric => metric.score)
    .filter(score => Number.isFinite(score) && score >= 0)

  return average(scores)
}

function getMarketingAverage(result: EvaluationResult): number {
  const marketing = result.marketing_quality
  if (!marketing) return -1

  const overall = marketing.overall
  if (typeof overall === 'number' && overall >= 0) {
    return overall
  }

  const scores = ['appeal', 'differentiation', 'kpi_validity', 'brand_tone']
    .map(key => marketing[key])
    .filter((value): value is number => typeof value === 'number' && value >= 0)

  return average(scores)
}

function getCustomAverage(result: EvaluationResult): number {
  if (!result.custom) return -1

  const scores = Object.values(result.custom)
    .map(metric => metric.score)
    .filter(score => Number.isFinite(score) && score >= 0)
    .map(score => score * 5)

  return average(scores)
}

export function calculateEvaluationOverall(result: EvaluationResult): number {
  const categoryScores = [
    getBuiltinAverage(result),
    getMarketingAverage(result),
    getCustomAverage(result),
  ].filter(score => Number.isFinite(score) && score >= 0)

  return average(categoryScores)
}

export function getEvaluationDeltaItems(current: EvaluationResult, previous: EvaluationResult): EvaluationDeltaItem[] {
  const items: EvaluationDeltaItem[] = []

  if (hasBuiltinMetrics(current.builtin) && hasBuiltinMetrics(previous.builtin)) {
    const metricKeys = new Set([...Object.keys(current.builtin), ...Object.keys(previous.builtin)])
    for (const key of metricKeys) {
      const currentMetric = current.builtin[key]
      const previousMetric = previous.builtin[key]
      if (!currentMetric || !previousMetric) continue
      if (currentMetric.score < 0 || previousMetric.score < 0) continue
      items.push({
        key,
        labelKey: `eval.${key}`,
        section: 'builtin',
        current: currentMetric.score,
        previous: previousMetric.score,
        delta: currentMetric.score - previousMetric.score,
        max: 5,
      })
    }
  }

  const currentMarketing = current.marketing_quality
  const previousMarketing = previous.marketing_quality
  if (currentMarketing && previousMarketing) {
    for (const key of MARKETING_KEYS) {
      const currentMetric = currentMarketing[key]
      const previousMetric = previousMarketing[key]
      if (typeof currentMetric !== 'number' || typeof previousMetric !== 'number') continue
      if (currentMetric < 0 || previousMetric < 0) continue
      items.push({
        key,
        labelKey: `eval.${key}`,
        section: 'marketing',
        current: currentMetric,
        previous: previousMetric,
        delta: currentMetric - previousMetric,
        max: 5,
      })
    }
  }

  if (current.custom && previous.custom) {
    const metricKeys = new Set([...Object.keys(current.custom), ...Object.keys(previous.custom)])
    for (const key of metricKeys) {
      const currentMetric = current.custom[key]
      const previousMetric = previous.custom[key]
      if (!currentMetric || !previousMetric) continue
      if (currentMetric.score < 0 || previousMetric.score < 0) continue
      items.push({
        key,
        labelKey: `eval.${key}`,
        section: 'custom',
        current: currentMetric.score,
        previous: previousMetric.score,
        delta: currentMetric.score - previousMetric.score,
        max: 1,
      })
    }
  }

  return items
}

export function summarizeEvaluationDiff(items: EvaluationDeltaItem[]): {
  improved: number
  degraded: number
  unchanged: number
} {
  return items.reduce(
    (summary, item) => {
      if (item.delta > 0.05) {
        summary.improved += 1
      } else if (item.delta < -0.05) {
        summary.degraded += 1
      } else {
        summary.unchanged += 1
      }
      return summary
    },
    { improved: 0, degraded: 0, unchanged: 0 },
  )
}

export function getEvaluationDetailChanges(current: EvaluationResult, previous: EvaluationResult): EvaluationDetailChange[] {
  if (!current.custom || !previous.custom) return []

  const changes: EvaluationDetailChange[] = []
  const metricKeys = new Set([...Object.keys(current.custom), ...Object.keys(previous.custom)])

  for (const key of metricKeys) {
    const currentDetails = current.custom[key]?.details
    const previousDetails = previous.custom[key]?.details
    if (!currentDetails || !previousDetails) continue

    const detailKeys = new Set([...Object.keys(currentDetails), ...Object.keys(previousDetails)])
    for (const item of detailKeys) {
      const currentValue = currentDetails[item]
      const previousValue = previousDetails[item]
      if (typeof currentValue !== 'boolean' || typeof previousValue !== 'boolean') continue
      if (currentValue === previousValue) continue
      changes.push({
        metricKey: key,
        metricLabelKey: `eval.${key}`,
        item,
        current: currentValue,
        previous: previousValue,
      })
    }
  }

  return changes
}
