import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import test from 'node:test'
import vm from 'node:vm'

const ROOT = path.resolve(import.meta.dirname, '..')
const WORKFLOW = path.join(ROOT, 'workflows', 'race-and-judge.mjs')
const APPLY = path.join(ROOT, 'bin', 'apply-race-artifact')
const MAX_ARTIFACT_BYTES = 80_000
const LANES = ['fable', 'codex', 'grok']

const TEXT_PATCH = [
  'diff --git a/example.txt b/example.txt',
  'index 7898192..422c2b7 100644',
  '--- a/example.txt',
  '+++ b/example.txt',
  '@@ -1 +1 @@',
  '-old',
  '+new',
  '',
].join('\n')

function sha256(text) {
  return createHash('sha256').update(text, 'utf8').digest('hex')
}

function loadWorkflow() {
  const source = readFileSync(WORKFLOW, 'utf8').replace('export const meta =', 'const meta =')
  return async (args, agent, parallel, pipeline, phase, log, budget) => {
    const context = vm.createContext({ args, agent, parallel, pipeline, phase, log, budget })
    assert.equal(vm.runInContext('typeof process', context), 'undefined')
    vm.runInContext(`
      const RuntimeDate = Date
      globalThis.Date = class extends RuntimeDate {
        constructor(...values) {
          if (values.length === 0) throw new Error('new Date() unavailable in Workflow runtime')
          super(...values)
        }
        static now() { throw new Error('Date.now() unavailable in Workflow runtime') }
      }
      Math.random = () => { throw new Error('Math.random() unavailable in Workflow runtime') }
    `, context)
    return vm.runInContext(`(async () => { 'use strict'; ${source}\n})()`, context)
  }
}

async function runFixture(options = {}) {
  const raceRunId = options.raceRunId || `offline-${process.pid}-${Math.random().toString(16).slice(2)}`
  const raceDir = path.join('/tmp', `omnicode-race-${raceRunId}`)
  mkdirSync(raceDir, { recursive: true })
  const artifactPaths = Object.fromEntries(LANES.map((lane) => [lane, path.join(raceDir, `${lane}.diff`)]))
  for (const lane of LANES) writeFileSync(artifactPaths[lane], options.artifacts?.[lane] ?? TEXT_PATCH, 'utf8')
  if (options.prepare) options.prepare({ raceDir, artifactPaths })

  const laneReturns = new Map()
  const calls = []
  const agent = async (prompt, opts = {}) => {
    calls.push({ prompt, opts })
    const lane = LANES.find((candidate) => opts.label?.startsWith(`${candidate}-lane`))
    if (lane) {
      const result = {
        lane,
        status: 'complete',
        summary: `${lane} implementation`,
        diffPath: artifactPaths[lane],
        completeArtifactText: options.reportedArtifacts?.[lane] ?? options.artifacts?.[lane] ?? TEXT_PATCH,
        verified: true,
        verifiedOutput: 'offline proof passed',
        gaps: 'none',
        ...(options.laneOverrides?.[lane] || {}),
      }
      laneReturns.set(lane, result)
      return result
    }

    if (opts.label?.startsWith('judge ')) {
      const winner = options.judge?.winner ?? 'fable'
      const returned = laneReturns.get(winner)
      const text = returned?.completeArtifactText ?? ''
      return {
        winner,
        winningDiffPath: options.judge?.winningDiffPath ?? artifactPaths[winner],
        reasoning: 'offline judge inspected the complete patch',
        risks: 'none',
        reviewedArtifactSha256: sha256(text),
        reviewedArtifactBytes: Buffer.byteLength(text),
        reviewedCompleteArtifact: true,
        ...options.judge,
      }
    }

    if (opts.label?.startsWith('glm-verify ')) {
      const winner = options.judge?.winner ?? 'fable'
      const returned = laneReturns.get(winner)
      const text = returned?.completeArtifactText ?? ''
      return {
        verdict: 'sound',
        keyFailure: 'no blocking issue found',
        glmSaid: 'offline verification passed',
        verifyCmdPassed: true,
        verifyCmdOutput: 'offline proof passed',
        artifactPathVerified: true,
        verifiedArtifactSha256: sha256(text),
        verifiedArtifactBytes: Buffer.byteLength(text),
        verifiedCompleteArtifact: true,
        ...options.verify,
      }
    }

    throw new Error(`unexpected agent call: ${opts.label}`)
  }

  const parallel = (thunks) => Promise.all(thunks.map(async (thunk) => {
    try { return await thunk() } catch { return null }
  }))
  const workflow = loadWorkflow()
  try {
    const result = await workflow(
      { spec: 'offline five-part spec', verifyCmd: 'true', raceRunId },
      agent,
      parallel,
      async (items, ...stages) => {
        const results = []
        for (let index = 0; index < items.length; index += 1) {
          let value = items[index]
          for (const stage of stages) value = await stage(value, items[index], index)
          results.push(value)
        }
        return results
      },
      () => {},
      () => {},
      { total: null, spent: () => 0, remaining: () => Infinity },
    )
    return { result, calls, raceDir, artifactPaths }
  } catch (error) {
    rmSync(raceDir, { recursive: true, force: true })
    throw error
  }
}

