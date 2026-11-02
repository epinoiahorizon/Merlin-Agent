import { Box, Text, useStdout } from '@merlin/ink'
import React, { useMemo } from 'react'

import type { Theme } from '../../theme.js'

const MERLIN_LOGO: string[] = [
  '╔═╗╔╦╗╔══╗╔╗  ╦  ╔═╗',
  '╠═╣║║║╠═╦╝║╚╗ ║  ║ ║',
  '║  ║║║║║║  ║ ║ ║  ║ ║',
  '╚═╝╩ ╩╚╩╝  ╚═╝╚╝  ╚═╝'
]

const C: Record<string, string> = {
  pageBg: '#0A0F14',
  windowBg: '#0D141C',
  border: '#1C2A36',
  divider: '#152230',
  chrome: '#333E49',
  dim: '#4E5F6B',
  label: '#5A6B77',
  body: '#8296A5',
  nodeName: '#7E93A2',
  bold: '#E8EFF3',
  green: '#38D996',
  amber: '#E4B45C',
  cursor: '#4E7D8C'
}

const WIDTH = 88

// Minimal mock of the real StatusRule props for this standalone demo.
function useMockTheme(): Theme {
  return useMemo(
    () => ({
      color: {
        primary: '#2aa198',
        accent: '#38D996',
        border: C.border,
        text: C.body,
        muted: C.dim,
        completionBg: '#0D141C',
        completionCurrentBg: '#1C2A36',
        completionMetaBg: '#0D141C',
        completionMetaCurrentBg: '#1C2A36',
        label: C.label,
        ok: C.green,
        error: '#ff4d6d',
        warn: C.amber,
        tool: C.green,
        thinking: C.dim,
        syntaxString: C.green,
        syntaxNumber: C.amber,
        syntaxKeyword: C.body,
        syntaxComment: C.dim,
        prompt: C.body,
        sessionLabel: C.label,
        sessionBorder: C.border,
        statusBg: C.windowBg,
        statusFg: C.label,
        statusGood: C.green,
        statusWarn: C.amber,
        statusBad: '#ff4d6d',
        statusCritical: '#ff4d6d',
        selectionBg: '#1C2A36',
        diffAdded: C.green,
        diffRemoved: '#ff4d6d',
        diffAddedWord: C.green,
        diffRemovedWord: '#ff4d6d',
        shellDollar: C.dim
      },
      brand: {
        name: 'MERLIN',
        icon: 'ᛗ',
        prompt: 'ᛗ',
        welcome: '',
        goodbye: '',
        tool: '',
        helpHeader: ''
      },
      bannerLogo: '',
      bannerHero: ''
    }),
    []
  )
}

// Replicates the visual rule line used in appChrome StatusRule.
function StatusRuleLine({
  t,
  width,
  leftSegments,
  rightLabel
}: {
  t: Theme
  width: number
  leftSegments: React.ReactNode
  rightLabel?: string
}) {
  if (!rightLabel) {
    return (
      <Box height={1} overflow="hidden" width={width}>
        <Text color={t.color.border}>{'─ '}</Text>
        {leftSegments}
      </Box>
    )
  }

  const sep = width >= 24 ? ' ─ ' : ' '
  const rightWidth = Math.min(stringWidth(rightLabel), Math.max(0, width - stringWidth('─ ') - 3 - 12))
  const leftWidth = Math.max(1, width - sep.length - rightWidth)

  return (
    <Box flexDirection="row" height={1} overflow="hidden" width={width}>
      <Box flexDirection="row" overflow="hidden" width={leftWidth}>
        <Text color={t.color.border}>{'─ '}</Text>
        {leftSegments}
      </Box>
      {rightWidth > 0 ? (
        <>
          <Text color={t.color.border}>{sep}</Text>
          <Box overflow="hidden" width={rightWidth}>
            <Text color={t.color.label} wrap="truncate-end">
              {rightLabel}
            </Text>
          </Box>
        </>
      ) : null}
    </Box>
  )
}

function stringWidth(s: string): number {
  let w = 0

  for (const ch of s) {
    const code = ch.codePointAt(0) || 0
    // CJK / runes / emoji roughly 2 cells; ASCII 1
    w += code > 0x24ff ? 2 : 1
  }

  return w
}

