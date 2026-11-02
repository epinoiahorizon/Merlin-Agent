import { Box, Text, useStdout } from '@merlin/ink'
import React from 'react'

// Truecolor palette extracted from the product screenshot.
const C = {
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

function pad(width: number, left: string, right?: string) {
  if (!right) {
    return left.padEnd(width, ' ')
  }
  const gap = Math.max(1, width - left.length - right.length)

  return left + ' '.repeat(gap) + right
}

function center(width: number, text: string) {
  const pad = Math.max(0, width - text.length)
  const left = Math.floor(pad / 2)

  return ' '.repeat(left) + text + ' '.repeat(pad - left)
}

export function OperatorConsole() {
  const { stdout } = useStdout()
  const width = stdout ? stdout.columns : WIDTH
  const w = Math.min(WIDTH, Math.max(80, width - 4))

  const line = (label: string) => <Text color={C.divider}>{'─'.repeat(w)}</Text>

  return (
    <Box alignItems="center" flexDirection="column" height={stdout?.rows || 20} justifyContent="center" width={width}>
      <Box backgroundColor={C.windowBg} borderColor={C.border} borderStyle="round" flexDirection="column" width={w + 2}>
        {/* Title bar */}
        <Box backgroundColor={C.windowBg} paddingX={1} paddingY={0}>
          <Text color={C.chrome}>{'● ● ●  '}</Text>
          <Text color={C.label}>merlin — operator session</Text>
        </Box>
        <Box height={1}>{line('div')}</Box>

        {/* Body */}
        <Box backgroundColor={C.windowBg} flexDirection="column" paddingX={2} paddingY={1}>
          <Box flexDirection="row" marginTop={1}>
            <Text color={C.dim}>{'$ '}</Text>
            <Text color={C.body}>merlin learn --from last-session</Text>
          </Box>

          <Box flexDirection="row" marginTop={1}>
            <Text color={C.green}>{'+ '}</Text>
            <Text bold color={C.bold}>
              skill windows-service-deploy
            </Text>
            <Text color={C.dim}>{'   3 rules captured'}</Text>
          </Box>
          <Box flexDirection="row" marginTop={1}>
            <Text color={C.green}>{'+ '}</Text>
            <Text bold color={C.bold}>
              memory fleet-update-doctrine
            </Text>
            <Text color={C.dim}>{'   global-first, verified'}</Text>
          </Box>
          <Box flexDirection="row" marginTop={1}>
            <Text color={C.amber}>{'- '}</Text>
            <Text bold color={C.bold}>
              eval suite
            </Text>
            <Text color={C.dim}>{'   14/14 → 16/16 green'}</Text>
          </Box>

          <Box height={1} />

          <Box flexDirection="row" marginTop={1}>
            <Text color={C.dim}>{'$ '}</Text>
            <Text color={C.body}>merlin fleet status</Text>
          </Box>

          <Box flexDirection="row" justifyContent="space-between" marginTop={1} width={w - 4}>
            <Text color={C.nodeName}>node-01</Text>
            <Text>
              <Text color={C.green}>online</Text>
              <Text color={C.dim}> · 5m</Text>
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            <Text color={C.nodeName}>node-02</Text>
            <Text>
              <Text color={C.green}>online</Text>
              <Text color={C.dim}> · 7h</Text>
            </Text>
          </Box>
          <Box flexDirection="row" justifyContent="space-between" width={w - 4}>
            <Text color={C.nodeName}>edge-03</Text>
            <Text>
              <Text color={C.green}>online</Text>
              <Text color={C.dim}> · 4m</Text>
            </Text>
          </Box>

          <Box flexDirection="row" marginTop={1}>
            <Text color={C.dim}>+ 2 more online</Text>
          </Box>

          <Box height={1} />

          <Box flexDirection="row">
            <Text color={C.dim}>{'$ '}</Text>
            <Box backgroundColor={C.cursor} height={1} width={1} />
          </Box>
        </Box>

        {/* Footer */}
        <Box height={1}>{line('div')}</Box>
        <Box
          backgroundColor={C.windowBg}
          flexDirection="row"
          justifyContent="space-between"
          paddingX={1}
          paddingY={0}
          width={w}
        >
          <Text color={C.label}>EVERY EDIT VERIFIED</Text>
          <Text color={C.label}>CACHE HIT 97%</Text>
          <Text color={C.green}>ZERO REGRESSIONS</Text>
        </Box>
      </Box>
    </Box>
  )
}
