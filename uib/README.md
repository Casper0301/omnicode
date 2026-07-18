# uib

Persistent, clean-profile Chromium for terminal coding agents.

Open a dev URL, screenshot it, inspect the accessibility tree, click/fill, re-screenshot — with state that survives across CLI invocations via a background daemon. One browser, one page (v1).

## Install

```bash
npm i
npx playwright install chromium
```

Requires Node.js ≥ 18.

## Commands

```bash
node uib.mjs <command> [args]
```

| Command | Description |
|--------|-------------|
| `open <url> [--vp WxH]` | Navigate the persistent page (starts daemon if needed). Default viewport `1440x900`. |
| `shot <out.png> [--full]` | Screenshot current page (`--full` = full page). |
| `snapshot` | Accessibility-tree outline with stable `@eN` refs. |
| `click <target>` | Click `@eN` (from last snapshot) or a CSS selector. |
| `fill <target> <text>` | Clear + type into `@eN` or CSS selector. |
| `press <key>` | Keyboard key on the page (`Enter`, `Tab`, …). |
| `eval <js>` | Evaluate JS in page context; prints JSON result. |
| `console [n]` | Last *n* console messages + page errors (default 20). |
| `url` | Current page URL and title. |
| `status` | Daemon pid / port / page URL (exit 1 if not running). |
| `stop` | Shut daemon + browser down. |
| `--help` | Usage text. |

## Examples

```bash
# Open a page and capture it
node uib.mjs open https://example.com
node uib.mjs shot page.png
node uib.mjs shot full.png --full

# Mobile viewport
node uib.mjs open https://example.com --vp 375x812

# Inspect and interact via accessibility refs
node uib.mjs snapshot
node uib.mjs click @e3
node uib.mjs fill @e5 "hello"
node uib.mjs press Enter

# CSS selector targets work too
node uib.mjs click "button.submit"
node uib.mjs fill "#email" "a@b.c"

# Page JS + console
node uib.mjs eval 'document.title'
node uib.mjs console 10
node uib.mjs url

# Lifecycle
node uib.mjs status
node uib.mjs stop
```

Typical agent loop:

```bash
node uib.mjs open http://localhost:3000
node uib.mjs shot before.png
node uib.mjs snapshot          # note refs
node uib.mjs click @e12
node uib.mjs shot after.png
```

## Env vars

| Variable | Default | Meaning |
|----------|---------|---------|
| `UIB_HOME` | `~/.uib` | State directory: `daemon.json` + clean Chromium profile at `$UIB_HOME/profile`. |
| `UIB_HEADED` | (unset) | Set to `1` to launch headed Chromium instead of headless. |

The profile under `$UIB_HOME/profile` is **clean and isolated** — uib never touches your system Chrome/Chromium profile.

## How it works

- First command (except `status` / `stop`) spawns a detached daemon (`node uib.mjs __daemon__`).
- Daemon listens on `127.0.0.1` (random free port); pid + port written to `$UIB_HOME/daemon.json`.
- Browser, page, a11y refs, and console ring buffer live only in the daemon process.
- Idle auto-shutdown after **30 minutes** without activity.
- Refs from `snapshot` are valid until the next `open` / navigation.

If Chromium is not installed:

```text
chromium missing — run: npx playwright install chromium
```
