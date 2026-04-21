# Autoresearch setup — one-time checklist

Everything the autoresearch loop needs before a cron can safely run it. Each
step is reversible by the Rollback doc (`docs/ROLLBACK.md`). Default posture
throughout this setup is **no pushes, no PRs** — the loop commits to local
branches only. You flip `HERMES_AUTO_PUSH=true` in the launchd plist after
you've watched several successful local-only runs.

## 0. Prerequisites

- mini1 is reachable and running Ollama with Gemma 4 E4B installed
- A writable checkout of `Dynamic-Network-Model` under `~/Projects/`
- `.venv` under `examples/hermes-riverside/` with the project installed
  (`python -m venv .venv && .venv/bin/pip install -e .`)

## 1. Branch protection on main (one-time, GitHub UI)

Without this, a future compromised PAT or cron accident could push straight
to main.

1. Open https://github.com/SGridworks/Dynamic-Network-Model/settings/branches
2. Add a branch ruleset or classic protection on `main`
3. Required settings:
   - Require a pull request before merging
   - Require approvals: 1
   - Require status checks to pass before merging
     - Required: `hermes-atlas tests` (from the CI workflow; see step 3)
   - Block force pushes
   - Block deletions

Rollback: just remove the ruleset if you need to.

## 2. Fine-grained PAT (one-time, GitHub UI)

1. https://github.com/settings/personal-access-tokens
2. Generate new token → Fine-grained
3. Name: `hermes-autoresearch`
4. Expiration: 90 days (set a calendar reminder to rotate)
5. Repository access: Only select repositories → `Dynamic-Network-Model`
6. Repository permissions:
   - Contents: Read and write
   - Metadata: Read
   - Pull requests: Read and write
7. Copy the token (starts with `github_pat_...`)

Rollback: delete the token in GitHub settings. See ROLLBACK.md level 5.

## 3. Wire the PAT on mini1

```
mkdir -p ~/.hermes
touch ~/.hermes/autoresearch.env
chmod 700 ~/.hermes
chmod 600 ~/.hermes/autoresearch.env
```

Put in `~/.hermes/autoresearch.env`:

```
GITHUB_TOKEN=github_pat_...
# Optional: override if Ollama is not at the default.
# OLLAMA_BASE_URL=http://10.0.5.1:11434
```

Sanity check:

```
stat -f '%Sp' ~/.hermes/autoresearch.env   # should be -rw-------
```

## 4. Install the launchd plist

```
cd examples/hermes-riverside
sed "s|__USER_HOME__|$HOME|g" \
  scripts/com.sgridworks.hermes-autoresearch.plist.template \
  > ~/Library/LaunchAgents/com.sgridworks.hermes-autoresearch.plist
launchctl load ~/Library/LaunchAgents/com.sgridworks.hermes-autoresearch.plist
launchctl list | grep hermes-autoresearch
```

The default schedule is 02:30 local. First scheduled run is the next 02:30
after install. Don't wait for it — trigger one manually:

```
launchctl start com.sgridworks.hermes-autoresearch
tail -f ~/.hermes/logs/autoresearch-$(date +%Y%m%d).log
```

## 5. Observe local-only runs for ~7 nights

`HERMES_AUTO_PUSH=false` is the default in the plist. The loop will:

- Read shipped HERMES-*.md files
- Compute baseline scores
- Ask the LLM for a proposed edit
- Score the candidate and apply the Pareto gate
- On ACCEPT: commit to `autoresearch/YYYY-MM-DD` locally
- Write per-iteration JSON to `runs/autoresearch/YYYYMMDD/`
- Append to `public/autoresearch-ledger.json`
- **Not push, not open a PR**

Inspect after the first run:

```
hermes autoresearch status
git log --oneline -20 --all | grep autoresearch
cat examples/hermes-riverside/public/autoresearch-ledger.json | jq '.[0]'
```

If anything looks wrong, halt:

```
hermes autoresearch halt --reason "observing initial runs"
```

## 6. Flip to auto-push (only after observation is clean)

Edit `~/Library/LaunchAgents/com.sgridworks.hermes-autoresearch.plist`:

```
<key>HERMES_AUTO_PUSH</key>
<string>true</string>   <!-- was: false -->
```

Reload:

```
launchctl unload ~/Library/LaunchAgents/com.sgridworks.hermes-autoresearch.plist
launchctl load ~/Library/LaunchAgents/com.sgridworks.hermes-autoresearch.plist
```

From this point:

- Minor diffs auto-commit AND push to `autoresearch/YYYY-MM-DD` on origin
- Major diffs auto-commit AND push AND open a PR against `main`
- PRs require your approval before they land (branch protection from step 1)

## 7. CI (already in the repo)

`.github/workflows/hermes-atlas-tests.yml` runs the test suite on every
PR that touches `examples/hermes-riverside/**`. This is the status check
`main` requires before merge.

## Summary

| Step | Where | Reversible |
|---|---|---|
| 1. Branch protection on main | GitHub web UI | remove ruleset |
| 2. Fine-grained PAT | GitHub web UI | delete token |
| 3. `~/.hermes/autoresearch.env` | mini1 | `shred` the file |
| 4. launchd plist | mini1 | `launchctl unload` |
| 5. Local-only observation | logs on mini1 | no change needed |
| 6. Flip HERMES_AUTO_PUSH | plist | flip back to false |
| 7. CI workflow | in repo | revert the commit |

Commit to do each step deliberately; if anything smells wrong at any step,
`hermes autoresearch halt` and investigate before continuing.
