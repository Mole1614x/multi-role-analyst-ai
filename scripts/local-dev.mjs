import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = join(root, "backend");
const frontend = join(root, "frontend");
const windows = process.platform === "win32";
const venv = join(backend, ".venv");
const python = windows ? join(venv, "Scripts", "python.exe") : join(venv, "bin", "python");
const next = join(frontend, "node_modules", "next", "dist", "bin", "next");
const envFile = join(root, ".env.development.local");
const stamps = join(venv, ".analyst-local");
const pythonVersionCheck = "import sys; print(sys.version.split()[0]); sys.exit(not ((3, 11) <= sys.version_info[:2] < (3, 14)))";

function run(command, args, cwd, env = process.env) {
  return new Promise((done, fail) => {
    const child = spawn(command, args, { cwd, env, stdio: "inherit" });
    child.once("error", error => fail(new Error(`Could not start ${command} (${error.code}).`)));
    child.once("exit", (code, signal) => {
      if (code === 0) done();
      else fail(new Error(`${args.join(" ")} exited with ${signal || code}.`));
    });
  });
}

function npm(args, env = process.env) {
  if (!process.env.npm_execpath) throw new Error("Run this command through npm.");
  return run(process.execPath, [process.env.npm_execpath, ...args], frontend, env);
}

function ensureEnv() {
  try {
    writeFileSync(envFile, readFileSync(join(root, ".env.development.example")), { flag: "wx", mode: 0o600 });
    console.log("Created .env.development.local for SQLite and local background jobs.");
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
  }
}

function pythonVersion(command, prefix = []) {
  return spawnSync(command, [...prefix, "-c", pythonVersionCheck], { encoding: "utf8", timeout: 5000 });
}

function pythonCommand() {
  const candidates = process.env.PYTHON_BIN ? [[process.env.PYTHON_BIN]] : [
    ...(windows ? [["py", "-3.11"], ["py", "-3.12"], ["py", "-3.13"]] : []),
    ["python3.11"], ["python3.12"], ["python3.13"], ["python3"], ["python"],
  ];
  for (const [command, ...prefix] of candidates) {
    if (pythonVersion(command, prefix).status === 0) return [command, ...prefix];
  }
  throw new Error("Python 3.11 through 3.13 is required. Install Python or set PYTHON_BIN to a supported interpreter, then run npm run setup.");
}

function ensureInstalled() {
  if (!existsSync(python) || !existsSync(next)) {
    throw new Error("Project dependencies are missing. Run npm run setup.");
  }
}

function developmentEnv(overrides = {}, base = process.env) {
  return {
    ...base,
    ANALYST_ENV_FILE: envFile,
    PYTHONUNBUFFERED: "1",
    MPLCONFIGDIR: process.env.MPLCONFIGDIR || join(backend, "data", "matplotlib"),
    OPENBLAS_NUM_THREADS: process.env.OPENBLAS_NUM_THREADS || "1",
    OMP_NUM_THREADS: process.env.OMP_NUM_THREADS || "1",
    ...overrides,
  };
}

function address(value, label) {
  const url = new URL(value);
  const hostname = url.hostname.replace(/^\[|\]$/g, "");
  const port = Number(url.port || 80);
  if (url.protocol !== "http:" || !["localhost", "127.0.0.1", "::1"].includes(hostname) || !port) {
    throw new Error(`${label} must be an HTTP loopback URL with a usable port.`);
  }
  return { url: url.origin, host: hostname === "localhost" ? "127.0.0.1" : hostname, port };
}

function developmentConfig(env) {
  const config = spawnSync(python, ["-c", [
    "import json",
    "from app.core.config import settings",
    "from sqlalchemy.engine import make_url",
    "config = settings()",
    "if make_url(config.database_url).get_backend_name() != 'sqlite' or config.task_backend != 'local': raise SystemExit(2)",
    "print(json.dumps([config.backend_url, config.origin]))",
  ].join("\n")], { cwd: backend, env, encoding: "utf8", timeout: 15_000 });
  if (config.status !== 0) {
    if (config.stderr?.includes("ModuleNotFoundError")) {
      throw new Error("Backend dependencies are missing. Run npm run setup.");
    }
    throw new Error("Local startup needs SQLite and TASK_BACKEND=local. Check .env.development.local and any shell overrides, then run npm run setup.");
  }
  const [api, web] = JSON.parse(config.stdout);
  return { api: address(api, "BACKEND_URL"), web: address(web, "FRONTEND_URL") };
}

