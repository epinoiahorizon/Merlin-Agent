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

function stringWidth(s: string): number {
  let w = 0;
  for (const ch of s) {
    const code = ch.codePointAt(0) || 0;
    w += code > 0x24ff ? 2 : 1;
  }
  return w;
}

function HRule({ w }: { w: number }) {
  return (
    <Box height={1} width={w}>
      <Text color={C.divider}>{"─".repeat(Math.max(0, w))}</Text>
    </Box>
  );
}

// One row holding a left and right label, rendered as a single pre-padded
// string. Always exactly one row: if it doesn't fit, the right label is
// truncated with "…" — never stack, never wrap (that's what overlapped
// rows in earlier builds).
function PairRow({ inner, left, right, lc = C.body, rc = C.body }: { inner: number; left: string; right: string; lc?: string; rc?: string }) {
  const avail = inner - 2;
  const lw = stringWidth(left);
  const fits = lw + stringWidth(right) + 4 <= avail;

  let rightShown = right;
  if (!fits) {
    const budget = Math.max(3, avail - lw - 4);
    let w = 0;
    let cut = 0;
    for (const ch of right) {
      const cw = ch.codePointAt(0) && ch.codePointAt(0) > 0x24ff ? 2 : 1;
      if (w + cw > budget) break;
      w += cw;
      cut++;
    }
    rightShown = right.slice(0, cut) + "…";
  }

  const pad = Math.max(1, avail - lw - stringWidth(rightShown));
  return (
    <Box height={1} width={avail}>
      <Text color={lc}>
        {left}
        {" ".repeat(pad)}
        <Text color={rc}>{rightShown}</Text>
      </Text>
    </Box>
  );
}

// Evenly spaced slot row, computed as one padded string per row.
function SlotRow({ inner, items }: { inner: number; items: string[] }) {
  const avail = inner - 2;
  const slotW = Math.floor(avail / items.length);
  const line = items.map((s) => (s + " ".repeat(slotW)).slice(0, slotW)).join("");
  return (
    <Box height={1} width={avail}>
      <Text color={C.body}>{line}</Text>
    </Box>
  );
}

