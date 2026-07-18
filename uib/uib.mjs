#!/usr/bin/env node
/**
 * uib — persistent clean-profile Chromium for terminal coding agents.
 * Single file: CLI entry + daemon mode (node uib.mjs __daemon__).
 */
import { chromium } from "playwright";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const UIB_HOME = process.env.UIB_HOME || path.join(os.homedir(), ".uib");
const DAEMON_JSON = path.join(UIB_HOME, "daemon.json");
const PROFILE_DIR = path.join(UIB_HOME, "profile");
const IDLE_MS = 30 * 60 * 1000;
const IDLE_CHECK_MS = 60 * 1000;
const NAV_TIMEOUT = 20_000;
const SETTLE_MS = 300;
const DAEMON_START_TIMEOUT_MS = 10_000;
const CONSOLE_RING = 200;
const DEFAULT_VP = { width: 1440, height: 900 };

// ─── helpers ─────────────────────────────────────────────────────────────────

function ensureHome() {
  fs.mkdirSync(UIB_HOME, { recursive: true });
  fs.mkdirSync(PROFILE_DIR, { recursive: true });
}

function readDaemonInfo() {
  try {
    const raw = fs.readFileSync(DAEMON_JSON, "utf8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeDaemonInfo(info) {
  ensureHome();
  fs.writeFileSync(DAEMON_JSON, JSON.stringify(info), "utf8");
}

function removeDaemonInfo() {
  try {
    fs.unlinkSync(DAEMON_JSON);
  } catch {
    /* ignore */
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function isChromiumMissingError(err) {
  const msg = String(err?.message || err || "");
  return (
    /Executable doesn't exist/i.test(msg) ||
    /browserType\.launch/i.test(msg) ||
    /Please run the following command to download/i.test(msg) ||
    /playwright install/i.test(msg) ||
    /chromium.*missing/i.test(msg) ||
    /Failed to launch.*chromium/i.test(msg)
  );
}

/** Collapse multi-line Playwright errors to a single human-readable line. */
function oneLineError(err) {
  const msg = String(err?.message || err || "error");
  const first = msg.split("\n").find((l) => l.trim()) || msg;
  return first.trim().replace(/\s+/g, " ");
}

// ─── DAEMON ──────────────────────────────────────────────────────────────────

async function runDaemon() {
  ensureHome();

  /** @type {import('playwright').BrowserContext | null} */
  let context = null;
  /** @type {import('playwright').Page | null} */
  let page = null;
  /** @type {Map<string, {role: string, name: string}>} */
  let refMap = new Map();
  /** @type {{level: string, text: string}[]} */
  let consoleBuf = [];
  let lastActivity = Date.now();
  let shuttingDown = false;

  function touch() {
    lastActivity = Date.now();
  }

  function pushConsole(level, text) {
    consoleBuf.push({ level, text: String(text) });
    if (consoleBuf.length > CONSOLE_RING) {
      consoleBuf = consoleBuf.slice(-CONSOLE_RING);
    }
  }

  function clearRefs() {
    refMap = new Map();
  }

  function attachPageListeners(p) {
    p.on("console", (msg) => {
      pushConsole(msg.type(), msg.text());
    });
    p.on("pageerror", (err) => {
      pushConsole("error", err?.message || String(err));
    });
  }

  async function ensureBrowser() {
    if (context) return;
    const headed = process.env.UIB_HEADED === "1";
    try {
      context = await chromium.launchPersistentContext(PROFILE_DIR, {
        headless: !headed,
        viewport: DEFAULT_VP,
        args: ["--disable-dev-shm-usage"],
      });
    } catch (err) {
      if (isChromiumMissingError(err)) {
        throw new Error(
          "chromium missing — run: npx playwright install chromium"
        );
      }
      throw err;
    }
    // Reuse first page if any, else create one on demand
    const pages = context.pages();
    if (pages.length > 0) {
      page = pages[0];
      attachPageListeners(page);
    }
  }

  async function ensurePage() {
    await ensureBrowser();
    if (!page || page.isClosed()) {
      page = await context.newPage();
      attachPageListeners(page);
      await page.setViewportSize(DEFAULT_VP);
    }
    return page;
  }

  async function requirePage() {
    if (!page || page.isClosed()) {
      throw new Error("no page open — run: uib open <url>");
    }
    return page;
  }

  async function navigate(url, vp) {
    const p = await ensurePage();
    if (vp) {
      await p.setViewportSize(vp);
    }
    clearRefs();
    try {
      await p.goto(url, { waitUntil: "load", timeout: NAV_TIMEOUT });
    } catch (err) {
      const msg = String(err?.message || err);
      if (/Timeout/i.test(msg)) {
        throw new Error(`navigation timeout: ${url}`);
      }
      throw err;
    }
    await sleep(SETTLE_MS);
    const finalUrl = p.url();
    const title = await p.title();
    return { url: finalUrl, title };
  }

  function resolveTarget(target) {
    if (typeof target !== "string" || !target) {
      throw new Error("missing target");
    }
    if (target.startsWith("@e")) {
      const info = refMap.get(target);
      if (!info) {
        throw new Error(`stale ref ${target} — run snapshot again`);
      }
      return { kind: "ref", ...info, target };
    }
    return { kind: "css", selector: target, target };
  }

  async function locatorFor(p, resolved) {
    if (resolved.kind === "ref") {
      // Static text is not a Playwright ARIA role — resolve by text content.
      if (resolved.role === "text") {
        return p.getByText(resolved.name || "", { exact: true }).first();
      }
      const opts = {};
      if (resolved.name) opts.name = resolved.name;
      return p.getByRole(resolved.role, opts).first();
    }
    return p.locator(resolved.selector).first();
  }

  /** Map CDP AX roles to Playwright getByRole names where needed. */
  function normalizeRole(raw) {
    if (!raw) return "generic";
    const map = {
      RootWebArea: "document",
      WebArea: "document",
      StaticText: "text",
      InlineTextBox: "text",
      image: "img",
    };
    return map[raw] || raw;
  }

  function axValue(node, prop) {
    const p = (node.properties || []).find((x) => x.name === prop);
    if (!p || p.value == null) return null;
    const v = p.value.value;
    return v === undefined || v === null || v === "" ? null : v;
  }

  function walkCdpAx(nodeId, byId, depth, lines) {
    const node = byId.get(nodeId);
    if (!node) return;
    const rawRole = node.role?.value || "generic";
    const ignored = !!node.ignored;
    // Skip pure ignored wrappers but still walk their children at same depth
    if (ignored && (rawRole === "none" || rawRole === "generic" || !rawRole)) {
      for (const childId of node.childIds || []) {
        walkCdpAx(childId, byId, depth, lines);
      }
      return;
    }
    const role = normalizeRole(rawRole);
    const name = node.name?.value || "";
    const value = axValue(node, "value");
    const ref = `@e${refMap.size + 1}`;
    // Store role/name for getByRole resolution (Playwright-facing role)
    refMap.set(ref, { role, name });
    const indent = "  ".repeat(depth);
    let line = `${indent}${ref} ${role}`;
    line += ` ${JSON.stringify(name)}`;
    if (value !== null && value !== undefined) line += ` [${value}]`;
    lines.push(line);
    for (const childId of node.childIds || []) {
      walkCdpAx(childId, byId, depth + 1, lines);
    }
  }

  async function doSnapshot() {
    const p = await requirePage();
    clearRefs();
    const cdp = await p.context().newCDPSession(p);
    let nodes;
    try {
      const result = await cdp.send("Accessibility.getFullAXTree");
      nodes = result.nodes || [];
    } finally {
      try {
        await cdp.detach();
      } catch {
        /* ignore */
      }
    }
    const byId = new Map(nodes.map((n) => [n.nodeId, n]));
    // Root: no parentId, or first RootWebArea / document
    let rootId =
      nodes.find((n) => !n.parentId)?.nodeId ||
      nodes.find((n) => /RootWebArea|WebArea/i.test(n.role?.value || ""))
        ?.nodeId ||
      nodes[0]?.nodeId;
    const lines = [];
    if (rootId) walkCdpAx(rootId, byId, 0, lines);
    return lines.join("\n") + (lines.length ? "\n" : "");
  }

  async function shutdown() {
    if (shuttingDown) return;
    shuttingDown = true;
    try {
      if (context) {
        await context.close();
      }
    } catch {
      /* ignore */
    }
    context = null;
    page = null;
    clearRefs();
    removeDaemonInfo();
    process.exit(0);
  }

  // Idle watcher
  setInterval(() => {
    if (Date.now() - lastActivity > IDLE_MS) {
      shutdown();
    }
  }, IDLE_CHECK_MS).unref();

  // Handlers
  const handlers = {
    async ping() {
      return { pong: true };
    },
    async open({ url, vp }) {
      if (!url) throw new Error("open requires a url");
      let viewport = null;
      if (vp) {
        const m = String(vp).match(/^(\d+)x(\d+)$/i);
        if (!m) throw new Error(`invalid viewport: ${vp} (use WxH)`);
        viewport = { width: parseInt(m[1], 10), height: parseInt(m[2], 10) };
      }
      const result = await navigate(url, viewport);
      return {
        message: `OK ${result.url} — ${result.title}`,
      };
    },
    async shot({ out, full }) {
      const p = await requirePage();
      if (!out) throw new Error("shot requires an output path");
      const abs = path.isAbsolute(out) ? out : path.resolve(process.cwd(), out);
      fs.mkdirSync(path.dirname(abs), { recursive: true });
      await p.screenshot({ path: abs, fullPage: !!full });
      const st = fs.statSync(abs);
      return { message: `OK ${abs} (${st.size} bytes)` };
    },
    async snapshot() {
      const text = await doSnapshot();
      return { message: text, raw: true };
    },
    async click({ target }) {
      const p = await requirePage();
      const resolved = resolveTarget(target);
      const loc = await locatorFor(p, resolved);
      await loc.click({ timeout: 5_000 });
      await sleep(SETTLE_MS);
      return { message: `OK clicked ${target}` };
    },
    async fill({ target, text }) {
      const p = await requirePage();
      if (text === undefined) throw new Error("fill requires text");
      const resolved = resolveTarget(target);
      const loc = await locatorFor(p, resolved);
      // Playwright fill() clears then types
      await loc.fill(String(text), { timeout: 5_000 });
      return { message: `OK filled ${target}` };
    },
    async press({ key }) {
      const p = await requirePage();
      if (!key) throw new Error("press requires a key");
      await p.keyboard.press(key);
      return { message: "OK" };
    },
    async eval({ js }) {
      const p = await requirePage();
      if (js === undefined || js === "") throw new Error("eval requires js");
      const result = await p.evaluate((code) => {
        // eslint-disable-next-line no-eval
        return eval(code);
      }, js);
      let out;
      try {
        out = JSON.stringify(result);
      } catch {
        out = String(result);
      }
      return { message: out === undefined ? "undefined" : out, raw: true };
    },
    async console({ n }) {
      const count = n == null ? 20 : Math.max(0, parseInt(n, 10) || 20);
      const slice = consoleBuf.slice(-count);
      const text = slice.map((m) => `[${m.level}] ${m.text}`).join("\n");
      return { message: text + (text ? "\n" : ""), raw: true };
    },
    async url() {
      const p = await requirePage();
      const u = p.url();
      const t = await p.title();
      return { message: `${u}\n${t}`, raw: true };
    },
    async status() {
      const url = page && !page.isClosed() ? page.url() : "none";
      return {
        message: `daemon pid=${process.pid} port=${serverPort} page=${url}`,
      };
    },
    async stop() {
      // Respond first, then shut down
      setTimeout(() => shutdown(), 50);
      return { message: "OK stopped" };
    },
  };

  let serverPort = 0;
  const server = http.createServer(async (req, res) => {
    touch();
    const send = (status, body) => {
      const data = JSON.stringify(body);
      res.writeHead(status, {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(data),
      });
      res.end(data);
    };

    if (req.method === "GET" && req.url === "/ping") {
      send(200, { ok: true, pong: true });
      return;
    }

    if (req.method !== "POST" || req.url !== "/rpc") {
      send(404, { ok: false, error: "not found" });
      return;
    }

    let body = "";
    for await (const chunk of req) body += chunk;
    let payload;
    try {
      payload = JSON.parse(body || "{}");
    } catch {
      send(400, { ok: false, error: "invalid json" });
      return;
    }

    const cmd = payload.cmd;
    const args = payload.args || {};
    const handler = handlers[cmd];
    if (!handler) {
      send(200, { ok: false, error: `unknown command: ${cmd}` });
      return;
    }

    try {
      const result = await handler(args);
      send(200, { ok: true, ...result });
    } catch (err) {
      const msg = oneLineError(err);
      // Chromium missing on first browser launch
      if (isChromiumMissingError(err) || msg.includes("chromium missing")) {
        send(200, {
          ok: false,
          error: "chromium missing — run: npx playwright install chromium",
        });
        return;
      }
      send(200, { ok: false, error: msg });
    }
  });

  // Bind random free port on 127.0.0.1
  await new Promise((resolve, reject) => {
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      serverPort = addr.port;
      writeDaemonInfo({ pid: process.pid, port: serverPort });
      resolve();
    });
    server.on("error", reject);
  });

  // Clean shutdown signals
  process.on("SIGTERM", () => shutdown());
  process.on("SIGINT", () => shutdown());
  process.on("SIGHUP", () => shutdown());

  // Keep alive
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

function usage() {
  return `uib — persistent clean-profile Chromium for terminal agents

Usage: node uib.mjs <command> [args]

Commands:
  open <url> [--vp WxH]   Navigate (default viewport 1440x900)
  shot <out.png> [--full] Screenshot current page
  snapshot                Accessibility tree with @eN refs
  click <target>          Click @eN ref or CSS selector
  fill <target> <text>    Fill @eN ref or CSS selector
  press <key>             Press keyboard key (Enter, Tab, …)
  eval <js>               Evaluate JS in page; print JSON result
  console [n]             Last n console messages (default 20)
  url                     Current URL and title
  status                  Daemon pid/port/page
  stop                    Shut down daemon + browser

Env:
  UIB_HOME     State dir (default ~/.uib)
  UIB_HEADED=1 Launch headed Chromium instead of headless
`;
}

async function rpc(port, cmd, args = {}) {
  const res = await fetch(`http://127.0.0.1:${port}/rpc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd, args }),
  });
  return res.json();
}

async function ping(port) {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/ping`, {
      signal: AbortSignal.timeout(1000),
    });
    if (!res.ok) return false;
    const j = await res.json();
    return j && j.ok;
  } catch {
    return false;
  }
}

function isProcessAlive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function ensureDaemon() {
  const info = readDaemonInfo();
  if (info && info.port && isProcessAlive(info.pid) && (await ping(info.port))) {
    return info;
  }
  // Stale file
  if (info) removeDaemonInfo();

  ensureHome();
  const child = spawn(process.execPath, [__filename, "__daemon__"], {
    detached: true,
    stdio: "ignore",
    env: { ...process.env },
    cwd: process.cwd(),
  });
  child.unref();

  const deadline = Date.now() + DAEMON_START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(100);
    const n = readDaemonInfo();
    if (n && n.port && (await ping(n.port))) {
      return n;
    }
  }
  throw new Error("failed to start uib daemon within 10s");
}

async function runCli(argv) {
  if (argv.length === 0) {
    process.stderr.write(usage());
    process.exit(2);
  }
  if (argv[0] === "--help" || argv[0] === "-h" || argv[0] === "help") {
    process.stdout.write(usage());
    process.exit(0);
  }
  if (argv[0] === "__daemon__") {
    await runDaemon();
    // never returns
    return;
  }

  const cmd = argv[0];

  // status / stop: no auto-start (stop still tries if running)
  if (cmd === "status") {
    const info = readDaemonInfo();
    if (!info || !info.port || !isProcessAlive(info.pid)) {
      process.stderr.write("not running\n");
      process.exit(1);
    }
    const alive = await ping(info.port);
    if (!alive) {
      process.stderr.write("not running\n");
      process.exit(1);
    }
    try {
      const result = await rpc(info.port, "status");
      if (!result.ok) {
        process.stderr.write((result.error || "error") + "\n");
        process.exit(1);
      }
      process.stdout.write(result.message + "\n");
      process.exit(0);
    } catch {
      process.stderr.write("not running\n");
      process.exit(1);
    }
  }

  if (cmd === "stop") {
    const info = readDaemonInfo();
    if (!info || !info.port) {
      process.stdout.write("OK stopped\n");
      process.exit(0);
    }
    try {
      if (await ping(info.port)) {
        await rpc(info.port, "stop");
      }
    } catch {
      /* ignore */
    }
    // Best-effort kill + cleanup
    if (info.pid && isProcessAlive(info.pid)) {
      try {
        process.kill(info.pid, "SIGTERM");
      } catch {
        /* ignore */
      }
    }
    // Wait briefly for clean exit
    await sleep(200);
    removeDaemonInfo();
    process.stdout.write("OK stopped\n");
    process.exit(0);
  }

  // All other commands auto-start daemon
  let info;
  try {
    info = await ensureDaemon();
  } catch (err) {
    process.stderr.write((err.message || String(err)) + "\n");
    process.exit(1);
  }

  // Parse command args
  let args = {};
  try {
    switch (cmd) {
      case "open": {
        const url = argv[1];
        if (!url) throw new Error("usage: open <url> [--vp WxH]");
        args = { url };
        const vpIdx = argv.indexOf("--vp");
        if (vpIdx !== -1 && argv[vpIdx + 1]) {
          args.vp = argv[vpIdx + 1];
        }
        break;
      }
      case "shot": {
        const out = argv[1];
        if (!out) throw new Error("usage: shot <out.png> [--full]");
        args = { out, full: argv.includes("--full") };
        break;
      }
      case "snapshot":
        args = {};
        break;
      case "click": {
        const target = argv[1];
        if (!target) throw new Error("usage: click <target>");
        args = { target };
        break;
      }
      case "fill": {
        const target = argv[1];
        const text = argv.slice(2).join(" ");
        if (!target) throw new Error("usage: fill <target> <text>");
        args = { target, text };
        break;
      }
      case "press": {
        const key = argv[1];
        if (!key) throw new Error("usage: press <key>");
        args = { key };
        break;
      }
      case "eval": {
        // Multi-word js arrives as one quoted arg, or join remaining
        const js = argv.slice(1).join(" ");
        if (!js) throw new Error("usage: eval <js>");
        args = { js };
        break;
      }
      case "console": {
        args = { n: argv[1] };
        break;
      }
      case "url":
        args = {};
        break;
      default:
        process.stderr.write(`unknown command: ${cmd}\n`);
        process.stderr.write(usage());
        process.exit(1);
    }
  } catch (err) {
    process.stderr.write((err.message || String(err)) + "\n");
    process.exit(1);
  }

  let result;
  try {
    result = await rpc(info.port, cmd, args);
  } catch (err) {
    process.stderr.write((err.message || String(err)) + "\n");
    process.exit(1);
  }

  if (!result.ok) {
    process.stderr.write((result.error || "error") + "\n");
    process.exit(1);
  }

  // raw: print message as-is (may already end with newline)
  if (result.raw) {
    process.stdout.write(result.message);
    if (result.message && !result.message.endsWith("\n")) {
      process.stdout.write("\n");
    }
  } else {
    process.stdout.write(result.message + "\n");
  }
  process.exit(0);
}

// cwd for screenshots: daemon inherits spawn cwd; for absolute paths we resolve
// on CLI side when possible — shot path is resolved in daemon against its cwd,
// so re-spawn preserves the invoker's cwd (spawn sets cwd: process.cwd()).

runCli(process.argv.slice(2)).catch((err) => {
  process.stderr.write((err?.message || String(err)) + "\n");
  process.exit(1);
});