async function setup() {
  ensureEnv();
  if (!existsSync(venv)) {
    const [command, ...prefix] = pythonCommand();
    console.log("Creating the Python environment in backend/.venv.");
    await run(command, [...prefix, "-m", "venv", venv], root);
  }
  const version = pythonVersion(python);
  if (version.status !== 0) {
    throw new Error("The existing backend/.venv must contain Python 3.11 through 3.13. Move the incompatible environment aside and run npm run setup.");
  }
  mkdirSync(stamps, { recursive: true });
  const backendHash = createHash("sha256").update(version.stdout);
  for (const name of ["requirements.txt", "requirements-dev.txt", "pyproject.toml"]) {
    backendHash.update(readFileSync(join(backend, name)));
  }
  const digest = backendHash.digest("hex");
  const pythonStamp = join(stamps, "python");
  const env = developmentEnv();
  const pip = spawnSync(python, ["-m", "pip", "--version"], { encoding: "utf8", timeout: 5000 });
  if (pip.status !== 0) await run(python, ["-m", "ensurepip", "--upgrade"], backend, env);
  const dependencies = spawnSync(python, ["-c", "import importlib.util as u; import sys; sys.exit(not all(u.find_spec(p) for p in ('fastapi', 'sqlalchemy', 'pyarrow', 'pytest', 'ruff')))"], {
    cwd: backend, env, timeout: 5000,
  });
  if (dependencies.status !== 0 || !existsSync(pythonStamp) || readFileSync(pythonStamp, "utf8") !== digest) {
    console.log("Installing backend dependencies. The first install may take several minutes.");
    await run(python, ["-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements-dev.txt"], backend, env);
    await run(python, ["-m", "pip", "install", "--disable-pip-version-check", "-q", "--no-deps", "-e", "."], backend, env);
    writeFileSync(pythonStamp, digest);
  }
  const frontendStamp = join(stamps, "frontend");
  const lock = createHash("sha256").update(readFileSync(join(frontend, "package-lock.json")))
    .update(process.version).digest("hex");
  if (!existsSync(next) || !existsSync(frontendStamp) || readFileSync(frontendStamp, "utf8") !== lock) {
    console.log("Installing front-end dependencies.");
    await npm(["ci", "--no-audit", "--no-fund"]);
    writeFileSync(frontendStamp, lock);
  }
  developmentConfig(env);
  await run(python, ["-c", "import duckdb, fastapi, langgraph, numpy, pandas, pyarrow, uvicorn; from app.main import app"], backend, env);
  await run(python, ["-m", "alembic", "upgrade", "head"], backend, env);
  console.log("Local workspace is ready. Run npm run dev.");
}

function portCheck(host, port) {
  return new Promise((done, fail) => {
    const server = createServer();
    server.once("error", error => fail(new Error(error.code === "EADDRINUSE"
      ? `Port ${port} is already in use. Stop the process or choose another URL in .env.development.local.`
      : `Could not use ${host}:${port} (${error.code}).`)));
    server.listen(port, host, () => {
      const boundPort = server.address().port;
      server.close(() => done(boundPort));
    });
  });
}

function stopTree(child, signal) {
  if (!child.pid) return;
  try {
    if (windows) {
      if (child.exitCode === null && child.signalCode === null) {
        spawnSync("taskkill.exe", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore", timeout: 5000 });
      }
    } else {
      process.kill(-child.pid, signal);
    }
  } catch (error) {
    if (error.code !== "ESRCH") throw error;
  }
}

async function waitForHttp(urls, signal) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    signal.throwIfAborted();
    const healthy = await Promise.all(urls.map(async url => {
      try {
        return (await fetch(url, { signal: AbortSignal.any([signal, AbortSignal.timeout(2000)]) })).ok;
      } catch {
        return false;
      }
    }));
    if (healthy.every(Boolean)) return;
    await delay(350, undefined, { signal });
  }
  throw new Error("The local servers did not become healthy. Check the startup messages above.");
}

