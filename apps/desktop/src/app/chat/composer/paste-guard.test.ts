import { beforeEach, describe, expect, it } from 'vitest'

import { isRepeatedPaste, resetPasteGuard } from './paste-guard'

beforeEach(resetPasteGuard)

describe('paste guard', () => {
  it('lets the first paste through', () => {
    expect(isRepeatedPaste('Merlin 3.5 Flash', 1000)).toBe(false)
  })

  it('swallows the same payload inside the repeat window', () => {
    expect(isRepeatedPaste('Merlin 3.5 Flash', 1000)).toBe(false)
    expect(isRepeatedPaste('Merlin 3.5 Flash', 1150)).toBe(true)
    expect(isRepeatedPaste('Merlin 3.5 Flash', 1300)).toBe(true)
  })

  it('lets a deliberate second paste through once the window has passed', () => {
    expect(isRepeatedPaste('same text', 1000)).toBe(false)
    expect(isRepeatedPaste('same text', 1500)).toBe(false)
  })

  it('never swallows different payloads or empty ones', () => {
    expect(isRepeatedPaste('first', 1000)).toBe(false)
    expect(isRepeatedPaste('second', 1010)).toBe(false)
    expect(isRepeatedPaste('   ', 1020)).toBe(false)
  })
})
