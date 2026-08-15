// omnicode (race-and-judge.mjs) — high-stakes race across four model families.
// Invoke from a clean GIT REPO cwd:
//   Workflow({ scriptPath: '~/.claude/workflows/race-and-judge.mjs', args: { spec: '<five-part spec>', verifyCmd: '<trusted command>' } })
// Race: Claude Opus + Codex/GPT-5.6-Sol + Grok. Judge: Opus-tier. Verify: GLM-5.3.
// The architect applies a winner only when verification is sound, then re-runs verifyCmd.

export const meta = {
  name: 'omnicode',
  description: 'Race Claude Opus, Codex, and Grok in isolated worktrees; Opus judges; GLM adversarially verifies. Fails closed before apply.',
  phases: [
    { title: 'Race', detail: '3 implementer lanes in parallel (Claude/GPT/Grok), each in its own git worktree' },
    { title: 'Judge', detail: 'Opus-tier model reads every eligible diff and picks one' },
    { title: 'Verify', detail: 'GLM-5.3 adversarially verifies the winner before any apply instruction' },
  ],
}

const spec = (args && args.spec) ? args.spec : ''
const verifyCmd = (args && args.verifyCmd) ? args.verifyCmd : ''
if (!spec) { log('ABORT: no args.spec'); throw new Error('race-and-judge requires args.spec (five-part spec text)') }
if (!verifyCmd) { log('ABORT: no args.verifyCmd'); throw new Error('race-and-judge requires args.verifyCmd (trusted verification command)') }

const raceRunId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
const raceDir = `/tmp/omnicode-race-${raceRunId}`
const diffPaths = {
  opus: `${raceDir}/opus.diff`,
  codex: `${raceDir}/codex.diff`,
  grok: `${raceDir}/grok.diff`,
}
const captureDiff = (diffPath) => `mkdir -p "${raceDir}" && git add -A && git diff --cached --binary HEAD -- > "${diffPath}"`

const LANE_SCHEMA = {
  type: 'object',
  properties: {
    lane: { type: 'string', enum: ['opus', 'codex', 'grok'] },
    status: { type: 'string', enum: ['complete', 'partial', 'timeout', 'unavailable'] },
    summary: { type: 'string', description: 'one-line restatement of what was implemented' },
    diffPath: { type: 'string', description: 'absolute path to the captured staged binary diff' },
    verified: { type: 'boolean', description: 'did the lane supervisor re-run verification and see it pass?' },
    verifiedOutput: { type: 'string', description: 'actual output from the re-run' },
    gaps: { type: 'string', description: 'unfinished items or "none"' },
  },
  required: ['lane', 'status', 'summary', 'diffPath', 'verified', 'gaps'],
}

