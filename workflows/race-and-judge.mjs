// omnicode (race-and-judge.mjs) — high-stakes race across four model families.
// Invoke from a clean GIT REPO cwd:
//   Workflow({ scriptPath: '~/.claude/workflows/race-and-judge.mjs', args: { spec: '<five-part spec>', verifyCmd: '<trusted command>' } })
// Race: Claude Fable 5.1 + GPT-6 Astra max + Grok 4.6 xhigh. Judge: Fable 5.1. Verify: GLM-5.3 max.
// State across the race is the spec + each lane's diffText. Implementations stay isolated.
// The architect applies a winner only when verification is sound AND verifyCmdPassed, then re-runs verifyCmd.

export const meta = {
  name: 'omnicode',
  description: 'Race Fable 5.1, GPT-6 Astra max, and Grok 4.6 xhigh in isolated worktrees; Fable 5.1 judges; GLM-5.3 max verifies.',
  phases: [
    { title: 'Race', detail: '3 implementer lanes in parallel (Claude/GPT/Grok), each in its own git worktree' },
    { title: 'Judge', detail: 'Fable 5.1 reads every eligible diffText and picks one' },
    { title: 'Verify', detail: 'GLM-5.3 adversarially verifies the winner and re-runs the trusted proof command' },
  ],
}

const spec = (args && args.spec) ? args.spec : ''
const verifyCmd = (args && args.verifyCmd) ? args.verifyCmd : ''
if (!spec) { log('ABORT: no args.spec'); throw new Error('race-and-judge requires args.spec (five-part spec text)') }
if (!verifyCmd) { log('ABORT: no args.verifyCmd'); throw new Error('race-and-judge requires args.verifyCmd (trusted verification command)') }

const raceRunId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
const raceDir = `/tmp/omnicode-race-${raceRunId}`
const diffPaths = {
  fable: `${raceDir}/fable.diff`,
  codex: `${raceDir}/codex.diff`,
  grok: `${raceDir}/grok.diff`,
}
const captureDiff = (diffPath) => `mkdir -p "${raceDir}" && git add -A && git diff --cached --binary HEAD -- > "${diffPath}"`
const isolation = `Do not read ${raceDir} except your own output file. Do not search the filesystem for hidden tests, oracles, or reference solutions. Other lanes' work is off-limits.`
const fillDiffText = (diffPath) => `After capturing the diff, set diffText to the first 80000 characters of a text unified diff: git diff --cached HEAD -- . (no --binary). If empty, status cannot be complete.`

const LANE_SCHEMA = {
  type: 'object',
  properties: {
    lane: { type: 'string', enum: ['fable', 'codex', 'grok'] },
    status: { type: 'string', enum: ['complete', 'partial', 'timeout', 'unavailable'] },
    summary: { type: 'string', description: 'one-line restatement of what was implemented' },
    diffPath: { type: 'string', description: 'absolute path to the captured staged binary diff' },
    diffText: { type: 'string', description: 'unified text diff served to the judge; required for complete' },
    verified: { type: 'boolean', description: 'did the lane supervisor re-run verification and see it pass?' },
    verifiedOutput: { type: 'string', description: 'actual output from the re-run' },
    gaps: { type: 'string', description: 'unfinished items or "none"' },
  },
  required: ['lane', 'status', 'summary', 'diffPath', 'diffText', 'verified', 'gaps'],
}

phase('Race')
const lanes = await parallel([
  () => agent(
    `You are the Claude Fable 5.1 implementation lane in a high-stakes race. Implement the five-part spec in your isolated worktree. ${isolation} Re-run the trusted verification command and record its actual output. Only after verification, capture every change including untracked files with \`${captureDiff(diffPaths.fable)}\`. ${fillDiffText(diffPaths.fable)} Return lane="fable" and diffPath=${diffPaths.fable}. Never claim success from model judgment alone.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'fable-lane [Claude Fable 5.1]', phase: 'Race', model: 'claude-fable-5-1', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the codex-implementer lane in a high-stakes race. ${isolation} Follow the current agent pattern and drive Codex with the prompt as its final positional argument: \`codex exec --ignore-user-config -m gpt-6-astra -c model_reasoning_effort=max -c model_context_window=272000 -c approval_policy="never" -s workspace-write --skip-git-repo-check -C "$(pwd)" -o "$FINAL" "$(cat "$SPEC")"\`. Never use stdin redirection. Re-run the trusted verification command yourself. Only after verification, capture every change with \`${captureDiff(diffPaths.codex)}\`. ${fillDiffText(diffPaths.codex)} Return lane="codex" and diffPath=${diffPaths.codex}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'codex-lane [GPT-6 Astra]', phase: 'Race', agentType: 'codex-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
  () => agent(
    `You are the grok-implementer lane in a high-stakes race. ${isolation} Drive Grok 4.6 at its maximum single-model reasoning depth with \`grok --prompt-file "$SPEC" -m grok-4.6 --reasoning-effort xhigh --permission-mode acceptEdits --output-format plain --cwd "$(pwd)" --no-plan --max-turns 120 --no-memory --no-subagents --disable-web-search\`. Re-run the trusted verification command yourself. Only after verification, capture every change with \`${captureDiff(diffPaths.grok)}\`. ${fillDiffText(diffPaths.grok)} Return lane="grok" and diffPath=${diffPaths.grok}.\n\nVERIFICATION COMMAND: ${verifyCmd}\n\nSPEC:\n${spec}`,
    { label: 'grok-lane [Grok]', phase: 'Race', agentType: 'grok-implementer', isolation: 'worktree', schema: LANE_SCHEMA }
  ),
])