async function serve(env, exercise) {
  const { api, web } = developmentConfig(env);
  if (api.port === web.port) throw new Error("BACKEND_URL and FRONTEND_URL need different ports.");
  await Promise.all([portCheck(api.host, api.port), portCheck(web.host, web.port)]);
  await run(python, ["-m", "alembic", "upgrade", "head"], backend, env);

  let requestStop;
  const interrupted = new Promise(done => { requestStop = done; });
  process.once("SIGINT", requestStop);
  process.once("SIGTERM", requestStop);
  const servers = [];
  const startup = new AbortController();
  function start(name, command, args, cwd, childEnv) {
    const processHandle = spawn(command, args, { cwd, env: childEnv, detached: !windows, stdio: "inherit" });
    const exit = new Promise((done, fail) => {
      processHandle.once("error", error => fail(new Error(`${name} could not start (${error.code}).`)));
      processHandle.once("exit", (code, signal) => done(new Error(`${name} exited with ${signal || code}.`)));
    });
    servers.push({ processHandle, exit });
  }

  try {
    start("FastAPI", python, ["-m", "uvicorn", "app.main:app", "--host", api.host, "--port", String(api.port),
      "--no-proxy-headers", "--timeout-graceful-shutdown", "5", ...(!exercise ? ["--reload"] : [])], backend, env);
    start("Next.js", process.execPath, [next, "dev", "--hostname", web.host, "--port", String(web.port)],
      frontend, { ...env, API_INTERNAL_URL: api.url, NEXT_PUBLIC_API_URL: api.url });
    console.log(`Starting Analyst Workspace at ${web.url}. API: ${api.url}.`);

    const exit = Promise.race(servers.map(server => server.exit)).then(error => { throw error; });
    const work = waitForHttp([api.url + "/health", web.url + "/api/health/ready"], startup.signal).then(async () => {
      console.log(`Ready at ${web.url}. Press Ctrl+C to stop both servers.`);
      if (exercise) await exercise(web.url);
      else await interrupted;
    });
    await Promise.race([exit, interrupted, work]);
  } finally {
    startup.abort();
    for (const server of servers) stopTree(server.processHandle, "SIGTERM");
    await Promise.race([Promise.allSettled(servers.map(server => server.exit)), delay(7500, undefined, { ref: false })]);
    for (const server of servers) stopTree(server.processHandle, "SIGKILL");
    process.removeListener("SIGINT", requestStop);
    process.removeListener("SIGTERM", requestStop);
  }
}

async function test() {
  ensureInstalled();
  const deploymentKeys = /^(ANALYST_|POSTGRES_|CELERY_|(?:APP_ENV|BACKEND_URL|DATABASE_URL|FRONTEND_URL|REDIS_URL|TASK_BACKEND)$)/i;
  const testBase = Object.fromEntries(Object.entries(process.env).filter(([key]) => !deploymentKeys.test(key)));
  await run(python, ["-m", "pytest", "-q"], backend, developmentEnv({ ANALYST_ENV_FILE: "" }, testBase));
  const { chromium } = createRequire(join(frontend, "package.json"))("@playwright/test");
  if (!process.env.CHROMIUM_PATH && !existsSync(chromium.executablePath())) {
    console.log("Installing the Chromium browser for tests.");
    await npm(["exec", "--", "playwright", "install", "chromium"]);
  }

  const directory = mkdtempSync(join(tmpdir(), "analyst-browser-"));
  try {
    const [apiPort, webPort] = await Promise.all([portCheck("127.0.0.1", 0), portCheck("127.0.0.1", 0)]);
    const env = developmentEnv({
      ANALYST_ENV_FILE: join(directory, ".env"),
      ANALYST_DATABASE_URL: `sqlite:///${join(directory, "browser.db").replaceAll("\\", "/")}`,
      ANALYST_TASK_BACKEND: "local",
      ANALYST_STORAGE_DIR: join(directory, "storage"),
      ANALYST_S3_BUCKET: "",
      ANALYST_LLM_PROVIDER: "none",
      ANALYST_RESEARCH_API_KEY: "",
      ANALYST_COOKIE_SECURE: "false",
      ANALYST_ORIGIN: `http://127.0.0.1:${webPort}`,
      BACKEND_URL: `http://127.0.0.1:${apiPort}`,
      MPLCONFIGDIR: join(directory, "matplotlib"),
    }, testBase);
    await serve(env, url => npm(["test"], { ...env, PLAYWRIGHT_BASE_URL: url }));
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

try {
  switch (process.argv[2]) {
    case "setup":
      await setup();
      break;
    case "dev":
      ensureInstalled();
      ensureEnv();
      await serve(developmentEnv());
      break;
    case "test":
      await test();
      break;
    case "build":
      ensureInstalled();
      await npm(["run", "build"]);
      break;
    case "lint":
      ensureInstalled();
      await run(python, ["-m", "ruff", "check", "app", "tests", "alembic"], backend);
      await run(python, ["-m", "ruff", "format", "--check", "app", "tests", "alembic"], backend);
      await npm(["run", "lint"]);
      await npm(["run", "check"]);
      break;
    default:
      throw new Error("Use npm run setup, dev, test, lint, or build.");
  }
} catch (error) {
  console.error(`Analyst Workspace: ${error.message}`);
  process.exitCode = 1;
}
