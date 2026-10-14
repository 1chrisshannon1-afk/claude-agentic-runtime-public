# Model/effort default regressions — full incident history (from CLAUDE.md §10)

This has regressed FOUR times now (07-09, 07-19, 08-03, and live
  during a session on 08-20 — see `feedback_model_effort_defaults` in memory, which is the accurate
  count; do not undercount it here again): a working-tree-only config fix silently evaporated once, a
  global `model`/`effortLevel` default got folded into an unrelated commit the second time,
  `effortLevel` drifted back to `xhigh` a third time (caught at commit time by `pre_commit_ratchet.py`,
  which exists because of this exact incident), and on 08-20 `settings.json`'s `model`/`effortLevel`
  fields were observed changing TWICE live, mid-session, with no commit and no hook/script in this repo
  writing either field (confirmed by exhaustive grep — investigated and ruled out: `pre_commit_ratchet.py`
  only BLOCKS a bad commit, never writes; `sync_agent_rules.py` is read-only; no cron/launchd agent
  touches it). The evidence points at the Claude Code CLIENT itself (`~/.claude.json`'s
  `orgModelDefaultCache`/`hasResetAutoModeOptInForDefaultOffer` keys suggest an org-level default or
  "Auto mode" pushing a value into `settings.json` from outside any script in this repo) — outside
  this repo's ability to fix; if it recurs, check Auto-mode/org-default settings in the client itself,
  not this repo's hooks. `pre_commit_ratchet.py` (added after the second regression) mechanically
  BLOCKS a `git commit` from re-introducing `effortLevel: "xhigh"` or losing `effortLevel` entirely —
  it cannot stop a live, uncommitted, client-driven rewrite, only a committed one, which is exactly
  what the fourth incident was.
