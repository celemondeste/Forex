#!/usr/bin/env node
// Runs the API with autoreload against the project virtual environment.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const windows = process.platform === 'win32';
const candidates = windows
  ? [join(root, '.venv', 'Scripts', 'python.exe'), join(root, 'backend', 'venv', 'Scripts', 'python.exe')]
  : [join(root, '.venv', 'bin', 'python'), join(root, 'backend', 'venv', 'bin', 'python')];
const python = process.env.PYTHON || candidates.find((candidate) => existsSync(candidate)) || (windows ? 'python' : 'python3');

spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', process.env.HOST || '0.0.0.0',
  '--port', process.env.PORT || '8000', '--reload'], {
  cwd: join(root, 'backend'), stdio: 'inherit', shell: windows,
}).on('exit', (code) => process.exit(code ?? 0));
