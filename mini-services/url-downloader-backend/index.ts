/**
 * URL Downloader Backend Service
 * 
 * This is a Node.js wrapper that starts the FastAPI Python backend.
 * The actual download logic runs in Python via uvicorn.
 */

import { spawn } from 'child_process';
import { resolve } from 'path';
import { existsSync } from 'fs';
import { mkdirSync } from 'fs';

const PORT = 8000;
const BACKEND_DIR = resolve(import.meta.dir);

console.log(`[URL Downloader Backend] Starting on port ${PORT}...`);
console.log(`[URL Downloader Backend] Working directory: ${BACKEND_DIR}`);

// Ensure downloads directory exists
const downloadsDir = resolve(BACKEND_DIR, 'downloads');
if (!existsSync(downloadsDir)) {
  mkdirSync(downloadsDir, { recursive: true });
  console.log(`[URL Downloader Backend] Created downloads directory`);
}

// Check if we're in an environment where we can run Python
const canRunPython = process.env.PYTHON_PATH || process.platform !== 'win';

if (!canRunPython) {
  console.error('[URL Downloader Backend] Cannot start: No Python available');
  process.exit(1);
}

// Start uvicorn
const pythonProcess = spawn(
  'python',
  [
    '-m', 'uvicorn',
    'app.main:app',
    '--host', '0.0.0.0',
    '--port', String(PORT),
    '--reload'
  ],
  {
    cwd: BACKEND_DIR,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYTHONDONTWRITEBYTECODE: '1',
      APP_NAME: 'URL Application Downloader',
      APP_ENV: 'development',
      HOST: '0.0.0.0',
      PORT: String(PORT),
      DOWNLOAD_DIRECTORY: 'downloads',
      MAX_DOWNLOAD_SIZE_BYTES: '1073741824',
      DOWNLOAD_CHUNK_SIZE_BYTES: '1048576',
      MAX_CONCURRENT_DOWNLOADS: '3',
      MAX_REDIRECTS: '5',
      CONNECT_TIMEOUT_SECONDS: '10',
      READ_TIMEOUT_SECONDS: '60',
      WRITE_TIMEOUT_SECONDS: '30',
      POOL_TIMEOUT_SECONDS: '10',
      ALLOWED_EXTENSIONS: '.apk,.exe,.msi,.zip,.rar,.7z,.dmg,.pkg,.deb,.rpm,.tar,.gz,.pdf,.docx,.xlsx',
      ALLOWED_MIME_TYPES: 'application/octet-stream,application/zip,application/x-7z-compressed,application/vnd.android.package-archive,application/pdf,application/x-rar-compressed,application/x-msdownload,application/x-msi,application/x-apple-diskimage,application/x-debian-package,application/x-redhat-package-manager,application/gzip,application/x-tar,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ALLOW_UNKNOWN_MIME_TYPES: 'false',
      ALLOW_HTML_DOWNLOADS: 'false',
      CORS_ORIGINS: 'http://localhost:3000',
      LOG_LEVEL: 'INFO',
    },
    stdio: 'inherit'
  }
);

pythonProcess.on('spawn', () => {
  console.log(`[URL Downloader Backend] ✅ Server started at http://0.0.0.0:${PORT}`);
  console.log(`[URL Downloader Backend] API Docs available at http://localhost:${PORT}/docs`);
});

pythonProcess.on('error', (err) => {
  console.error('[URL Downloader Backend] Failed to start:', err.message);
  process.exit(1);
});

pythonProcess.on('exit', (code) => {
  console.log(`[URL Downloader Backend] Process exited with code ${code}`);
  process.exit(code || 0);
});

// Handle shutdown
process.on('SIGINT', () => {
  console.log('\n[URL Downloader Backend] Shutting down...');
  pythonProcess.kill('SIGTERM');
});

process.on('SIGTERM', () => {
  pythonProcess.kill('SIGTERM');
});
