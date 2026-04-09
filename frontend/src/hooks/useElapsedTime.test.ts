import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useElapsedTime } from './useElapsedTime'

describe('useElapsedTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('resets immediately when the running step changes', () => {
    const { result, rerender } = renderHook(
      ({ isRunning, resetKey }) => useElapsedTime(isRunning, resetKey),
      {
        initialProps: {
          isRunning: true,
          resetKey: 1,
        },
      },
    )

    act(() => {
      vi.advanceTimersByTime(2200)
    })

    expect(result.current).toBe(2)

    act(() => {
      rerender({ isRunning: true, resetKey: 2 })
    })

    expect(result.current).toBe(0)
  })
})