export function OperatorConsoleV2() {
  const { stdout } = useStdout()
  const width = stdout ? stdout.columns : WIDTH
  const w = Math.min(WIDTH, Math.max(80, width - 4))
  const h = stdout ? stdout.rows : 24
  const t = useMockTheme()

  const logoLines = useMemo(() => {
    const lines = MERLIN_LOGO.map((text, i) => {
      const p = [C.green, C.body, C.dim, C.border]

      return [p[i] ?? C.dim, text] as [string, string]
    })

    return lines
  }, [])

  const logoW = useMemo(() => Math.max(...logoLines.map(([, t]) => t.length)), [logoLines])

  const [now, setNow] = React.useState(new Date())
  const [manaPct, setManaPct] = React.useState(57)
  const [typed, setTyped] = React.useState('')
  const fullReply =
    "I'll capture windows-service-deploy as a skill and verify the eval suite before applying it globally."

  React.useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)

    return () => clearInterval(timer)
  }, [])

  React.useEffect(() => {
    const timer = setInterval(() => {
      setManaPct(p => (p >= 95 ? 12 : p + 3))
    }, 800)

    return () => clearInterval(timer)
  }, [])

  React.useEffect(() => {
    if (typed.length >= fullReply.length) {
      const reset = setTimeout(() => setTyped(''), 4000)

      return () => clearTimeout(reset)
    }

    const timer = setTimeout(() => setTyped(fullReply.slice(0, typed.length + 2)), 80)

    return () => clearTimeout(timer)
  }, [typed])

  const timeStr = now.toLocaleTimeString('en-GB', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
  const filled = Math.round((manaPct / 100) * 16)
  const empty = 16 - filled
  const manaBar = '▰'.repeat(filled) + '▱'.repeat(empty)

  const statusSegments = (
    <>
      <Text color={t.color.accent}>{'ᛗ kimi-k2.7-code'}</Text>
      <Text color={t.color.muted}>{' │ '}</Text>
      <Text color={t.color.ok}>{'ᛟ grimoire'}</Text>
      <Text color={t.color.muted}>{' │ '}</Text>
      <Text color={t.color.muted}>{'ᚨ['}</Text>
      <Text color={t.color.accent}>{manaBar}</Text>
      <Text color={t.color.muted}>{'>' + manaPct + '%'}</Text>
      <Text color={t.color.muted}>{' │ '}</Text>
      <Text color={t.color.muted}>{'ᛝ '}</Text>
      <Text color={typed.length > 0 ? t.color.ok : t.color.muted}>
        {typed.length > 0 ? 'stream · ' + timeStr.slice(0, 5) : 'idle · ' + timeStr.slice(0, 5)}
      </Text>
    </>
  )

  return (
    <Box alignItems="center" flexDirection="column" height={h} justifyContent="center" width={width}>
      <Box
        backgroundColor={C.windowBg}
        borderColor={C.border}
        borderStyle="round"
        flexDirection="column"
        height={h}
        width={w + 2}
      >
        {/* Title bar */}
        <Box
          backgroundColor={C.windowBg}
          flexDirection="row"
          justifyContent="space-between"
          overflow="hidden"
          paddingX={1}
          paddingY={0}
          width={w}
        >
          <Box flexDirection="column" marginRight={1}>
            {logoLines.map(([color, text], i) => (
              <Text color={color} key={i} wrap="truncate-end">
                {text}
              </Text>
            ))}
          </Box>
          <Box alignItems="flex-end" flexDirection="column">
            <Text color={C.label}>MERLIN AGENT</Text>
            <Text color={C.label}>operator session</Text>
          </Box>
        </Box>
        <Box height={1} paddingX={0} paddingY={0} width={w}>
          <Text color={C.divider}>{'─'.repeat(w)}</Text>
        </Box>

        <Box flexDirection="row" flexGrow={1} overflow="hidden" width={w}>
          {/* Chat / cast transcript column */}
          <Box
            backgroundColor={C.windowBg}
            flexDirection="column"
            flexGrow={1}
            overflow="hidden"
            paddingX={2}
            paddingY={0}
          >
            <Box flexDirection="row" marginTop={0}>
              <Text color={C.dim}>{'$ '}</Text>
              <Text color={C.body}>merlin learn --from last-session</Text>
            </Box>
            <Box flexDirection="row" marginTop={0}>
              <Text color={C.green}>{'+ '}</Text>
              <Text bold color={C.bold}>
                skill windows-service-deploy
              </Text>
              <Text color={C.dim}>{'   3 rules captured'}</Text>
            </Box>
            <Box flexDirection="row" marginTop={0}>
              <Text color={C.green}>{'+ '}</Text>
              <Text bold color={C.bold}>
                memory fleet-update-doctrine
              </Text>
              <Text color={C.dim}>{'   global-first, verified'}</Text>
            </Box>
            <Box flexDirection="row" marginTop={0}>
              <Text color={C.amber}>{'- '}</Text>
              <Text bold color={C.bold}>
                eval suite
              </Text>
              <Text color={C.dim}>{'   14/14 → 16/16 green'}</Text>
            </Box>

            <Box height={1} />

            <Box flexDirection="row" marginTop={0}>
              <Text color={C.dim}>{'$ '}</Text>
              <Text color={C.body}>merlin fleet status</Text>
            </Box>

            {[
              ['node-01', '5m'],
              ['node-02', '7h'],
              ['edge-03', '4m']
            ].map(([name, age]) => (
              <Box flexDirection="row" justifyContent="space-between" key={name} marginTop={0} width={w - 4}>
                <Text color={C.nodeName}>{name}</Text>
                <Text>
                  <Text color={C.green}>online</Text>
                  <Text color={C.dim}>{` · ${age}`}</Text>
                </Text>
              </Box>
            ))}

            <Box flexDirection="row" marginTop={0}>
              <Text color={C.dim}>+ 2 more online</Text>
            </Box>

            <Box height={1} />

            <Box flexDirection="row" marginTop={0}>
              <Text color={C.dim}>{'$ '}</Text>
              <Box backgroundColor={C.cursor} height={1} width={1} />
            </Box>

            {typed.length > 0 ? (
              <Box flexDirection="column" marginTop={0}>
                <Text color={C.green}>{'● assistant'}</Text>
                <Box marginTop={0} width={w - 38}>
                  <Text color={C.body}>{typed}</Text>
                  <Text color={C.cursor}>▮</Text>
                </Box>
              </Box>
            ) : null}
          </Box>

          {/* Right sidebar: Scrying + Fleet */}
          <Box
            backgroundColor={C.windowBg}
            borderColor={C.border}
            borderStyle="single"
            flexDirection="column"
            marginRight={1}
            paddingX={1}
            paddingY={0}
            width={36}
          >
            <Text color={C.label}>✧━ ⟨ SCRYING ⟩ ━✧</Text>
            <Text color={C.dim}>{'→ checking fleet node-02 uptime 7h'}</Text>
            <Text color={C.dim}>{'→ comparing skill windows-service-deploy against eval suite'}</Text>
            <Text color={C.amber}>{'∴ 1 rule needs manual verify (service auto-start)'}</Text>

            <Box height={1} />

            <Text color={C.label}>✧━ ⟨ FLEET ⟩ ━✧</Text>
            {[
              ['node-01', '5m'],
              ['node-02', '7h'],
              ['edge-03', '4m']
            ].map(([name, age]) => (
              <Box flexDirection="row" justifyContent="space-between" key={name} marginTop={0} width={32}>
                <Text color={C.nodeName}>{name}</Text>
                <Text>
                  <Text color={C.green}>online</Text>
                  <Text color={C.dim}>{` · ${age}`}</Text>
                </Text>
              </Box>
            ))}
            <Box flexDirection="row" marginTop={0}>
              <Text color={C.dim}>+ 2 more online</Text>
            </Box>
          </Box>
        </Box>

        {/* Quick slots panel */}
        <Box
          backgroundColor={C.windowBg}
          borderColor={C.border}
          borderStyle="single"
          flexDirection="column"
          marginBottom={0}
          marginX={1}
          paddingX={1}
          paddingY={0}
        >
          <Text color={C.label}>✧━ ⟨ QUICK SLOTS ⟩ ━✧</Text>
          <Box flexDirection="row" justifyContent="space-between" marginTop={0} width={w - 6}>
            {[
              { k: '1', rune: 'ᛋ', name: 'web-search' },
              { k: '2', rune: 'ᛗ', name: 'code-exec' },
              { k: '3', rune: 'ᚠ', name: 'file-read' },
              { k: '4', rune: 'ᚦ', name: 'tools' }
            ].map(s => (
              <Box flexDirection="row" flexShrink={0} key={s.k}>
                <Text color={C.amber}>{`[${s.k}]`}</Text>
                <Text color={C.green}>{` ${s.rune} ${s.name}`}</Text>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Status bar */}
        <StatusRuleLine leftSegments={statusSegments} rightLabel="operator session" t={t} width={w} />

        {/* Process footer */}
        <Box
          backgroundColor={C.windowBg}
          flexDirection="row"
          justifyContent="space-between"
          paddingX={1}
          paddingY={0}
          width={w}
        >
          <Text color={t.color.muted}>Processes · 1 running · Ctrl+T expand · Ctrl+R collapse</Text>
          <Text color={t.color.ok}>?</Text>
        </Box>
      </Box>
    </Box>
  )
}
