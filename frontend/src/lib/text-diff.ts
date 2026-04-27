export type TextDiffLineType = 'unchanged' | 'added' | 'removed'

export interface TextDiffLine {
  type: TextDiffLineType
  text: string
}

export interface TextDiffSummary {
  added: number
  removed: number
  unchanged: number
}

function splitLines(text: string): string[] {
  if (!text) return []
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
}

export function buildTextDiff(previousText: string, currentText: string): TextDiffLine[] {
  const previousLines = splitLines(previousText)
  const currentLines = splitLines(currentText)
  const rows = previousLines.length + 1
  const columns = currentLines.length + 1
  const table = Array.from({ length: rows }, () => Array<number>(columns).fill(0))

  for (let previousIndex = previousLines.length - 1; previousIndex >= 0; previousIndex -= 1) {
    for (let currentIndex = currentLines.length - 1; currentIndex >= 0; currentIndex -= 1) {
      table[previousIndex][currentIndex] = previousLines[previousIndex] === currentLines[currentIndex]
        ? table[previousIndex + 1][currentIndex + 1] + 1
        : Math.max(table[previousIndex + 1][currentIndex], table[previousIndex][currentIndex + 1])
    }
  }

  const diffLines: TextDiffLine[] = []
  let previousIndex = 0
  let currentIndex = 0

  while (previousIndex < previousLines.length || currentIndex < currentLines.length) {
    if (
      previousIndex < previousLines.length
      && currentIndex < currentLines.length
      && previousLines[previousIndex] === currentLines[currentIndex]
    ) {
      diffLines.push({ type: 'unchanged', text: previousLines[previousIndex] })
      previousIndex += 1
      currentIndex += 1
      continue
    }

    if (
      currentIndex >= currentLines.length
      || (
        previousIndex < previousLines.length
        && table[previousIndex + 1][currentIndex] >= table[previousIndex][currentIndex + 1]
      )
    ) {
      diffLines.push({ type: 'removed', text: previousLines[previousIndex] })
      previousIndex += 1
      continue
    }

    diffLines.push({ type: 'added', text: currentLines[currentIndex] })
    currentIndex += 1
  }

  return diffLines
}

export function summarizeTextDiff(diffLines: TextDiffLine[]): TextDiffSummary {
  return diffLines.reduce<TextDiffSummary>(
    (summary, line) => ({
      ...summary,
      [line.type]: summary[line.type] + 1,
    }),
    { added: 0, removed: 0, unchanged: 0 },
  )
}
