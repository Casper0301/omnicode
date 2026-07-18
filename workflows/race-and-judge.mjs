// omnicode (race-and-judge.mjs) — multi-model fan-out, all 5 flagships. Say 'omnicode this' to invoke.
// Invoke from a GIT REPO cwd (worktree isolation needs one):
//   Workflow({ scriptPath: '~/.claude/workflows/race-and-judge.mjs', args: { spec: '<five-part spec>', verifyCmd: '<command>' } })
// Returns: { lanes, judge, verify } — the architect applies judge.winningDiffPath + does final verification.
// Subscriptions only. Race: Sonnet(Claude) + codex(GPT-5.6-Sol max) + grok(grok-4.5) + agy(authenticated Antigravity default). Judge: opus-tier (Opus 4.8 under Max / glm-5.2 under glm). Verify: glm (GLM-5.2).
// Works under both `claude` (Max) and `glm` (z.ai) — no model is hard-pinned to Fable (which z.ai lacks).

export const meta = {
  name: 'omnicode',
  description: 'omnicode — Race Sonnet + codex + grok + antigravity on a spec (worktree-isolated), opus-tier judges the diffs, GLM adversarially verifies the winner. 5 flagship families, subscriptions only.',
  phases: [
    { title: 'Race', detail: '4 implementer lanes in parallel (Claude/GPT/Grok/Gemini), each in its own git worktree' },
    { title: 'Judge', detail: 'opus-tier model reads all diffs, picks the single strongest' },
    { title: 'Verify', detail: 'GLM-5.2 (5th family, z.ai) adversarially verifies the winning diff' },
  ],
}

const spec = (args && args.spec) ? args.spec : ''
const verifyCmd = (args && args.verifyCmd) ? args.verifyCmd : ''
if (!spec) { log('ABORT: no args.spec'); throw new Error('race-and-judge requires args.spec (five-part spec text)') }
if (!verifyCmd) { log('ABORT: no args.verifyCmd'); throw new Error('race-and-judge requires args.verifyCmd (the verification command)') }

// A unique directory prevents concurrent races from overwriting one another.
// Staging inside each disposable worktree makes the binary diff include new,
// modified, renamed, and deleted files; plain `git diff` omits untracked files.
const raceRunId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
const raceDir = `/tmp/omnicode-race-${raceRunId}`
const diffPaths = {
  sonnet: `${raceDir}/sonnet.diff`,
  codex: `${raceDir}/codex.diff`,
  grok: `${raceDir}/grok.diff`,
  agy: `${raceDir}/agy.diff`,
}
const captureDiff = (diffPath) => `mkdir -p "${raceDir}" && git add -A && git diff --cached --binary HEAD -- > "${diffPath}"`

const LANE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['complete', 'partial', 'timeout', 'unavailable'] },
    summary: { type: 'string', description: 'one-line restatement of what was implemented' },
    diffPath: { type: 'string', description: 'absolute path to the captured staged binary diff in this race run directory' },
    verified: { type: 'boolean', description: 'did YOU re-run the verification command and see it pass?' },
    verifiedOutput: { type: 'string', description: 'actual output of the verification command you re-ran' },
    gaps: { type: 'string', description: 'spec ambiguities / unfinished items, or "none"' },
  },
  required: ['status', 'summary', 'diffPath', 'verified', 'gaps'],
}

