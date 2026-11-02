import React, { useState, useEffect } from "react";
import { Box, Text, useStdout } from "@merlin/ink";

const C: Record<string, string> = {
  bg: "#0A0F14",
  panel: "#0D141C",
  border: "#1C2A36",
  divider: "#152230",
  dim: "#4E5F6B",
  label: "#5A6B77",
  body: "#8296A5",
  bold: "#E8EFF3",
  green: "#38D996",
  amber: "#E4B45C",
  cyan: "#2DD4BF",
  cursor: "#4E7D8C",
};

const RUNE_HEADER =
  "ᚠ   ᛗ   ᛖ   ᚱ   ᛚ   ᛁ   ᚾ   ·   ᛖ   ᛈ   ᛁ   ᚾ   ᛟ   ᛁ   ᚨ       ᚺ   ᛟ   ᚱ   ᛁ   ᛉ   ᛟ   ᚾ";

const MERLIN_LOGO: string[] = [
  "███╗   ███╗ ███████╗ ██████╗  ██╗     ██╗ ███╗   ██╗",
  "████╗ ████║ ██╔════╝ ██╔══██╗ ██║     ██║ ████╗  ██║",
  "██╔████╔██║ █████╗   ██████╔╝ ██║     ██║ ██╔██╗ ██║",
  "██║╚██╔╝██║ ██╔══╝   ██╔══██╗ ██║     ██║ ██║╚██╗██║",
  "██║ ╚═╝ ██║ ███████╗ ██║  ██║ ███████╗██║ ██║ ╚████║",
  "╚═╝     ╚═╝ ╚══════╝ ╚═╝  ╚═╝ ╚══════╝╚═╝ ╚═╝  ╚═══╝",
];

const FULL_REPLY = "Summarize what's in this folder";

function HRule({ w }: { w: number }) {
  return (
    <Box height={1} width={w}>
      <Text color={C.divider}>{"─".repeat(Math.max(0, w))}</Text>
    </Box>
  );
}

// Two-column row: renders children pairs side by side only when each half
// really fits; otherwise stacks vertically. Ink flexWrap mangles borders.
function SpellRow({ inner, children }: { inner: number; children: React.ReactNode[] }) {
  const [a, b, c, d] = children;
  const colW = Math.floor((inner - 2) / 2);

  if (colW < 46) {
    return (
      <Box flexDirection="column" width={inner - 2}>
        <Box flexDirection="row">
          {a}
          {b}
        </Box>
        <Box flexDirection="row">
          {c}
          {d}
        </Box>
      </Box>
    );
  }

  return (
    <Box flexDirection="row" width={inner - 2}>
      <Box flexDirection="row" width={colW}>
        {a}
        {b}
      </Box>
      <Box flexDirection="row" width={colW}>
        {c}
        {d}
      </Box>
    </Box>
  );
}

