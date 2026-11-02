import React, { useMemo, useState, useEffect } from "react";
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
  purple: "#9D7BFF",
  cursor: "#4E7D8C",
};

const WIDTH = 124;

const RUNE_HEADER = "ᚠ   ᛗ   ᛖ   ᚱ   ᛚ   ᛁ   ᚾ   ·   ᛖ   ᛈ   ᛁ   ᚾ   ᛟ   ᛁ   ᚨ       ᚺ   ᛟ   ᚱ   ᛁ   ᛉ   ᛟ   ᚾ";

const MERLIN_LOGO: string[] = [
  "██████╗ ███████╗ ██████╗  ██╗     ██╗ ███╗   ██╗",
  "██╔══██╗██╔════╝ ██╔══██╗ ██║     ██║ ████╗  ██║",
  "██████╔╝█████╗   ██████╔╝ ██║     ██║ ██╔██╗ ██║",
  "██╔══██╗██╔══╝   ██╔══██╗ ██║     ██║ ██║╚██╗██║",
  "██║  ██║███████╗ ██║  ██║ ███████╗██║ ██║ ╚████║",
  "╚═╝  ╚═╝╚══════╝ ╚═╝  ╚═╝ ╚══════╝╚═╝ ╚═╝  ╚═══╝",
];

function HRule({ w, color = C.divider }: { w: number; color?: string }) {
  return (
    <Box height={1} width={w}>
      <Text color={color}>{"─".repeat(w)}</Text>
    </Box>
  );
}

export function OperatorConsoleV3() {
  const { stdout } = useStdout();
  const width = stdout ? stdout.columns : WIDTH;
  const w = Math.min(WIDTH, Math.max(100, width - 4));
  const h = stdout ? stdout.rows : 32;

  const [mana, setMana] = useState(60);
  const [tick, setTick] = useState(0);
  const [typed, setTyped] = useState("");
  const fullReply = "Summarize what's in this folder";

  useEffect(() => {
    const t1 = setInterval(() => setTick((n) => n + 1), 1000);
    const t2 = setInterval(() => setMana((p) => (p >= 95 ? 20 : p + 2)), 900);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
  }, []);

  useEffect(() => {
    if (typed.length >= fullReply.length) {
      const r = setTimeout(() => setTyped(""), 3000);
      return () => clearTimeout(r);
    }
    const t = setTimeout(() => setTyped(fullReply.slice(0, typed.length + 1)), 120);
    return () => clearTimeout(t);
  }, [typed]);

  const filled = Math.round((mana / 100) * 16);
  const manaBar = "█".repeat(filled) + "░".repeat(16 - filled);

  return (
    <Box width={width} height={h} backgroundColor={C.bg} paddingX={1} paddingY={1}>
      <Box
        width={w}
        height={h - 2}
        borderStyle="round"
        borderColor={C.border}
        backgroundColor={C.panel}
        flexDirection="column"
        paddingX={1}
        paddingY={0}
      >
        {/* Rune header */}
        <Box height={1} overflow="hidden" width={w - 2}>
          <Text color={C.dim}>{RUNE_HEADER}</Text>
        </Box>

        <HRule w={w - 2} />

        {/* Logo + info panel */}
        <Box flexDirection="row" width={w - 2} marginY={0}>
          <Box flexDirection="column" width={54}>
            {MERLIN_LOGO.map((line, i) => (
              <Text key={i} color={i < 3 ? C.cyan : C.dim} wrap="truncate-end">
                {line}
              </Text>
            ))}
          </Box>

          <Box flexDirection="column" width={w - 56}>
            <Box borderStyle="round" borderColor={C.border} paddingX={1} paddingY={0} flexDirection="column">
              <Text color={C.green}>✧ RUNIC HARNESS : ONLINE  [6/6 NODES SYNC]</Text>
              <Text color={C.label}>ᛞ SHA: d274c22 · v0.0.0+48.dirty · 2026.09</Text>
              <Text color={C.label}>ᛟ TIER: APEX MASTER · REALM: LOCAL SCRATCH</Text>
              <Text color={C.label}>ᛝ HOST: EPINOIA-NODE-01 · UPTIME: {112875 + tick}s</Text>
            </Box>
          </Box>
        </Box>

        <HRule w={w - 2} />

        {/* Arsenal */}
        <Box borderStyle="round" borderColor={C.border} flexDirection="column" paddingX={1} paddingY={0} marginY={0}>
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

        {/* Spellbook status + quick slots */}
        <Box borderStyle="round" borderColor={C.border} flexDirection="column" paddingX={1} paddingY={0} marginY={0}>
          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            <Text color={C.label}>✧━ ⟨ SPELLBOOK STATUS ⟩</Text>
            <Text color={C.dim}>[ESC] banish ─ [/] runes ─ [CTRL+C] exit</Text>
          </Box>

          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            <Text color={C.body}>ᛟ INCANTATION ── clario/gpt-6-sol</Text>
            <Text color={C.body}>ᛞ FOCUS LEVEL ── [ HIGH · THREE-TIER DEPTH ]</Text>
          </Box>

          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            <Text color={C.body}>
              ᚨ MANA QUOTA ── [<Text color={C.cyan}>{manaBar}</Text>] {mana}%
            </Text>
            <Text color={C.body}>ᛝ HARNESS LATENCY ── 42ms · state: idle</Text>
          </Box>

          <Box height={1} />

          <Text color={C.amber}>ᚨ QUICK SLOTS</Text>
          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            {[
              "[1] ᛋ web-search",
              "[2] ᛗ code-exec",
              "[3] ᚠ file-read",
              "[4] ᚦ custom-tools",
            ].map((s) => (
              <Text key={s} color={C.body}>{s}</Text>
            ))}
          </Box>
          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            {[
              "[5] ᛟ mem-sync",
              "[6] ᚱ fleet-trace",
              "[7] ᛞ raw-terminal",
              "[8] ᛝ clear-mana",
            ].map((s) => (
              <Text key={s} color={C.body}>{s}</Text>
            ))}
          </Box>
        </Box>

        {/* Daemon subprocesses */}
        <Box borderStyle="round" borderColor={C.border} flexDirection="column" paddingX={1} paddingY={0} marginY={0}>
          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            <Text color={C.label}>✧━ ⟨ DAEMON SUBPROCESSES ⟩</Text>
            <Text color={C.dim}>1 active ─ [Ctrl+T] expand ─ [Ctrl+R] fold</Text>
          </Box>
          <Text color={C.body}>⚙ PID 40912 · astro preview</Text>
          <Text color={C.dim}>└─ cd ".../merlin/cache/scratch/wm-dashboard" && npx astro preview --port 4321</Text>
        </Box>

        <Box flexGrow={1} />

        {/* Command bar */}
        <Box borderStyle="round" borderColor={C.border} flexDirection="row" paddingX={1} paddingY={0}>
          <Text color={C.amber}>cast ❯</Text>
          <Text color={C.bold}> {typed}</Text>
          <Text color={C.cursor}>▮</Text>
        </Box>
      </Box>
    </Box>
  );
}