function cleanup(fixture) {
  rmSync(fixture.raceDir, { recursive: true, force: true })
}

test('requires an explicit safe invocation id so race artifact paths cannot be silently reused', async () => {
  const workflow = loadWorkflow()
  const noop = () => {}
  await assert.rejects(
    workflow(
      { spec: 'offline five-part spec', verifyCmd: 'true' },
      async () => { throw new Error('agent must not run') },
      async () => [],
      async () => [],
      noop,
      noop,
      { total: null, spent: () => 0, remaining: () => Infinity },
    ),
    /raceRunId/,
  )
})

test('binds each lane to its trusted artifact and reviews every byte before readiness', async () => {
  const fixture = await runFixture()
  try {
    assert.equal(fixture.result.readyToApply, true)
    assert.equal(fixture.result.judge.winner, 'fable')
    assert.equal(fixture.result.judge.winningDiffPath, fixture.artifactPaths.fable)
    assert.equal(fixture.result.apply.artifactSha256, sha256(TEXT_PATCH))
    assert.equal(fixture.result.apply.artifactBytes, Buffer.byteLength(TEXT_PATCH))
    const judgeCall = fixture.calls.find((call) => call.opts.label?.startsWith('judge '))
    assert.match(judgeCall.prompt, new RegExp(sha256(TEXT_PATCH)))
    assert.match(judgeCall.prompt, /diff --git a\/example\.txt b\/example\.txt/)
    for (const lane of LANES) {
      const laneCall = fixture.calls.find((call) => call.opts.label?.startsWith(`${lane}-lane`))
      assert.match(laneCall.prompt, /completeArtifactText/)
      assert.match(laneCall.prompt, /test ! -e/)
    }
    assert.deepEqual(
      fixture.calls.map((call) => call.opts.label),
      [
        'fable-lane [Claude Fable 5.1]',
        'codex-lane [GPT-6 Astra]',
        'grok-lane [Grok]',
        'judge [Fable 5.1]',
        'glm-verify [GLM-5.3]',
      ],
    )
  } finally { cleanup(fixture) }
})

test('workflow UTF-8 byte count and digest match the deterministic apply helper inputs', async () => {
  const unicodePatch = TEXT_PATCH.replace('+new', '+ny hjerne 🧠')
  const fixture = await runFixture({
    artifacts: Object.fromEntries(LANES.map((lane) => [lane, unicodePatch])),
  })
  try {
    assert.equal(fixture.result.apply.artifactBytes, Buffer.byteLength(unicodePatch, 'utf8'))
    assert.equal(fixture.result.apply.artifactSha256, sha256(unicodePatch))
  } finally { cleanup(fixture) }
})

test('rejects forged paths and duplicate or forged lane identities', async () => {
  const fixture = await runFixture({
    laneOverrides: {
      codex: { lane: 'fable' },
      grok: { diffPath: '/tmp/forged.diff' },
    },
  })
  try {
    assert.equal(fixture.result.eligible.length, 0)
    assert.equal(fixture.result.lanes.find((entry) => entry.lane === 'fable').rejection, 'duplicate lane identity')
    assert.equal(fixture.result.lanes.find((entry) => entry.lane === 'codex').rejection, 'lane identity mismatch')
    assert.equal(fixture.result.lanes.find((entry) => entry.lane === 'grok').rejection, 'artifact path mismatch')
  } finally { cleanup(fixture) }
})

test('rejects oversized, empty, and binary returned artifacts before judging', async () => {
  const fixture = await runFixture({
    reportedArtifacts: {
      fable: 'x'.repeat(MAX_ARTIFACT_BYTES + 1),
      codex: '',
      grok: `${TEXT_PATCH}GIT binary patch\nliteral 1\nAcmZQz\n`,
    },
    judge: { winner: 'none' },
  })
  try {
    assert.equal(fixture.result.eligible.length, 0)
    assert.equal(fixture.calls.some((call) => call.opts.label?.startsWith('judge ')), false)
    assert.match(fixture.result.lanes.find((entry) => entry.lane === 'fable').rejection, /size cap/)
    assert.match(fixture.result.lanes.find((entry) => entry.lane === 'codex').rejection, /empty/)
    assert.match(fixture.result.lanes.find((entry) => entry.lane === 'grok').rejection, /binary/)
  } finally { cleanup(fixture) }
})

