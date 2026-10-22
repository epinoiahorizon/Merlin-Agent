/**
 * One paste, one insert.
 *
 * A single ⌘V can reach the composer more than once: the composer's own `paste`
 * handler and the window-level paste-to-focus router both observe the event
 * whenever focus moves during dispatch, and a held/repeated key sends the same
 * clipboard payload again a few milliseconds later. Either way the text lands
 * twice, and once the turn is sent it reads as the app having answered twice —
 * the failure mode is invisible in the model, the transcript shows ONE reply and
 * the user's own message carries the duplicate.
 *
 * Same payload arriving inside REPEAT_WINDOW_MS is the same gesture; the second
 * insert is swallowed. Outside the window the user really did paste twice and
 * gets both copies.
 */
const REPEAT_WINDOW_MS = 400

let lastPaste: { at: number; text: string } | null = null

/** True when this identical payload already landed moments ago. */
export function isRepeatedPaste(text: string, now = Date.now()): boolean {
  const trimmed = text.trim()

  if (!trimmed) {
    return false
  }

  if (lastPaste && lastPaste.text === trimmed && now - lastPaste.at < REPEAT_WINDOW_MS) {
    // Keep the stamp fresh so a held key cannot dribble copies in every 399ms.
    lastPaste = { at: now, text: trimmed }

    return true
  }

  lastPaste = { at: now, text: trimmed }

  return false
}

/** Test seam — a suite that pastes the same fixture twice is not a user gesture. */
export function resetPasteGuard(): void {
  lastPaste = null
}