phase('Race')
const lanes = await parallel([
  () => agent(
    `You are the Claude (Sonnet) implementation lane in a race. Implement this spec IN FULL in your worktree using Edit/Write. Then capture every change, including untracked files, with \`${captureDiff(diffPaths.sonnet)}\` (run it from your worktree root) and return diffPath=${diffPaths.sonnet}. Then re-run the verification command yourself and paste the actual output. Never claim done without re-running verification.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'sonnet-lane [Sonnet]', phase: 'Race', model: 'sonnet', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the codex-implementer lane in a race. Follow your agent pattern: write the spec to a mktemp file, drive \`codex exec --ignore-user-config -m gpt-5.6-sol -c model_reasoning_effort=max -c model_context_window=272000 -c approval_policy="never" -s workspace-write --skip-git-repo-check -C "$(pwd)" -o "$FINAL" - < "$SPEC"\` to implement it in your worktree. After codex finishes, capture every change, including untracked files, with \`${captureDiff(diffPaths.codex)}\`, re-run the verification command YOURSELF (codex's claim is not evidence), and return the structured report with diffPath=${diffPaths.codex}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'codex-lane [Sonnet> GPT-5.6-Sol]', phase: 'Race', agentType: 'codex-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the grok-implementer lane in a race. Follow your agent pattern: write the spec to a mktemp file, drive \`grok --prompt-file "$SPEC" -m grok-4.5 --permission-mode acceptEdits --output-format plain --cwd "$(pwd)"\` to implement it in your worktree. After grok finishes, capture every change, including untracked files, with \`${captureDiff(diffPaths.grok)}\`, re-run the verification command YOURSELF, and return the structured report with diffPath=${diffPaths.grok}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'grok-lane [Sonnet> Grok]', phase: 'Race', agentType: 'grok-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the antigravity-implementer (Gemini) lane in a race. Follow your agent pattern: write the spec to a mktemp file, drive \`agy -p "$(cat "$SPEC")" --mode accept-edits --add-dir "$(pwd)" --print-timeout 10m\` through the authenticated Antigravity default model to implement it in your worktree. After agy finishes, capture every change, including untracked files, with \`${captureDiff(diffPaths.agy)}\`, re-run the verification command YOURSELF (agy's claim is not evidence), and return the structured report with diffPath=${diffPaths.agy}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'agy-lane [Gemini / Antigravity default]', phase: 'Race', agentType: 'antigravity-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
])

const valid = lanes.filter(Boolean).filter(l => l.status && l.status !== 'unavailable' && l.diffPath)
log(`Race complete: ${valid.length}/${lanes.length} lanes produced a diff`)

if (valid.length === 0) {
  return { lanes: lanes.filter(Boolean), judge: { winner: 'none', reasoning: 'all lanes unavailable or produced no diff — likely the cwd is not a git repo (cd into one) or the vendor CLIs are down (see each lane STATUS/REASON)', winningDiffPath: 'none' }, verify: null }
}

phase('Judge')
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    winner: { type: 'string', enum: ['sonnet', 'codex', 'grok', 'agy', 'none'] },
    winningDiffPath: { type: 'string', description: 'path to the diff the architect should apply, or "none"' },
    reasoning: { type: 'string', description: 'why this winner; cite specific diff content' },
    risks: { type: 'string', description: 'the single risk to watch in the winning diff, or "none"' },
  },
  required: ['winner', 'winningDiffPath', 'reasoning'],
}
// Judge on opus-tier: Opus 4.8 under Max, glm-5.2 under glm (opus is model-mapped in both envs; not Fable-pinned, which z.ai lacks).
const judge = await agent(
  `You are the judge. Four lanes (Claude Sonnet, GPT-5.6-Sol via codex, Grok via grok, Gemini via agy) implemented the same spec independently. Read each lane's diff file (use the Read tool on each diffPath) and compare against the spec. Pick the single strongest diff. Set winner="none" only if every diff is flawed; otherwise pick exactly one of sonnet/codex/grok/agy and set winningDiffPath to that lane's diffPath.\n\nSPEC:\n${spec}\n\nLANE REPORTS:\n${JSON.stringify(valid, null, 2)}\n\nRead every diffPath before deciding. The architect will apply winningDiffPath to the main tree, so be precise.`,
  { label: 'judge [opus]', phase: 'Judge', model: 'opus', schema: JUDGE_SCHEMA }
)

phase('Verify')
const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['sound', 'flawed'] },
    keyFailure: { type: 'string', description: 'the single most important issue with a concrete failing scenario, or "no blocking issue found"' },
    glmSaid: { type: 'string', description: 'one-line summary of GLM\'s verdict' },
  },
  required: ['verdict', 'keyFailure'],
}
let verify = null
if (judge && judge.winningDiffPath && judge.winningDiffPath !== 'none') {
  verify = await agent(
    `You are the cross-vendor adversarial verifier (GLM-5.2 via z.ai — the 5th model family, subscription-authed). Read the winning diff at ${judge.winningDiffPath} (use Read). Then drive glm per your agent pattern: write a review request to a mktemp file and run \`glm --model opus -p "$(cat "$REQ")"\` asking GLM to BREAK the diff — find correctness bugs, spec violations, edge cases the verification command wouldn't catch, silent failures. Return the structured verdict (sound|flawed + key failure).\n\nORIGINAL SPEC:\n${spec}\n\nWINNING DIFF PATH: ${judge.winningDiffPath}`,
    { label: 'glm-verify [GLM-5.2]', phase: 'Verify', agentType: 'glm-longcontext', schema: VERIFY_SCHEMA }
  )
} else {
  log('No winning diff — skipping adversarial verify')
}

return {
  lanes: valid,
  judge,
  verify,
  nextStep: (judge && judge.winningDiffPath && judge.winningDiffPath !== 'none')
    ? `Architect: apply ${judge.winningDiffPath} to the main tree (\`git apply ${judge.winningDiffPath}\`), then re-run verification: ${verifyCmd}`
    : 'Architect: no winning diff — revise the spec (consult fable-advisor) and re-run.',
}
