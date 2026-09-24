#!/usr/bin/env node
// Builds the React bundle, then serves it together with the API from a single origin.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const windows = process.platform === 'win32';
const host = process.env.HOST || '127.0.0.1';
const port = process.env.PORT || '8000';

function run(command, args, options = {}) {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, { stdio: 'inherit', shell: windows, ...options });
    child.on('error', rejectPromise);
    child.on('exit', (code, signal) => {
      if (signal) return resolvePromise(0);
      return code === 0 ? resolvePromise(0) : rejectPromise(new Error(`${command} exited with code ${code}`));
    });
  });
}

function resolvePython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const candidates = windows
    ? [join(root, '.venv', 'Scripts', 'python.exe'), join(root, 'backend', 'venv', 'Scripts', 'python.exe')]
    : [join(root, '.venv', 'bin', 'python'), join(root, 'backend', 'venv', 'bin', 'python')];
  const found = candidates.find((candidate) => existsSync(candidate));
  if (found) return found;
  console.warn('No project virtual environment found; falling back to the system Python.');
  return windows ? 'python' : 'python3';
}

const npm = windows ? 'npm.cmd' : 'npm';
await run(npm, ['run', 'build'], { cwd: root });

const python = resolvePython();
console.log(`\nServing the dashboard and API on http://${host}:${port} (docs at /docs)\n`);
await run(python, ['-m', 'uvicorn', 'app.main:app', '--host', host, '--port', port], {
  cwd: join(root, 'backend'),
});
