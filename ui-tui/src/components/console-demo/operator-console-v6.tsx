import { Box, stringWidth, Text, useStdout } from '@merlin/ink'
import React, { useEffect, useState } from 'react'

// ── Arcane palette (mirrors merlin_arcane_agent_tui.html) ─────────────
const C: Record<string, string> = {
  obsidian: '#03080e',
  deep: '#071620',
  panel: '#091c28',
  border: '#1a384b',
  borderBright: '#0e7490',
  cyan: '#00f2fe',
  teal: '#2aa198',
  emerald: '#10b981',
  gold: '#eab308',
  amber: '#f59e0b',
  purple: '#a855f7',
  red: '#f43f5e',
  dim: '#335061',
  text: '#b2ccd6',
  bright: '#e2e8f0'
}

const RUNE_HEADER = 'ᚠ   ᛗ   ᛖ   ᚱ   ᛚ   ᛁ   ᚾ   ·   ᛖ   ᛈ   ᛁ   ᚾ   ᛟ   ᛁ   ᚨ       ᚺ   ᛟ   ᚱ   ᛁ   ᛉ   ᛟ   ᚾ'

const MERLIN_LOGO: string[] = [
  '███╗   ███╗ ███████╗ ██████╗  ██╗     ██╗ ███╗   ██╗',
  '████╗ ████║ ██╔════╝ ██╔══██╗ ██║     ██║ ████╗  ██║',
  '██╔████╔██║ █████╗   ██████╔╝ ██║     ██║ ██╔██╗ ██║',
  '██║╚██╔╝██║ ██╔══╝   ██╔══██╗ ██║     ██║ ██║╚██╗██║',
  '██║ ╚═╝ ██║ ███████╗ ██║  ██║ ███████╗██║ ██║ ╚████║',
  '╚═╝     ╚═╝ ╚══════╝ ╚═╝  ╚═╝ ╚══════╝╚═╝ ╚═╝  ╚═══╝'
]

const FULL_REPLY = "Summarize what's in this folder"

// Truncate s to display width `maxW` with ellipsis.
function clip(s: string, maxW: number): string {
  if (stringWidth(s) <= maxW) {
    return s
  }

  let w = 0
  let out = ''

  for (const ch of s) {
    const cw = stringWidth(ch)

    if (w + cw > maxW - 1) {
      break
    }

    w += cw
    out += ch
  }

  return out + '…'
}

// Left + right labels on one row; the right side truncates natively via
// flexbox (no manual padding math — Ink clips it, can't overflow the frame).
function PairRow({
  avail,
  left,
  right,
  lc = C.text,
  rc = C.dim
}: {
  avail: number
  left: string
  right: string
  lc?: string
  rc?: string
}) {
  const leftW = Math.min(stringWidth(left), avail - 8)
  const rightW = Math.max(4, avail - leftW - 4)

  return (
    <Box flexDirection="row" height={1} width={avail}>
      <Box flexShrink={0} overflow="hidden" width={leftW}>
        <Text color={lc} wrap="truncate-end">
          {left}
        </Text>
      </Box>
      <Box flexGrow={1} flexShrink={1} overflow="hidden">
        <Text color={rc} wrap="truncate-end">
          {'    '}
          {right}
        </Text>
      </Box>
    </Box>
  )
}

// Full-width single line: array of [color, text] segments, clipped as one
// string with ellipsis at exactly `avail` — no wrap, no overflow ever.
type Seg = [string, string]

function clipSegs(segs: Seg[], maxW: number): Seg[] {
  const full = segs.map(([, t]) => t).join('')

  if (stringWidth(full) <= maxW) {
    return segs
  }

  let budget = maxW - 1
  const out: Seg[] = []

  for (const [c, t] of segs) {
    if (budget <= 0) {
      break
    }

    let w = 0
    let s = ''

    for (const ch of t) {
      const cw = stringWidth(ch)

      if (w + cw > budget) {
        break
      }

      w += cw
      s += ch
    }

    budget -= w
    out.push([c, s])
  }

  out.push([C.dim, '…'])

  return out
}