export function OperatorConsoleV4() {
  const { stdout } = useStdout();
  const cols = stdout ? stdout.columns : 100;
  const rows = stdout ? stdout.rows : 30;

  // Never render into the terminal's last column: a line ending exactly on
  // the last column triggers pending-wrap and shatters the right border.
  const W = Math.max(60, cols - 1);
  const H = Math.max(24, rows);
  const inner = W - 4; // outer border (2) + paddingX (1+1)

  const wide = inner >= 92;
  const logoW = wide ? 52 : 0;
  const infoW = wide ? inner - logoW : inner;

  const [mana, setMana] = useState(60);
  const [tick, setTick] = useState(0);
  const [typed, setTyped] = useState("");

  useEffect(() => {
    const t1 = setInterval(() => setTick((n) => n + 1), 1000);
    const t2 = setInterval(() => setMana((p) => (p >= 95 ? 20 : p + 2)), 900);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
  }, []);

  useEffect(() => {
    if (typed.length >= FULL_REPLY.length) {
      const r = setTimeout(() => setTyped(""), 3000);
      return () => clearTimeout(r);
    }
    const t = setTimeout(() => setTyped(FULL_REPLY.slice(0, typed.length + 1)), 100);
    return () => clearTimeout(t);
  }, [typed]);

  const filled = Math.round((mana / 100) * 16);
  const manaBar = "█".repeat(filled) + "░".repeat(16 - filled);

  return (
    <Box
      width={W}
      height={H}
      borderStyle="round"
      borderColor={C.border}
      backgroundColor={C.panel}
      flexDirection="column"
      paddingX={1}
      paddingY={0}
    >
      {/* Rune header */}
      <Box height={1} overflow="hidden" width={inner}>
        <Text color={C.dim} wrap="truncate-end">
          {RUNE_HEADER}
        </Text>
      </Box>

      <HRule w={inner} />

      {/* Logo + info panel */}
      <Box flexDirection="row" width={inner}>
        {wide && (
          <Box flexDirection="column" width={logoW}>
            {MERLIN_LOGO.map((line, i) => (
              <Text key={i} color={i < 3 ? C.cyan : C.dim} wrap="truncate-end">
                {line}
              </Text>
            ))}
          </Box>
        )}

        <Box
          borderStyle="round"
          borderColor={C.border}
          paddingX={1}
          paddingY={0}
          flexDirection="column"
          width={infoW}
        >
          <Text color={C.green}>✧ RUNIC HARNESS : ONLINE  [6/6 NODES SYNC]</Text>
          <Text color={C.label}>ᛞ SHA: d274c22 · v0.0.0+48.dirty · 2026.09</Text>
          <Text color={C.label}>ᛟ TIER: APEX MASTER · REALM: LOCAL SCRATCH</Text>
          <Text color={C.label}>ᛝ HOST: EPINOIA-NODE-01 · UPTIME: {112900 + tick}s</Text>
        </Box>
      </Box>

      <HRule w={inner} />

      {/* Arsenal */}
      <Box
        borderStyle="round"
        borderColor={C.border}
        flexDirection="column"
        paddingX={1}
        paddingY={0}
        width={inner}
      >
        <Text color={C.label}>✧━ ⟨ ARSENAL & CIPHERS ⟩</Text>
        <Text color={C.body}>● ENGINE CORE :: clario/gpt-6-sol [Custom Bridge] · 25 Tools Armed</Text>
        <Text color={C.body}>
          ● ACTIVE RUNES :: browser · clarify · code_execution · computer_use · sys_inspect … (+12 deep)
        </Text>
        <Text color={C.body}>
          ● SKILL GRIMOIRE :: [ᛋ systematic-debugging] [ᚷ github] [ᛗ doc-to-actions] [ᛏ weekly-review]
        </Text>
        <Text color={C.body}>● BUFFER LIMIT :: 20,000 chars [Head/Tail Truncation: ACTIVE]</Text>
      </Box>

      {/* Daemon subprocesses */}
      <Box
        borderStyle="round"
        borderColor={C.border}
        flexDirection="column"
        paddingX={1}
        paddingY={0}
        width={inner}
      >
        <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
          <Text color={C.label}>✧━ ⟨ DAEMON SUBPROCESSES ⟩</Text>
          <Text color={C.dim}>1 active ─ [Ctrl+T] expand ─ [Ctrl+R] fold</Text>
        </Box>
        <Text color={C.body}>⚙ PID 40912 · astro preview</Text>
        <Text color={C.dim}>
          └─ cd ".../merlin/cache/scratch/wm-dashboard" && npx astro preview --port 4321
        </Text>
      </Box>

      {/* Spellbook status + quick slots */}
      <Box
        borderStyle="round"
        borderColor={C.border}
        flexDirection="column"
        paddingX={1}
        paddingY={0}
        width={inner}
      >
        <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
          <Text color={C.label}>✧━ ⟨ SPELLBOOK STATUS ⟩</Text>
          <Text color={C.dim}>[ESC] banish ─ [/] runes ─ [CTRL+C] exit</Text>
        </Box>

        <SpellRow inner={inner}>
          <Text color={C.body}>ᛟ INCANTATION ── </Text>
          <Text color={C.bold}>clario/gpt-6-sol</Text>
          <Text color={C.body}>ᛞ FOCUS LEVEL ── </Text>
          <Text color={C.body}>[ HIGH · THREE-TIER DEPTH ]</Text>
        </SpellRow>

        <SpellRow inner={inner}>
          <Text color={C.body}>ᚨ MANA QUOTA ── [</Text>
          <Text color={C.cyan}>{manaBar}</Text>
          <Text color={C.body}>] {mana}%</Text>
          <Text color={C.body}>ᛝ HARNESS LATENCY ── </Text>
          <Text color={C.body}>42ms · state: idle</Text>
        </SpellRow>

        <Text color={C.amber}>ᚨ QUICK SLOTS</Text>
        {wide ? (
          <>
            <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
              <Text color={C.body}>[1] ᛋ web-search</Text>
              <Text color={C.body}>[2] ᛗ code-exec</Text>
              <Text color={C.body}>[3] ᚠ file-read</Text>
              <Text color={C.body}>[4] ᚦ custom-tools</Text>
            </Box>
            <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
              <Text color={C.body}>[5] ᛟ mem-sync</Text>
              <Text color={C.body}>[6] ᚱ fleet-trace</Text>
              <Text color={C.body}>[7] ᛞ raw-terminal</Text>
              <Text color={C.body}>[8] ᛝ clear-mana</Text>
            </Box>
          </>
        ) : (
          <Text color={C.body}>[1] ᛋ web-search  [2] ᛗ code-exec  [3] ᚠ file-read  [4] ᚦ custom-tools</Text>
        )}
      </Box>

      {/* Transcript fills the remaining height */}
      <Box
        borderStyle="round"
        borderColor={C.border}
        flexDirection="column"
        paddingX={1}
        paddingY={0}
        flexGrow={1}
        overflow="hidden"
        width={inner}
      >
        <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
          <Text color={C.label}>✧━ ⟨ CAST ⟩ ━✧</Text>
          <Text color={C.dim}>session · operator</Text>
        </Box>

        <Box flexDirection="row">
          <Text color={C.dim}>$ </Text>
          <Text color={C.body}>merlin learn --from last-session</Text>
        </Box>
        <Box flexDirection="row">
          <Text color={C.green}>+ </Text>
          <Text bold color={C.bold}>
            skill windows-service-deploy
          </Text>
          <Text color={C.dim}>   3 rules captured</Text>
        </Box>
        <Box flexDirection="row">
          <Text color={C.green}>+ </Text>
          <Text bold color={C.bold}>
            memory fleet-update-doctrine
          </Text>
          <Text color={C.dim}>   global-first, verified</Text>
        </Box>
        <Box flexDirection="row">
          <Text color="#ff4d6d">- </Text>
          <Text bold color={C.bold}>
            eval suite
          </Text>
          <Text color={C.dim}>   14/14 → 16/16 green</Text>
        </Box>

        <Box flexDirection="row">
          <Text color={C.dim}>$ </Text>
          <Text color={C.body}>merlin fleet status</Text>
        </Box>
        {[
          ["node-01", "online · 5m"],
          ["node-02", "online · 7h"],
          ["edge-03", "online · 4m"],
        ].map(([name, status]) => (
          <Box key={name} flexDirection="row">
            <Text color={C.body}>{`  ${name}`}</Text>
            <Text color={C.dim}>{"  "}</Text>
            <Text color={C.green}>{status}</Text>
          </Box>
        ))}
        <Text color={C.dim}>  + 2 more online</Text>

        <Box flexDirection="row">
          <Text color={C.dim}>$ </Text>
          <Box width={1} height={1} backgroundColor={C.cursor} />
        </Box>

        {typed.length > 0 && (
          <Box flexDirection="column">
            <Text color={C.green}>● assistant</Text>
            <Text color={C.body}>
              {typed}
              <Text color={C.cursor}>▮</Text>
            </Text>
          </Box>
        )}
      </Box>

      {/* Command bar */}
      <Box
        borderStyle="round"
        borderColor={C.border}
        flexDirection="row"
        paddingX={1}
        paddingY={0}
        width={inner}
      >
        <Text color={C.amber}>cast ❯</Text>
        <Text color={C.bold}> {typed}</Text>
        <Text color={C.cursor}>▮</Text>
      </Box>
    </Box>
  );
}
