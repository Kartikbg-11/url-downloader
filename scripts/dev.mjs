import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backendRoot = path.join(
  projectRoot,
  "mini-services",
  "url-downloader-backend",
);
const python = path.join(backendRoot, "venv", "Scripts", "python.exe");

const children = [];

try {
  const response = await fetch("http://127.0.0.1:8001/api/health", {
    signal: AbortSignal.timeout(1500),
  });
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  console.log("Using the backend already running on http://127.0.0.1:8001");
} catch {
  children.push(
    spawn(
      python,
      ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001"],
      { cwd: backendRoot, stdio: "inherit" },
    ),
  );
}

children.push(
  spawn("node", [path.join(projectRoot, "node_modules", "next", "dist", "bin", "next"), "dev", "-p", "3000"], {
    cwd: projectRoot,
    stdio: "inherit",
  }),
);

let stopping = false;
function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exitCode = exitCode;
}

for (const child of children) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping && code !== 0) stop(code ?? 1);
  });
}

process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
