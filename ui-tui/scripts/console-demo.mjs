import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const env = { ...process.env, PATH: (process.env.PATH || '') + ';C:/Windows/System32', ComSpec: 'cmd.exe' };
const p = spawn('npx', ['tsx', 'src/components/console-demo/demo-v5.tsx'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true,
  env,
});
