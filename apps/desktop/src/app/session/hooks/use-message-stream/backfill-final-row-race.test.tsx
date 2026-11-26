import type { GatewayEventName } from '@merlin/shared'
import { act, cleanup } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

import { mergeOlderTranscriptPage } from '@/app/chat/transcript-backfill'
import { chatMessageText, textPart, toChatMessages } from '@/lib/chat-messages'

import { renderMessageStream } from './test-harness'

const SID = 'backfill-final-row-race'
const ANSWER = 'One stored answer.'

afterEach(cleanup)

it('does not show a backfilled final row beside its live stream when completion arrives', () => {
  const stream = renderMessageStream(SID)
  const send = (type: GatewayEventName, payload: Record<string, unknown> = {}) =>
    act(() => stream.handleEvent({ type, payload, session_id: SID }))
  const user = toChatMessages([{ id: 3993, role: 'user', content: 'Question' }])[0]
  stream.states.set(SID, { ...stream.state(), messages: [user], storedSessionId: 'stored-backfill-race' })

  send('message.start')
  // The live bubble already holds streamed text (its RAF flush completed).
  // Seed it directly to keep this regression focused on the backfill race,
  // without introducing an unrelated tool-response text boundary.
  const liveId = 'assistant-stream-live'
  stream.states.set(SID, {
    ...stream.state(),
    messages: [user, { id: liveId, role: 'assistant', parts: [textPart(ANSWER)], pending: true }],
    streamId: liveId,
    sawAssistantPayload: true
  })
  expect(stream.state().messages.filter(m => m.role === 'assistant')).toHaveLength(1)

  // "Show earlier" started before the final SQLite commit, but its page
  // arrives after it: the offset-drift merge brings back the just-saved row
  // while the gateway's completion receipt has not reached this window yet.
  const page = toChatMessages([
    { id: 3993, role: 'user', content: 'Question' },
    { id: 3994, role: 'assistant', content: ANSWER }
  ])
  const before = stream.state()
  stream.states.set(SID, {
    ...before,
    messages: mergeOlderTranscriptPage(before.messages, page)
  })
  expect(stream.state().messages.filter(m => m.role === 'assistant')).toHaveLength(2)

  send('message.complete', {
    text: ANSWER,
    persisted_turn: {
      row_ids: [3993, 3994],
      user_row_id: 3993,
      final_assistant_row_id: 3994,
      complete: true
    }
  })

  const assistants = stream.state().messages.filter(m => m.role === 'assistant' && !m.hidden)
  expect(assistants).toHaveLength(1)
  expect(assistants[0]).toMatchObject({ id: liveId, rowId: 3994, pending: false })
  expect(chatMessageText(assistants[0])).toBe(ANSWER)
  expect(assistants[0].parts.filter(part => part.type === 'text')).toHaveLength(1)
})