export function OperatorConsoleV5() {
  const { stdout } = useStdout();
  const cols = stdout ? stdout.columns : 100;
  const rows = stdout ? stdout.rows : 30;

  // Dev/test override so narrow pipes and small PTYs can exercise both modes.
  const colsEnv = Number(process.env.MERLIN_DEMO_COLS || 0);
  const rowsEnv = Number(process.env.MERLIN_DEMO_ROWS || 0);
  const realCols = colsEnv > 0 ? colsEnv : cols;
  const realRows = rowsEnv > 0 ? rowsEnv : rows;

  // Never render into the terminal's last column (pending-wrap shatters
  // the right border). Compact mode for short windows.
  const W = Math.max(60, realCols - 1);
  const H = Math.max(8, realRows);
  const inner = W - 4; // outer border (2) + paddingX (1+1)
  const compact = H < 16;

  const wide = !compact && inner >= 92;
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
  const manaLeft = `ᚨ MANA QUOTA ── [${manaBar}] ${mana}%`;
  const latencyRight = "ᛝ HARNESS LATENCY ── 42ms · state: idle";
  const incantLeft = "ᛟ INCANTATION ── clario/gpt-6-sol";
  const focusRight = "ᛞ FOCUS LEVEL ── [ HIGH · THREE-TIER DEPTH ]";

  const slots1 = ["[1] ᛋ web-search", "[2] ᛗ code-exec", "[3] ᚠ file-read", "[4] ᚦ custom-tools"];
  const slots2 = ["[5] ᛟ mem-sync", "[6] ᚱ fleet-trace", "[7] ᛞ raw-terminal", "[8] ᛝ clear-mana"];

  /* ── STRIP MODE (short terminal): adaptive, never overflows height ── */
  if (compact) {
    const B = H - 2; // content rows available inside the outer border
    const showSlots1 = B >= 8;
    const showSlots2 = B >= 9;
    const showDaemon = B >= 8;
    const castBordered = B >= 11;

    const castBar = castBordered ? (
      <Box borderStyle="round" borderColor={C.border} flexDirection="row" paddingX={1} width={inner}>
        <Text color={C.amber}>cast ❯</Text>
        <Text color={C.bold}> {typed}</Text>
        <Text color={C.cursor}>▮</Text>
      </Box>
    ) : (
      <Box height={1} width={inner}>
        <Text>
          <Text color={C.amber}>cast ❯</Text>
          <Text color={C.bold}> {typed}</Text>
          <Text color={C.cursor}>▮</Text>
        </Text>
      </Box>
    );

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
        <Box height={1} overflow="hidden" width={inner}>
          <Text color={C.dim} wrap="truncate-end">
            {RUNE_HEADER}
          </Text>
        </Box>

        <HRule w={inner} />

        <Box flexDirection="row" justifyContent="space-between" width={inner}>
          <Text color={C.label}>✧━ ⟨ SPELLBOOK STATUS ⟩</Text>
          <Text color={C.dim}>[ESC] banish ─ [/] runes ─ [CTRL+C] exit</Text>
        </Box>

        <PairRow inner={inner} left={incantLeft} right={focusRight} lc={C.bold} rc={C.body} />
        <PairRow inner={inner} left={manaLeft} right={latencyRight} lc={C.body} rc={C.body} />

        {showSlots1 && (
          <PairRow
            inner={inner}
            left="ᚨ QUICK SLOTS"
            right={slots1.join("   ")}
            lc={C.amber}
            rc={C.body}
          />
        )}
        {showSlots2 && <SlotRow inner={inner} items={slots2} />}

        {showDaemon && (
          <PairRow
            inner={inner}
            left="⚙ PID 40912 · astro preview ── 1 active"
            right="[Ctrl+T] expand ─ [Ctrl+R] fold"
            lc={C.body}
            rc={C.dim}
          />
        )}

        <Box flexGrow={1} />

        {castBar}
      </Box>
    );
  }

  /* ── FULL MODE ── */
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
      <Box borderStyle="round" borderColor={C.border} flexDirection="column" paddingX={1} width={inner}>
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
      <Box borderStyle="round" borderColor={C.border} flexDirection="column" paddingX={1} width={inner}>
        <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
          <Text color={C.label}>✧━ ⟨ DAEMON SUBPROCESSES ⟩</Text>
          <Text color={C.dim}>1 active ─ [Ctrl+T] expand ─ [Ctrl+R] fold</Text>
        </Box>
        <Text color={C.body}>⚙ PID 40912 · astro preview</Text>
        <Text color={C.dim}>└─ cd ".../merlin/cache/scratch/wm-dashboard" && npx astro preview --port 4321</Text>
      </Box>

      {/* Spellbook status + quick slots */}
      <Box borderStyle="round" borderColor={C.border} flexDirection="column" paddingX={1} width={inner}>
        <Box flexDirection="row" justifyContent="space-between" width={inner - 2}>
          <Text color={C.label}>✧━ ⟨ SPELLBOOK STATUS ⟩</Text>
          <Text color={C.dim}>[ESC] banish ─ [/] runes ─ [CTRL+C] exit</Text>
        </Box>

        <PairRow inner={inner} left={incantLeft} right={focusRight} lc={C.bold} rc={C.body} />
        <PairRow inner={inner} left={manaLeft} right={latencyRight} />

        <Text color={C.amber}>ᚨ QUICK SLOTS</Text>
        <SlotRow inner={inner} items={slots1} />
        <SlotRow inner={inner} items={slots2} />
      </Box>

      {/* Transcript fills the remaining height */}
      <Box
        borderStyle="round"
        borderColor={C.border}
        flexDirection="column"
        paddingX={1}
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
      <Box borderStyle="round" borderColor={C.border} flexDirection="row" paddingX={1} width={inner}>
        <Text color={C.amber}>cast ❯</Text>
        <Text color={C.bold}> {typed}</Text>
        <Text color={C.cursor}>▮</Text>
      </Box>
    </Box>
  );
}