// Fail closed: partial, timed-out, unavailable, unverified, or empty-diff candidates never reach the judge.
const eligible = lanes.filter(Boolean).filter(l =>
  l.status === 'complete' && l.verified === true && l.diffPath && typeof l.diffText === 'string' && l.diffText.trim().length > 0
)
log(`Race complete: ${eligible.length}/${lanes.length} lanes are complete, independently verified, and served a diff`)

if (eligible.length === 0) {
  return {
    raceRunId,
    lanes: lanes.filter(Boolean),
    judge: { winner: 'none', reasoning: 'No lane completed with independent verification and a served diff.', winningDiffPath: 'none' },
    verify: null,
    readyToApply: false,
    nextStep: 'Do not apply a diff. Fix lane availability/spec/verification and re-run.',
  }
}

phase('Judge')
const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    winner: { type: 'string', enum: ['fable', 'codex', 'grok', 'none'] },
    winningDiffPath: { type: 'string', description: 'candidate diff path; normalized by the workflow before use' },
    reasoning: { type: 'string', description: 'why this winner; cite specific diff content' },
    risks: { type: 'string', description: 'single risk to watch, or "none"' },
  },
  required: ['winner', 'winningDiffPath', 'reasoning'],
}
const judgePayload = eligible.map(l => ({
  lane: l.lane,
  summary: l.summary,
  diffPath: l.diffPath,
  verifiedOutput: l.verifiedOutput || '',
  gaps: l.gaps,
  diffText: l.diffText,
}))
const rawJudge = await agent(
  `You are the judge. The implementers cannot see each other. You are given each eligible lane's actual diffText — compare those diffs to the five-part spec and pick exactly one, or winner="none" if all are flawed. Do not trust summaries or verification claims instead of the diffText. Cite concrete hunks.\n\nSPEC:\n${spec}\n\nELIGIBLE CANDIDATES:\n${JSON.stringify(judgePayload, null, 2)}`,
  { label: 'judge [Fable 5.1]', phase: 'Judge', model: 'fable', schema: JUDGE_SCHEMA }
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
    verifyCmdPassed: { type: 'boolean', description: 'true only if you re-ran the trusted verification command and it exited 0' },
    verifyCmdOutput: { type: 'string', description: 'actual stdout/stderr from that re-run' },
  },
  required: ['verdict', 'keyFailure', 'verifyCmdPassed', 'verifyCmdOutput'],
}
let verify = null
if (winningLane) {
  verify = await agent(
    `You are the cross-vendor adversarial verifier using GLM-5.3. The winner's diffText is inlined below — do not skip it. Drive glm with \`glm --model opus -p "$(cat "$REQ")"\` to try to break the change: correctness bugs, spec violations, edge cases, silent failures. Then YOU must re-run this trusted verification command in the winner's tree (or after applying the diff to a throwaway copy) and record the actual output: ${verifyCmd}\nReturn sound only when no blocking issue is found AND verifyCmdPassed is true. A prose review without a command re-run is flawed.\n\nORIGINAL SPEC:\n${spec}\n\nWINNING LANE: ${winningLane.lane}\nWINNING DIFF PATH: ${winningLane.diffPath}\n\nWINNING DIFF TEXT:\n${winningLane.diffText}`,
    { label: 'glm-verify [GLM-5.3]', phase: 'Verify', agentType: 'glm-longcontext', schema: VERIFY_SCHEMA }
  )
} else {
  log('Judge produced no valid winner — skipping adversarial verify')
}

const readyToApply = Boolean(
  winningLane &&
  verify &&
  verify.verdict === 'sound' &&
  verify.verifyCmdPassed === true
)
return {
  raceRunId,
  lanes: lanes.filter(Boolean).map(l => ({
    lane: l.lane,
    status: l.status,
    summary: l.summary,
    diffPath: l.diffPath,
    verified: l.verified,
    gaps: l.gaps,
    diffChars: typeof l.diffText === 'string' ? l.diffText.length : 0,
  })),
  eligible: eligible.map(l => ({ lane: l.lane, diffPath: l.diffPath, diffChars: l.diffText.length })),
  judge: normalizedJudge,
  verify,
  readyToApply,
  nextStep: readyToApply
    ? `Architect: apply ${winningLane.diffPath} to the main tree, inspect the result, then re-run: ${verifyCmd}`
    : 'Do not apply the candidate. Need a served diff, a Fable pick, GLM sound, and verifyCmdPassed=true.',
}
