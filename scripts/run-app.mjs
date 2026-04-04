import { cpSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const isWindows = process.platform === "win32";
const currentFile = fileURLToPath(import.meta.url);
const rootDir = path.resolve(path.dirname(currentFile), "..");
const frontendDir = path.join(rootDir, "frontend");
const configPath = path.join(rootDir, "config", "conf.yaml");
const defaultConfigPath = path.join(rootDir, "config", "conf.default.yaml");
const setupOnly = process.argv.includes("--setup-only");

function commandName(command) {
  return isWindows ? `${command}.cmd` : command;
}

function run(command, args, options = {}) {
  const result = spawnSync(commandName(command), args, {
    cwd: rootDir,
    stdio: "inherit",
    ...options,
  });

  if (result.error) {
    const detail = result.error.code === "ENOENT" ? `Command not found: ${command}` : result.error.message;
    console.error(`[deeplecture] ${detail}`);
    process.exit(1);
  }

  if (typeof result.status === "number" && result.status !== 0) {
    process.exit(result.status);
  }
}

function ensureConfig() {
  if (existsSync(configPath)) {
    return;
  }

  cpSync(defaultConfigPath, configPath);
  console.log("[deeplecture] Created config/conf.yaml from config/conf.default.yaml");
  console.log("[deeplecture] Fill in your API keys in config/conf.yaml when you are ready.");
}

function ensureFrontendDeps() {
  const nodeModulesDir = path.join(frontendDir, "node_modules");
  const installCommand = existsSync(path.join(frontendDir, "package-lock.json")) ? "ci" : "install";

  if (existsSync(nodeModulesDir)) {
    console.log("[deeplecture] frontend/node_modules already exists, skipping npm install");
    return;
  }

  console.log(`[deeplecture] Installing frontend dependencies with npm ${installCommand}...`);
  run("npm", [installCommand], { cwd: frontendDir });
}

console.log("[deeplecture] Preparing workspace...");
ensureConfig();

console.log("[deeplecture] Syncing Python dependencies with uv...");
run("uv", ["sync", "--extra", "dev"]);

ensureFrontendDeps();

if (setupOnly) {
  console.log("[deeplecture] Setup complete.");
  process.exit(0);
}

console.log("[deeplecture] Starting DeepLecture...");
run("uv", ["run", "deeplecture"]);
