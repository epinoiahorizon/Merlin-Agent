import { spawn } from 'child_process'
import { existsSync } from 'fs'
import { fileURLToPath } from 'url'
import path from 'path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const uiTuiRoot = path.resolve(__dirname, '..')
const bundle = path.join(uiTuiRoot, 'dist', 'console-demo.cjs')

// Preferred path: run the prebuilt bundle (npm run demo:build). CommonJS
// output keeps Ink's dynamic requires working, and with no tsx/esbuild or
// symlink resolution at runtime it behaves identically under Windows node
// even when the repo is reached via UNC (\\wsl.localhost\...) — where
// Windows node cannot realpath WSL's relative node_modules symlinks and the
// dev-mode tsx path fails.
let args

if (existsSync(bundle)) {
  args = [bundle]
} else {
  // Dev fallback: load the TS entry through tsx. Needs platform-matching
  // node_modules (the native checkout's own install).
  args = ['--import', 'tsx', path.join(uiTuiRoot, 'src/components/console-demo/demo.tsx')]
}

const p = spawn(process.execPath, args, {
  cwd: uiTuiRoot,
  stdio: 'inherit',
  env: process.env
})

p.on('error', err => {
  console.error(`console-demo failed to launch: ${err.message}`)
  process.exit(1)
})

p.on('exit', code => {
  process.exit(code ?? 0)
})
