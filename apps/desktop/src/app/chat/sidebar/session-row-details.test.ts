import { describe, expect, it } from 'vitest'

import type { SessionInfo } from '@/types/merlin'

import { sessionRowDetails, type SessionRowFormatters } from './session-row-details'

const en: SessionRowFormatters = {
  messageCount: count => `${count} ${count === 1 ? 'message' : 'messages'}`,
  toolCallCount: count => `${count} ${count === 1 ? 'tool call' : 'tool calls'}`
}

const session = (overrides: Partial<SessionInfo> = {}): SessionInfo => ({
  ended_at: null,
  id: 's1',
  input_tokens: 0,
  is_active: false,
  last_active: 1,
  message_count: 26,
  model: 'google/gemini-3.1-pro',
  output_tokens: 0,
  preview: '  Explore\nGmail-like density tiers for session rows.  ',
  source: 'desktop',
  started_at: 1,
  title: 'Session density exploration',
  tool_call_count: 8,
  ...overrides
})

describe('session row details', () => {
  it('formats deterministic metadata without ambiguous call wording', () => {
    expect(sessionRowDetails(session({ git_branch: 'feature/menu' }), en)).toEqual({
      metadata: 'feature/menu · Gemini 3.1 Pro · 26 messages · 8 tool calls',
      preview: 'Explore Gmail-like density tiers for session rows.'
    })
  })

  it('uses singular labels and omits unavailable fields', () => {
    expect(
      sessionRowDetails(
        session({
          git_branch: null,
          message_count: 1,
          model: null,
          preview: null,
          title: 'Manual title',
          tool_call_count: 1
        }),
        en
      )
    ).toEqual({ metadata: '1 message · 1 tool call', preview: null })
  })

  it('omits zero counts from metadata so the sidebar stays clean', () => {
    expect(
      sessionRowDetails(session({ git_branch: null, message_count: 0, model: null, tool_call_count: 0 }), en)
    ).toEqual({ metadata: '', preview: 'Explore Gmail-like density tiers for session rows.' })
  })

  it('normalizes whitespace-only title, branch, and preview values', () => {
    expect(
      sessionRowDetails(
        session({
          git_branch: '   ',
          preview: '  ',
          title: '   '
        }),
        en
      )
    ).toEqual({ metadata: 'Gemini 3.1 Pro · 26 messages · 8 tool calls', preview: null })
  })

  it('omits the preview when it already supplies the displayed title', () => {
    expect(sessionRowDetails(session({ title: null }), en)).toEqual({
      metadata: 'Gemini 3.1 Pro · 26 messages · 8 tool calls',
      preview: null
    })
  })
})

describe('session row model label', () => {
  // The sidebar names models the way the composer pill does — the prettifier in
  // lib/model-status-label is the single source of that naming. Echoing the raw
  // provider slug here is what made the list read like a config file.
  it('prettifies the ids sessions actually carry', () => {
    const label = (model: string) =>
      sessionRowDetails(session({ git_branch: null, message_count: 0, model, tool_call_count: 0 }), en).metadata

    expect(label('deepseek-flash')).toBe('DeepSeek Flash')
    expect(label('glm-5.3-flash')).toBe('GLM 5.3 Flash')
    // GPT ids keep their provider casing rule (`gpt-` → `GPT-`), which is what
    // the composer pill already prints for this same model.
    expect(label('clario/gpt-6-sol')).toBe('GPT-6-sol')
    expect(label('deepseek/deepseek-v4-pro')).toBe('DeepSeek V4 Pro')
  })
})
