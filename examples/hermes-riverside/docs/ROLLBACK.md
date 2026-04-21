# Rollback Plan — Hermes Substation Atlas (Phase 1a)

The autoresearch loop can ship bad playbook edits, exhaust credentials, or
break the eval harness in a way that silently degrades scores. This doc is
the recipe for undoing each class of failure. Every rollback here is
reversible by the same path in reverse.

## Severity ladder

| Level | Symptom | First move | Time-to-safe |
|---|---|---|---|
| 1 | Autoresearch proposing bad edits but gate rejects | `hermes autoresearch status` to confirm, no-op | ~30 s |
| 2 | Autoresearch accepted a bad edit, minor diff, auto-committed | `git revert` the commit on the `autoresearch/YYYY-MM-DD` branch | ~2 min |
| 3 | Autoresearch opened a bad PR against main | Close PR, delete branch | ~1 min |
| 4 | Bad edit merged to main | `git revert <merge-sha>` on main; force-push blocked by protection | ~5 min |
| 5 | PAT compromised | Revoke PAT in GitHub, delete all `autoresearch/*` branches | ~10 min |
| 6 | Schema change breaks existing playbooks | Revert the schema commit; retest | ~2 min |
| 7 | Eval harness change causes silent regression | Revert `evals/scoring.py` and `evals/run.py`; re-run tests | ~2 min |

## Level 1 — Bad proposals, gate rejecting

**Confirm posture:**
```
hermes autoresearch status
```
If `halted: False` and the ledger shows recent `rejected_proposal` /
`reject_regression` entries, the gate is doing its job. No action needed.

If you want to stop the loop while you investigate:
```
hermes autoresearch halt --reason "investigating recent rejections"
```
The next cron will see `halted: True` and exit early. Un-halt when done:
```
hermes autoresearch unhalt
```

## Level 2 — Accepted minor edit is bad

The edit lives on `autoresearch/YYYY-MM-DD`. The current HEAD of that branch
has the bad commit. Check out the branch locally, revert the commit, push.

```
git fetch origin
git checkout autoresearch/2026-04-21
git log --oneline -5             # find the bad SHA
git revert <bad-sha>              # creates a new revert commit
git push
hermes autoresearch halt --reason "reverted bad minor edit <bad-sha>"
```

`hermes autoresearch halt` prevents the next cron from stacking another
edit on top while you decide whether to patch the root cause. Un-halt
when ready.

**If the edit is one of many on that branch and only one is bad:**
Same flow with `git revert <specific-sha>` — the other edits stay.

**If the branch has ONLY bad commits:**
```
git push origin --delete autoresearch/2026-04-21
```

## Level 3 — Bad PR open against main

Close the PR without merging:
```
gh pr close <pr-number> --delete-branch --comment "bad autoresearch proposal"
```
This closes the PR AND deletes the head branch remote. Main is untouched.

Then halt the loop:
```
hermes autoresearch halt --reason "closed bad PR #<N>"
```

## Level 4 — Bad edit merged to main

This should require a human PR approval to reach main, so landing here
means a human reviewer approved something they shouldn't have.

Revert the merge on main:
```
git checkout main
git pull
git revert -m 1 <merge-commit-sha>
git push
```
`-m 1` tells git to revert relative to the first parent of the merge
(main's tip before the merge), which is what you want for a PR merge.

Then halt autoresearch and document the postmortem.

## Level 5 — PAT compromised

Revoke first, investigate second. In GitHub:

1. Open https://github.com/settings/tokens
2. Find the autoresearch PAT, click Delete
3. Every autoresearch push fails from this moment on

Delete all autoresearch branches remotely:
```
git fetch --prune
git branch -r | grep 'origin/autoresearch/' | sed 's|origin/||' | \
  xargs -I{} git push origin --delete {}
```

Halt the loop locally:
```
hermes autoresearch halt --reason "PAT compromised"
```

Rotate: issue a new fine-grained PAT scoped to the DNM repo with
`contents:write` on `autoresearch/*` branches only (not main — that's
still gated by branch protection). Update `~/.hermes/autoresearch.env`
on mini1 (700 perms).

## Level 6 — Schema change breaks existing playbooks

Symptom: `.venv/bin/python -m pytest tests/test_schema.py` fails on the
shipped HERMES-*.md files after a schema edit.

```
cd examples/hermes-riverside
git log --oneline hermes/schema/         # find the schema commit
git revert <schema-commit-sha>
.venv/bin/python -m pytest tests/        # should pass again
```

If the schema change was a bump (0.1 → 0.2) and needed the retrofit to
work: revert the schema commit AND any retrofit commits in the same
reverse order as they landed.

## Level 7 — Eval harness silent regression

Symptom: recent autoresearch iterations ACCEPT edits that a reviewer
judges worse than baseline. Suggests the 4-axis scorer stopped
penalizing something it should.

Halt first:
```
hermes autoresearch halt --reason "investigating scorer regression"
```

Review recent changes to `evals/scoring.py` and `evals/run.py`:
```
git log --oneline --follow examples/hermes-riverside/evals/scoring.py
```

If a commit looks suspicious:
```
git revert <sha>
.venv/bin/python -m pytest examples/hermes-riverside/tests/
```

The regression test on existing `qa_pairs.yaml` should catch most
scorer mistakes — if it didn't, add a new test case that would have
caught this one before un-halting.

## What CAN'T happen at the current posture

- **Autoresearch cannot push to main.** Branch protection on `main`
  requires PR approval. Autoresearch has write access only to
  `autoresearch/*`. This is by design.
- **Autoresearch cannot exceed 3 consecutive regressions before halting.**
  The kill-switch in `hermes/autoresearch/commit.py` sets `halted: True`
  automatically. Manual `hermes autoresearch unhalt` is required to resume.
- **Autoresearch cannot cross MAX_MINOR_LINES without PR review.** Major
  diffs (>20 lines, Identity change, or playbook add/remove) route to
  `gh pr create` and wait for human merge.
- **Autoresearch cannot commit a candidate that fails schema validation.**
  `propose.py` rejects pre-eval; `hermes lint` in CI catches anything that
  survives the proposer.

## Drill

Once a quarter, run through a level-1 and level-2 rollback on the
`autoresearch/drill` branch as a fire drill. The runbook is worth as
much as the last time someone actually did it.

## See also

- `hermes/autoresearch/commit.py` — kill-switch state machine
- `hermes/autoresearch/loop.py` — `auto_push=False` keeps everything
  local during initial rollout
- `hermes/cli.py` — `hermes autoresearch {status, halt, unhalt}`