phase('Race')
const lanes = await parallel([
  () => agent(
    `You are the Claude Opus implementation lane in a high-stakes race. Implement the five-part spec in your isolated worktree. Re-run the trusted verification command and record its actual output. Only after verification, capture every change including untracked files with \`${captureDiff(diffPaths.opus)}\`. Return lane="opus" and diffPath=${diffPaths.opus}. Never claim success from model judgment alone.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'opus-lane [Claude Opus]', phase: 'Race', model: 'opus', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the codex-implementer lane in a high-stakes race. Follow the current agent pattern and drive Codex with the prompt as its final positional argument: \`codex exec --ignore-user-config -m gpt-5.6-sol -c model_reasoning_effort=max -c model_context_window=272000 -c approval_policy="never" -s workspace-write --skip-git-repo-check -C "$(pwd)" -o "$FINAL" "$(cat "$SPEC")"\`. Never use stdin redirection. Re-run the trusted verification command yourself. Only after verification, capture every change with \`${captureDiff(diffPaths.codex)}\`. Return lane="codex" and diffPath=${diffPaths.codex}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'codex-lane [GPT-5.6-Sol]', phase: 'Race', agentType: 'codex-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the grok-implementer lane in a high-stakes race. Follow the current agent pattern and drive Grok with \`grok --prompt-file "$SPEC" -m grok-4.5 --permission-mode acceptEdits --output-format plain --cwd "$(pwd)"\`. Re-run the trusted verification command yourself. Only after verification, capture every change with \`${captureDiff(diffPaths.grok)}\`. Return lane="grok" and diffPath=${diffPaths.grok}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'grok-lane [Grok]', phase: 'Race', agentType: 'grok-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
])

// Fail closed: partial, timed-out, unavailable, or self-unverified candidates do not reach the judge.
const eligible = lanes.filter(Boolean).filter(l => l.status === 'complete' && l.verified === true && l.diffPath)
log(`Race complete: ${eligible.length}/${lanes.length} lanes are complete and independently verified`)

if (eligible.length === 0) {
  return {
    lanes: lanes.filter(Boolean),
    judge: { winner: 'none', reasoning: 'No lane completed with independent verification.', winningDiffPath: 'none' },
    verify: null,
    readyToApply: false,
    nextStep: 'Do not apply a diff. Fix lane availability/spec/verification and re-run.',
  }
}

phase('Judge')
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    winner: { type: 'string', enum: ['opus', 'codex', 'grok', 'none'] },
    winningDiffPath: { type: 'string', description: 'candidate diff path; normalized by the workflow before use' },
    reasoning: { type: 'string', description: 'why this winner; cite specific diff content' },
    risks: { type: 'string', description: 'single risk to watch, or "none"' },
  },
  required: ['winner', 'winningDiffPath', 'reasoning'],
}
const rawJudge = await agent(
  `You are the judge. Read every eligible diffPath and compare it against the five-part spec. Pick exactly one eligible lane, or winner="none" if all are flawed. Do not trust summaries or verification claims instead of reading diffs.\n\nSPEC:\n${spec}\n\nELIGIBLE LANE REPORTS:\n${JSON.stringify(eligible, null, 2)}`,
  { label: 'judge [Opus]', phase: 'Judge', model: 'opus', schema: JUDGE_SCHEMA }
)

// Never trust a model-returned path. Resolve the path from the known eligible lane record.
const winningLane = rawJudge && rawJudge.winner !== 'none'
  ? eligible.find(l => l.lane === rawJudge.winner)
  : null
const normalizedJudge = {
  ...(rawJudge || { winner: 'none', reasoning: 'Judge returned no result.' }),
  winner: winningLane ? winningLane.lane : 'none',
  winningDiffPath: winningLane ? winningLane.diffPath : 'none',
}

phase('Verify')
const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['sound', 'flawed'] },
    keyFailure: { type: 'string', description: 'most important concrete issue, or "no blocking issue found"' },
    glmSaid: { type: 'string', description: 'one-line summary of GLM verdict' },
  },
  required: ['verdict', 'keyFailure'],
}
let verify = null
if (winningLane) {
  verify = await agent(
    `You are the cross-vendor adversarial verifier using GLM-5.3. Read ${winningLane.diffPath}, then drive glm with \`glm --model opus -p "$(cat "$REQ")"\` to try to break the diff: correctness bugs, spec violations, edge cases, and silent failures. Return sound only when no blocking issue is found.\n\nORIGINAL SPEC:\n${spec}\n\nWINNING DIFF PATH: ${winningLane.diffPath}`,
    { label: 'glm-verify [GLM-5.3]', phase: 'Verify', agentType: 'glm-longcontext', schema: VERIFY_SCHEMA }
  )
} else {
  log('Judge produced no valid winner — skipping adversarial verify')
}

const readyToApply = Boolean(winningLane && verify && verify.verdict === 'sound')
return {
  lanes: lanes.filter(Boolean),
  eligible,
  judge: normalizedJudge,
  verify,
  readyToApply,
  nextStep: readyToApply
    ? `Architect: apply ${winningLane.diffPath} to the main tree, inspect the result, then re-run: ${verifyCmd}`
    : 'Do not apply the candidate. The judge or adversarial verifier did not produce a sound, eligible winner.',
}
