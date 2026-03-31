/** 改善前/後のバージョンラベルを付けたプランリストを構築する */
export function buildPlanVersions(
  textContents: Array<{ agent?: string; content?: string }>,
  t: (key: string) => string,
): Array<{ label: string; content: string }> {
  const plans = textContents.filter(c => c.agent === 'marketing-plan-agent' && c.content)
  if (plans.length <= 1) return []

  return plans.map((p, i) => ({
    label: i === 0 ? t('eval.version.original') : `${t('eval.version.refined')} ${i > 1 ? i : ''}`.trim(),
    content: p.content || '',
  }))
}