function Line({ avail, segs }: { avail: number; segs: Seg[] }) {
  const shown = clipSegs(segs, avail)

  return (
    <Box height={1} overflow="hidden" width={avail}>
      <Text wrap="truncate-end">
        {shown.map(([c, t], i) => (
          <Text color={c} key={i}>
            {t}
          </Text>
        ))}
      </Text>
    </Box>
  )
}

function Panel({ width, children }: { width: number; children: React.ReactNode }) {
  // `width` is the CONTENT width; +4 covers border (2) + padding (2).
  return (
    <Box
      borderColor={C.border}
      borderStyle="round"
      flexDirection="column"
      flexShrink={0}
      paddingX={1}
      width={width + 4}
    >
      {children}
    </Box>
  )
}

export function OperatorConsoleV6() {
  const { stdout } = useStdout()
  const cols = stdout ? stdout.columns : 100
  const rows = stdout ? stdout.rows : 30

  const colsEnv = Number(process.env.MERLIN_DEMO_COLS || 0)
  const rowsEnv = Number(process.env.MERLIN_DEMO_ROWS || 0)
  const realCols = colsEnv > 0 ? colsEnv : cols
  const realRows = rowsEnv > 0 ? rowsEnv : rows

  // Never touch the terminal's last column (pending-wrap shatters borders).
  const W = Math.max(60, realCols - 1)
  const H = Math.max(8, realRows)
  const inner = W - 4 // outer border + padding
  const avail = inner - 2 // inside panel padding

  const [mana, setMana] = useState(60)
  const [tick, setTick] = useState(0)
  const [typed, setTyped] = useState('')

  useEffect(() => {
    const t1 = setInterval(() => setTick(n => n + 1), 1000)
    const t2 = setInterval(() => setMana(p => (p >= 95 ? 20 : p + 2)), 900)

    return () => {
      clearInterval(t1)
      clearInterval(t2)
    }
  }, [])

  useEffect(() => {
    if (typed.length >= FULL_REPLY.length) {
      const r = setTimeout(() => setTyped(''), 3000)

      return () => clearTimeout(r)
    }

    const t = setTimeout(() => setTyped(FULL_REPLY.slice(0, typed.length + 1)), 100)

    return () => clearTimeout(t)
  }, [typed])

  const filled = Math.round((mana / 100) * 16)
  const manaBar = '█'.repeat(filled) + '░'.repeat(16 - filled)
  const manaState = mana < 30 ? 'CRITICAL' : mana < 60 ? 'DRAINING' : 'OPTIMAL'
  const manaStateColor = mana < 30 ? C.red : mana < 60 ? C.amber : C.emerald

  const wide = inner >= 92
  const full = H >= 28
  const mid = H >= 14

  /* ── Header bar ── */
  const headerRow = (
    <PairRow
      avail={avail}
      lc={C.cyan}
      left="● ● ● MERLIN // ARCANE TERMINAL SYSTEM · EPINOIA HORIZON KERNEL v2.7"
      rc={C.purple}
      right="SFX: ON · CRT: ON · [/] Runes Grimoire"
    />
  )

  const runeRow = (
    <Box height={1} overflow="hidden" width={avail}>
      <Text color={C.cyan} wrap="truncate-end">
        {RUNE_HEADER}
      </Text>
    </Box>
  )

  /* ── Logo + telemetry block ── */
  const logoBlock = (
    <Box flexDirection="row" width={avail}>
      <Box flexDirection="column" width={52}>
        {MERLIN_LOGO.map((line, i) => (
          <Text color={i < 3 ? C.cyan : C.dim} key={i} wrap="truncate-end">
            {line}
          </Text>
        ))}
      </Box>
      <Panel width={avail - 56}>
        <PairRow avail={avail - 56} lc={C.cyan} left="✧ RUNIC HARNESS : ONLINE" rc={C.emerald} right="6/6 NODES SYNC" />
        <Line avail={avail - 56} segs={[[C.dim, 'ᛞ SHA: d274c22.dirty  ᛟ VER: 2026.9.24-apx']]} />
        <Line
          avail={avail - 56}
          segs={[
            [C.text, 'ᚨ REALM: '],
            [C.amber, 'LOCAL SCRATCH'],
            [C.text, '  ᛝ TIER: '],
            [C.purple, 'APEX MASTER']
          ]}
        />
        <Line
          avail={avail - 56}
          segs={[
            [C.dim, 'HOST: '],
            [C.cyan, 'EPINOIA-NODE-01'],
            [C.dim, '  UPTIME: '],
            [C.emerald, `${112875 + tick}s`]
          ]}
        />
      </Panel>
    </Box>
  )

  /* ── Arsenal panel ── */
  const arsenalPanel = (
    <Panel width={avail - 2}>
      <PairRow
        avail={avail - 2}
        lc={C.cyan}
        left="✧━ ⟨ ARSENAL & CIPHERS ⟩"
        rc={C.dim}
        right="[CACHE BUFFER: 20,000 CHARS ACTIVE]"
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.emerald, '● ENGINE CORE: '],
          [C.cyan, 'clario/gpt-6-sol'],
          [C.text, ' · 25 Tools Armed & Binded · Provider: Custom Arcane Bridge']
        ]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.cyan, '● ACTIVE RUNES: '],
          [C.text, 'browser · clarify · code_execution · computer_use · sys_inspect · connections · +12 deep runes']
        ]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.amber, '● SKILL GRIMOIRE: '],
          [C.text, '[ᛋ systematic-debugging] [ᚷ github] [ᛗ doc-to-actions] [ᛏ weekly-review]']
        ]}
      />
    </Panel>
  )

  /* ── Spellbook panel ── */
  const spellbookPanel = (
    <Panel avail={avail}>
      <PairRow
        avail={avail - 2}
        lc={C.purple}
        left="✧━ ⟨ SPELLBOOK STATUS ⟩ ━✧"
        rc={C.cyan}
        right="HARNESS: IDLE · 42ms"
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.cyan, 'ᛟ Incantation: '],
          [C.bright, 'clario/gpt-6-sol'],
          [C.dim, '   ᛞ Runes State: '],
          [C.emerald, 'grimoire loaded (100%)'],
          [C.dim, '   ᛝ Response Aura: '],
          [C.text, `idle · last ⏲ ${tick}s`]
        ]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.cyan, 'ᚨ MANA QUOTA: '],
          [C.cyan, `[${manaBar}]`],
          [C.bright, ` ${mana}% `],
          [manaStateColor, `[${manaState}]`]
        ]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.amber, 'ᚨ QUICK SLOTS: '],
          [
            C.text,
            '[1] ᛋ web-search  [2] ᛗ code-exec  [3] ᚠ file-read  [4] ᚦ tools  [5] ᛟ mem-sync  [6] ᚱ fleet-trace  [7] ᛞ raw-terminal  [8] ᛝ recharge-mana'
          ]
        ]}
      />
    </Panel>
  )

  /* ── Daemon panel ── */
  const daemonPanel = (
    <Panel avail={avail}>
      <PairRow
        avail={avail - 2}
        lc={C.emerald}
        left="⚙ DAEMON SUBPROCESSES:  [1 RUNNING]"
        rc={C.cyan}
        right="[Ctrl+T] Expand · [Ctrl+R] Collapse"
      />
      <Line
        avail={avail - 2}
        segs={[[C.text, `⚙ PID 40912 · astro preview · Status: online · port 4321 · uptime ${112875 + tick}s`]]}
      />
      <Line avail={avail - 2} segs={[[C.dim, '[astro:server] ready in 412ms  ➜  Local: http://127.0.0.1:4321/']]} />
    </Panel>
  )

  /* ── Scroll (transcript) panel ── */
  const scrollPanel = (
    <Panel avail={avail}>
      <PairRow avail={avail - 2} lc={C.cyan} left="📜 SPELLCAST HISTORICAL SCROLL" rc={C.dim} right="[CLEAR SCROLL]" />
      <Line
        avail={avail - 2}
        segs={[[C.dim, '✦ Epinoia Horizon arcane engine connected. Type a spell query or select quick slots.']]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.cyan, 'ᛟ cast ❯ '],
          [C.bright, 'Explain this error and how to fix it']
        ]}
      />
      <Line avail={avail - 2} segs={[[C.emerald, '✧ [clario/gpt-6-sol] Synthesizing rune diagnosis:']]} />
      <Line
        avail={avail - 2}
        segs={[
          [
            C.text,
            'Error in Astro preview daemon: Port 4321 is bound by active daemon PID 40912. The preview server responded with 200 OK across loopback.'
          ]
        ]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [C.amber, 'FIX: '],
          [C.text, 'Terminate lingering daemon with kill -9 40912 or invoke slot [4] tools banish.']
        ]}
      />
      <Line
        avail={avail - 2}
        segs={[
          [
            C.dim,
            'Suggested spells: "Summarize what\'s in this folder" · "Refactor auth middleware to rust" · "Audit smart contract gas"'
          ]
        ]}
      />
    </Panel>
  )

  /* ── Command bar ── */
  const commandBar = (
    <Box borderColor={C.borderBright} borderStyle="round" flexDirection="row" paddingX={1} width={avail}>
      <Text color={C.purple}>ᛟ </Text>
      <Text bold color={C.cyan}>
        cast
      </Text>
      <Text color={C.emerald}> ❯ </Text>
      <Text color={C.bright}>{typed}</Text>
      <Text color={C.cyan}>▮</Text>
    </Box>
  )

  /* ── Strip modes for short terminals ── */
  if (!mid) {
    return (
      <Box
        backgroundColor={C.obsidian}
        borderColor={C.border}
        borderStyle="round"
        flexDirection="column"
        height={H}
        paddingX={1}
        paddingY={0}
        width={W}
      >
        {runeRow}
        <Box height={1} width={avail}>
          <Text color={C.border}>{'─'.repeat(avail)}</Text>
        </Box>
        <PairRow
          avail={avail}
          lc={C.purple}
          left="✧━ ⟨ SPELLBOOK STATUS ⟩ ━✧"
          rc={C.dim}
          right="[ESC] banish ─ [/] runes ─ [CTRL+C] exit"
        />
        <Line
          avail={avail}
          segs={[
            [C.cyan, 'ᛟ Incantation: '],
            [C.bright, 'clario/gpt-6-sol'],
            [C.dim, '   ᛞ Runes State: '],
            [C.emerald, 'grimoire loaded']
          ]}
        />
        <Line
          avail={avail}
          segs={[
            [C.cyan, 'ᚨ MANA QUOTA: '],
            [C.cyan, `[${manaBar}]`],
            [C.bright, ` ${mana}% `],
            [manaStateColor, `[${manaState}]`],
            [C.dim, `   ᛝ Aura: idle · ${tick}s`]
          ]}
        />
        <Box flexGrow={1} />
        {commandBar}
      </Box>
    )
  }

  /* ── Mid mode: header + panels, no logo/telemetry side-by-side ── */
  if (!full) {
    return (
      <Box
        backgroundColor={C.obsidian}
        borderColor={C.border}
        borderStyle="round"
        flexDirection="column"
        height={H}
        paddingX={1}
        paddingY={0}
        width={W}
      >
        {headerRow}
        {runeRow}
        {arsenalPanel}
        {spellbookPanel}
        {daemonPanel}
        <Box flexGrow={1} />
        {commandBar}
      </Box>
    )
  }

  /* ── Full mode ── */
  return (
    <Box
      backgroundColor={C.obsidian}
      borderColor={C.border}
      borderStyle="round"
      flexDirection="column"
      height={H}
      paddingX={1}
      paddingY={0}
      width={W}
    >
      {headerRow}
      {runeRow}
      {wide && logoBlock}
      {arsenalPanel}
      {spellbookPanel}
      {daemonPanel}
      <Box flexDirection="column" flexGrow={1} minHeight={6}>
        {scrollPanel}
      </Box>
      {commandBar}
    </Box>
  )
}