test('requires judge and verifier to bind their decisions to the workflow-computed digest', async () => {
  const badJudge = await runFixture({ judge: { reviewedArtifactSha256: '0'.repeat(64) } })
  try {
    assert.equal(badJudge.result.judge.winner, 'none')
    assert.equal(badJudge.result.readyToApply, false)
    assert.equal(badJudge.calls.some((call) => call.opts.label?.startsWith('glm-verify ')), false)
  } finally { cleanup(badJudge) }

  const badVerify = await runFixture({ verify: { verifiedArtifactSha256: 'f'.repeat(64) } })
  try {
    assert.equal(badVerify.result.readyToApply, false)
    assert.match(badVerify.result.nextStep, /Do not apply/)
  } finally { cleanup(badVerify) }
})

test('guarded apply replaces model capture and seal: it rejects missing, outside, symlinked, or mutated artifacts and applies exact reviewed bytes', () => {
  const temp = path.join(tmpdir(), `omnicode-apply-${process.pid}-${Math.random().toString(16).slice(2)}`)
  const repo = path.join(temp, 'repo')
  const raceDir = path.join(temp, 'race')
  mkdirSync(repo, { recursive: true })
  mkdirSync(raceDir, { recursive: true })
  spawnSync('git', ['init', '-q'], { cwd: repo })
  spawnSync('git', ['config', 'user.email', 'offline@example.invalid'], { cwd: repo })
  spawnSync('git', ['config', 'user.name', 'Offline Test'], { cwd: repo })
  writeFileSync(path.join(repo, 'example.txt'), 'old\n')
  spawnSync('git', ['add', 'example.txt'], { cwd: repo })
  spawnSync('git', ['commit', '-qm', 'fixture'], { cwd: repo })
  const artifact = path.join(raceDir, 'fable.diff')
  const common = ['--race-dir', raceDir, '--artifact', artifact, '--sha256', sha256(TEXT_PATCH), '--bytes', String(Buffer.byteLength(TEXT_PATCH)), '--verify-cmd', 'true']
  try {
    const missing = spawnSync(APPLY, common, { cwd: repo, encoding: 'utf8' })
    assert.equal(missing.error, undefined)
    assert.notEqual(missing.status, 0)
    assert.equal(readFileSync(path.join(repo, 'example.txt'), 'utf8'), 'old\n')

    writeFileSync(artifact, `${TEXT_PATCH}# mutated\n`)
    const mutated = spawnSync(APPLY, common, { cwd: repo, encoding: 'utf8' })
    assert.equal(mutated.error, undefined)
    assert.notEqual(mutated.status, 0)
    assert.equal(readFileSync(path.join(repo, 'example.txt'), 'utf8'), 'old\n')

    const outside = path.join(temp, 'outside.diff')
    writeFileSync(outside, TEXT_PATCH)
    const escaped = spawnSync(APPLY, ['--race-dir', raceDir, '--artifact', outside, '--sha256', sha256(TEXT_PATCH), '--bytes', String(Buffer.byteLength(TEXT_PATCH)), '--verify-cmd', 'true'], { cwd: repo, encoding: 'utf8' })
    assert.equal(escaped.error, undefined)
    assert.notEqual(escaped.status, 0)
    assert.equal(readFileSync(path.join(repo, 'example.txt'), 'utf8'), 'old\n')

    rmSync(artifact)
    symlinkSync(outside, artifact)
    const symlinked = spawnSync(APPLY, common, { cwd: repo, encoding: 'utf8' })
    assert.equal(symlinked.error, undefined)
    assert.notEqual(symlinked.status, 0)
    assert.equal(readFileSync(path.join(repo, 'example.txt'), 'utf8'), 'old\n')

    rmSync(artifact)
    writeFileSync(artifact, TEXT_PATCH)
    const failedProof = spawnSync(APPLY, [...common.slice(0, -1), 'false'], { cwd: repo, encoding: 'utf8' })
    assert.equal(failedProof.error, undefined)
    assert.notEqual(failedProof.status, 0)
    assert.equal(readFileSync(path.join(repo, 'example.txt'), 'utf8'), 'old\n')
    assert.equal(spawnSync('git', ['status', '--porcelain=v1'], { cwd: repo, encoding: 'utf8' }).stdout, '')

    const applied = spawnSync(APPLY, common, { cwd: repo, encoding: 'utf8' })
    assert.equal(applied.error, undefined)
    assert.equal(applied.status, 0, applied.stderr)
    assert.equal(readFileSync(path.join(repo, 'example.txt'), 'utf8'), 'new\n')
    assert.equal(spawnSync('git', ['diff', '--cached', '--quiet'], { cwd: repo }).status, 1)
  } finally { rmSync(temp, { recursive: true, force: true }) }
})
