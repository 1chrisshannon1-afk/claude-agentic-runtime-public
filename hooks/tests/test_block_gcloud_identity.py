"""Hermetic tests for hooks/block_gcloud_identity.py (#5310).

#5310 is the spec: `gcloud config`/`gcloud auth`'s active account and
`~/.config/gcloud/application_default_credentials.json` are MACHINE-WIDE
state, shared by every concurrently-running agent session on this machine —
mutating either silently re-identifies every OTHER live session's next
gcloud/ADC-consuming call, exactly like `git checkout`ing a shared branch out
from under a peer session (the reason `checkout`/`switch` are already
STATE_VERBS in block_branch_ops.py). This suite covers the pure decision()
function's full branch matrix (the exact incident-shaped commands, the
sanctioned per-invocation scoping forms that must NOT block, and edge cases)
plus the thin main() driver (log-only vs enforce, kill-switch, escape hatch,
inline tripwire, parse-error fail-closed).

FALSIFIABILITY (runtime CLAUDE.md §6): the genuine revert-and-rerun (reverting
the fix under test to its pre-fix source, keeping this file, and confirming
the affected assertions go RED, then reapplying the fix and confirming GREEN)
was performed by hand during implementation, outside this file (see the
task's own red/green proof in the implementation report). An earlier version
of this docstring, and a same-named test method, claimed this file proved
that fact ITSELF via a simulated "no gate at all" baseline comparison; that
method's core assertion was unconditionally true regardless of the gate's
actual behavior (`assert x != y or True`) and was deleted rather than kept as
decoration — see the note in `TestIncidentShapedCommandsBlock` where it used
to live.

Everything runs against the `sandbox` fixture ($HOME + _lib path constants
pointed into a tmp dir) so the operator's real ~/.claude is never touched. No
network, no real `gcloud` subprocess is ever invoked — this module makes no
subprocess calls of its own, only string/regex analysis.
"""

from __future__ import annotations

import io
import json

import _lib  # noqa: F401  (imported for parity / sys.path shim via conftest)

# The module lives one dir up from tests/; conftest already put it on sys.path.
import block_gcloud_identity as guard
import pretooluse_bash as pbash
import pytest

# ===========================================================================
# Helpers.
# ===========================================================================


def _ev(command, tool_name="Bash", **extra):
    """Build a Bash PreToolUse event dict."""
    ev = {"tool_name": tool_name}
    if command is not None:
        ev["tool_input"] = {"command": command}
    ev.update(extra)
    return ev


def _run_main(monkeypatch, payload, capsys):
    """Drive main() end-to-end with `payload` (dict|str) on stdin; return (rc, out)."""
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = guard.main()
    out = capsys.readouterr().out
    return rc, out


# ===========================================================================
# The exact incident-shaped commands named in the task, and their per-command
# sanctioned equivalents. Every BLOCK case here is the RED fixture: proven to
# fail (i.e. decision() returns block=True, reason=<the exact tag>) only
# because the gate exists — see the falsifiability note above.
# ===========================================================================

_INCIDENT_SHAPED_BLOCK_CASES = [
    (
        "gcloud config set account (bare property name)",
        "gcloud config set account other@example.com",
        "config-set-account",
    ),
    (
        "gcloud config set core/account (synonym spelling)",
        "gcloud config set core/account other@example.com",
        "config-set-account",
    ),
    (
        "gcloud config configurations activate",
        "gcloud config configurations activate other-config",
        "config-configurations-activate",
    ),
    (
        "gcloud auth activate-service-account",
        "gcloud auth activate-service-account sa@x.iam.gserviceaccount.com "
        "--key-file=/tmp/k.json",
        "auth-activate-service-account",
    ),
    (
        "gcloud auth activate-service-account, no key-file flag order matters not",
        "gcloud auth activate-service-account --key-file=/tmp/k.json "
        "sa@x.iam.gserviceaccount.com",
        "auth-activate-service-account",
    ),
    (
        "gcloud auth application-default login",
        "gcloud auth application-default login",
        "auth-application-default-login",
    ),
    (
        "gcloud auth application-default login with an account arg",
        "gcloud auth application-default login someone@example.com",
        "auth-application-default-login",
    ),
    (
        "gcloud auth login, bare (no --no-activate)",
        "gcloud auth login",
        "auth-login-without-no-activate",
    ),
    (
        "gcloud auth login with an explicit account, still no --no-activate",
        "gcloud auth login someone@example.com",
        "auth-login-without-no-activate",
    ),
    (
        "ADC file overwritten via redirect",
        "cat /tmp/key.json > ~/.config/gcloud/application_default_credentials.json",
        "adc-file-redirect-write",
    ),
    (
        "ADC file appended via >>",
        "echo x >> ~/.config/gcloud/application_default_credentials.json",
        "adc-file-redirect-write",
    ),
    (
        "ADC file overwritten via cp",
        "cp /tmp/key.json ~/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via mv, absolute destination",
        "mv /tmp/key.json /Users/x/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via tee",
        "cat /tmp/key.json | tee ~/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    # --- N3 coverage: writer programs beyond cp/mv/tee, plus the directory-
    # destination form (source basename IS the ADC filename, destination is
    # a directory that preserves it) -- all executed and confirmed ALLOW
    # pre-fix.
    (
        "ADC file overwritten via ln -sf",
        "ln -sf /tmp/key.json ~/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via install",
        "install -m 600 /tmp/key.json ~/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via dd of=",
        "dd if=/tmp/key.json of=/Users/x/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via rsync",
        "rsync /tmp/key.json ~/.config/gcloud/application_default_credentials.json",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via mv into a directory (source basename is the ADC filename)",
        "mv /tmp/application_default_credentials.json ~/.config/gcloud/",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via cp into a directory (source basename is the ADC filename)",
        "cp /tmp/application_default_credentials.json ~/.config/gcloud/",
        "adc-file-cp-mv-tee-write",
    ),
    # --- N4 coverage: the directory-destination form WITHOUT a trailing
    # slash (`cp SRC ~/.config/gcloud`, an existing directory as dest) must
    # match exactly like the trailing-slash form does -- the basename still
    # survives the copy unchanged. Proven ALLOW pre-fix by execution.
    (
        "ADC file overwritten via cp into a directory, NO trailing slash",
        "cp /tmp/application_default_credentials.json ~/.config/gcloud",
        "adc-file-cp-mv-tee-write",
    ),
    (
        "ADC file overwritten via mv into a directory, NO trailing slash",
        "mv /tmp/application_default_credentials.json ~/.config/gcloud",
        "adc-file-cp-mv-tee-write",
    ),
    # --- B1 regression cases: a GLOBAL flag before the subcommand path must
    # never truncate the path scan and thereby allow a blocked verb through.
    # `--quiet`/`-q` is the flag an automation agent adds by reflex to
    # suppress interactive prompts -- the likely ACCIDENTAL spelling of the
    # exact incident command, not an exotic evasion. Verified live against
    # real gcloud (2026-09-13): `gcloud --quiet config set --help` and
    # `gcloud --verbosity=debug config set --help` both parse and exit 0.
    (
        "config set account, --quiet BEFORE the path (long form)",
        "gcloud --quiet config set account other@example.com",
        "config-set-account",
    ),
    (
        "config set account, -q BEFORE the path (short form)",
        "gcloud -q config set account other@example.com",
        "config-set-account",
    ),
    (
        "config set account, --verbosity=debug BEFORE the path (=value global flag)",
        "gcloud --verbosity=debug config set account other@example.com",
        "config-set-account",
    ),
    (
        "config set account, --verbosity debug BEFORE the path (space-value global flag)",
        "gcloud --verbosity debug config set account other@example.com",
        "config-set-account",
    ),
    (
        "auth application-default login, --quiet before the path",
        "gcloud --quiet auth application-default login",
        "auth-application-default-login",
    ),
    (
        "auth activate-service-account, --quiet before the path",
        "gcloud --quiet auth activate-service-account sa@x.iam.gserviceaccount.com "
        "--key-file=/tmp/k.json",
        "auth-activate-service-account",
    ),
    (
        "auth login (bare), --quiet before the path",
        "gcloud --quiet auth login",
        "auth-login-without-no-activate",
    ),
    (
        "config configurations activate, --quiet before the path",
        "gcloud --quiet config configurations activate other-config",
        "config-configurations-activate",
    ),
    # --- B2 regression case: a space-separated --account/--impersonate-
    # service-account value must be SKIPPED as a value token, never mistaken
    # for (or allowed to mask) the next subcommand-path token -- an agent
    # scoping a command with a real account must not thereby gain a way to
    # smuggle `config set account` through unblocked.
    (
        "config set account, with an UNRELATED --account scoping flag present "
        "(space-separated value) -- scoping one command never authorizes "
        "mutating the ambient identity in the SAME command",
        "gcloud --account cursor-agent@example-org.iam.gserviceaccount.com "
        "config set account other@example.com",
        "config-set-account",
    ),
    (
        "config set account, with an UNRELATED --account= scoping flag present "
        "(=value form)",
        "gcloud --account=cursor-agent@example-org.iam.gserviceaccount.com "
        "config set account other@example.com",
        "config-set-account",
    ),
    # --- B3 regression cases: an `alpha`/`beta` release-track prefix exposes
    # the IDENTICAL command surface one path element later and must not mask
    # any blocked verb. Verified live against real gcloud (2026-09-13):
    # `gcloud alpha config set --help` / `gcloud beta auth login --help` both
    # resolve to the same command as their non-prefixed form.
    (
        "config set account under the alpha track",
        "gcloud alpha config set account other@example.com",
        "config-set-account",
    ),
    (
        "config set account under the beta track",
        "gcloud beta config set account other@example.com",
        "config-set-account",
    ),
    (
        "auth login (bare) under the alpha track",
        "gcloud alpha auth login",
        "auth-login-without-no-activate",
    ),
    (
        "auth activate-service-account under the beta track",
        "gcloud beta auth activate-service-account sa@x.iam.gserviceaccount.com "
        "--key-file=/tmp/k.json",
        "auth-activate-service-account",
    ),
    (
        "auth application-default login under the alpha track",
        "gcloud alpha auth application-default login",
        "auth-application-default-login",
    ),
    (
        "config configurations activate under the beta track",
        "gcloud beta config configurations activate other-config",
        "config-configurations-activate",
    ),
    # --- B4 regression cases: `--update-adc` overwrites the shared ADC file
    # regardless of `--no-activate`, which only suppresses the active-account
    # change, not the ADC write. Verified against the real installed CLI
    # (`gcloud auth login --help`): "--update-adc: Write the obtained
    # credentials to the well-known location for Application Default
    # Credentials... Any credentials previously generated by gcloud auth
    # application-default login will be overwritten."
    (
        "auth login --no-activate --update-adc",
        "gcloud auth login --no-activate --update-adc",
        "auth-login-update-adc",
    ),
    (
        "auth login --update-adc --no-activate (flag order reversed)",
        "gcloud auth login --update-adc --no-activate",
        "auth-login-update-adc",
    ),
    (
        "auth login --update-adc under the beta track",
        "gcloud beta auth login --update-adc",
        "auth-login-update-adc",
    ),
    (
        "auth login --update-adc with no --no-activate at all",
        "gcloud auth login --update-adc",
        "auth-login-update-adc",
    ),
    # --- B5 regression cases: `config configurations create` activates the
    # new configuration BY DEFAULT (verified against the real installed CLI,
    # `gcloud config configurations create --help`: "--activate ... Enabled
    # by default, use --no-activate to disable"), the same mutation
    # `config-configurations-activate` already blocks, reachable via `create`.
    (
        "config configurations create, bare (no --no-activate)",
        "gcloud config configurations create sneaky",
        "config-configurations-create",
    ),
    (
        "config configurations create with explicit --activate",
        "gcloud config configurations create sneaky --activate",
        "config-configurations-create",
    ),
    (
        "config configurations create under the alpha track",
        "gcloud alpha config configurations create sneaky",
        "config-configurations-create",
    ),
    # --- B6 regression cases: `config unset account|core/account` and
    # `auth revoke`/`auth application-default revoke` reach the identical
    # machine-wide mutations already blocked above, by DELETION instead of
    # ASSIGNMENT. Verified against the real installed CLI (SDK 574.0.0,
    # 2026-09-13): `gcloud config unset --help` -- "By default, unsets the
    # property in your active configuration only" (the same active-
    # configuration scope `set` mutates); `gcloud auth revoke --help` -- "If
    # no account is specified, this command revokes credentials for the
    # currently active account, effectively logging out of that account";
    # `gcloud auth application-default revoke --help` -- "deletes the local
    # credential file".
    (
        "config unset account (bare property name)",
        "gcloud config unset account",
        "config-unset-account",
    ),
    (
        "config unset core/account (synonym spelling)",
        "gcloud config unset core/account",
        "config-unset-account",
    ),
    (
        "config unset account under the alpha track",
        "gcloud alpha config unset account",
        "config-unset-account",
    ),
    (
        "auth revoke, bare (no account -- revokes the active account)",
        "gcloud auth revoke",
        "auth-revoke",
    ),
    (
        "auth revoke --all",
        "gcloud auth revoke --all",
        "auth-revoke",
    ),
    (
        "auth revoke with an explicit account",
        "gcloud auth revoke other@example.com",
        "auth-revoke",
    ),
    (
        "auth revoke under the beta track",
        "gcloud beta auth revoke",
        "auth-revoke",
    ),
    (
        "auth application-default revoke",
        "gcloud auth application-default revoke",
        "auth-application-default-revoke",
    ),
    (
        "auth application-default revoke under the alpha track",
        "gcloud alpha auth application-default revoke",
        "auth-application-default-revoke",
    ),
    (
        "config unset account, --quiet before the path",
        "gcloud --quiet config unset account",
        "config-unset-account",
    ),
    (
        "auth revoke, --quiet before the path",
        "gcloud --quiet auth revoke",
        "auth-revoke",
    ),
    # --- B7 regression cases (#5890): `scheduler jobs
    # describe` / `run services describe` / `run jobs describe` / `functions
    # describe` print the resource's FULL representation to stdout by
    # default -- a Scheduler job's httpTarget.headers, a Cloud Run
    # revision's env, or a Cloud Functions OIDC/service-account token config
    # can carry a literal secret value. Denied unless --format is a safe
    # field projection. The exact incident command from the issue.
    (
        "scheduler jobs describe, bare (the exact incident command)",
        "gcloud scheduler jobs describe my-scheduler-job",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, --format=value(httpTarget.headers) -- the "
        "exact secret-leaking shape the incident named",
        "gcloud scheduler jobs describe my-scheduler-job --format=value(httpTarget.headers)",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, bare --format=yaml (full dump, no field list)",
        "gcloud scheduler jobs describe my-scheduler-job --format=yaml",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, bare --format=json (full dump, no field list)",
        "gcloud scheduler jobs describe my-scheduler-job --format=json",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, bare --format=text (full dump, no field list)",
        "gcloud scheduler jobs describe my-scheduler-job --format=text",
        "describe-unmasked-format",
    ),
    (
        "run services describe, bare (no --format at all)",
        "gcloud run services describe my-svc --region=us-central1",
        "describe-unmasked-format",
    ),
    (
        "run services describe, projection naming an env field",
        "gcloud run services describe my-svc "
        "--format='json(spec.template.spec.containers[].env)'",
        "describe-unmasked-format",
    ),
    (
        "run jobs describe, bare",
        "gcloud run jobs describe my-run-job",
        "describe-unmasked-format",
    ),
    (
        "functions describe, bare",
        "gcloud functions describe my-fn",
        "describe-unmasked-format",
    ),
    (
        "functions describe, projection naming an oidcToken-shaped field",
        "gcloud functions describe my-fn --format='yaml(serviceConfig.oidcToken)'",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe under the alpha track, bare",
        "gcloud alpha scheduler jobs describe my-scheduler-job",
        "describe-unmasked-format",
    ),
    (
        "run services describe under the beta track, bare",
        "gcloud beta run services describe my-svc",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, --quiet before the path, bare",
        "gcloud --quiet scheduler jobs describe my-scheduler-job",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, --format given as a separate token, unsafe kind",
        "gcloud scheduler jobs describe my-scheduler-job --format yaml",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, empty field list is degenerate/unsafe",
        "gcloud scheduler jobs describe my-scheduler-job --format='table()'",
        "describe-unmasked-format",
    ),
    (
        "scheduler jobs describe, --format present but no value at all "
        "(malformed/trailing flag)",
        "gcloud scheduler jobs describe my-scheduler-job --format",
        "describe-unmasked-format",
    ),
    # `list`'s default output is already a summary table -- no --format at
    # all is fine (see the allow-cases list); only an EXPLICIT full-dump
    # format is denied.
    (
        "scheduler jobs list, bare --format=yaml (full dump)",
        "gcloud scheduler jobs list --format=yaml",
        "list-unmasked-format",
    ),
    (
        "run services list, bare --format=json (full dump)",
        "gcloud run services list --format=json",
        "list-unmasked-format",
    ),
    (
        "run jobs list, bare --format=text (full dump)",
        "gcloud run jobs list --format=text",
        "list-unmasked-format",
    ),
    (
        "functions list, bare --format=yaml (full dump)",
        "gcloud functions list --format=yaml",
        "list-unmasked-format",
    ),
    (
        "scheduler jobs list under the alpha track, full-dump format",
        "gcloud alpha scheduler jobs list --format=yaml",
        "list-unmasked-format",
    ),
    # === #5890 round 2 (trust-architect review) ===========
    # --- B1: a PARENT key projects its entire subtree, including unsafe
    # children -- must be denied even though the parent's own name contains
    # no unsafe-looking substring. Proven RED pre-fix (see the task's own
    # red_check.py scratch run): every one of these ALLOWED before the
    # allowlist redesign.
    (
        "B1: scheduler describe, yaml(httpTarget) projects the whole "
        "subtree including headers",
        "gcloud scheduler jobs describe j --format='yaml(httpTarget)'",
        "describe-unmasked-format",
    ),
    (
        "B1: scheduler describe, json(httpTarget,name) mixes a safe leaf "
        "with an unsafe parent",
        "gcloud scheduler jobs describe j --format='json(httpTarget,name)'",
        "describe-unmasked-format",
    ),
    (
        "B1: scheduler describe, value(appEngineHttpTarget) parent key",
        "gcloud scheduler jobs describe j --format='value(appEngineHttpTarget)'",
        "describe-unmasked-format",
    ),
    (
        "B1: run services describe, yaml(spec) parent key",
        "gcloud run services describe s --format='yaml(spec)'",
        "describe-unmasked-format",
    ),
    (
        "B1: run services describe, json(spec.template.spec.containers) "
        "parent key",
        "gcloud run services describe s "
        "--format='json(spec.template.spec.containers)'",
        "describe-unmasked-format",
    ),
    (
        "B1: run services describe, yaml(template) parent key",
        "gcloud run services describe s --format='yaml(template)'",
        "describe-unmasked-format",
    ),
    (
        "B1: functions describe, json(serviceConfig) parent key",
        "gcloud functions describe f --format='json(serviceConfig)'",
        "describe-unmasked-format",
    ),
    (
        "B1: functions describe, json(buildConfig) parent key",
        "gcloud functions describe f --format='json(buildConfig)'",
        "describe-unmasked-format",
    ),
    (
        "B1: scheduler list, json(httpTarget) parent key",
        "gcloud scheduler jobs list --format='json(httpTarget)'",
        "list-unmasked-format",
    ),
    (
        "B1: scheduler describe, httpTarget.body leaf not on the allowlist",
        "gcloud scheduler jobs describe j --format='value(httpTarget.body)'",
        "describe-unmasked-format",
    ),
    (
        "B1: scheduler describe, pubsubTarget.attributes leaf not allowlisted",
        "gcloud scheduler jobs describe j "
        "--format='value(pubsubTarget.attributes)'",
        "describe-unmasked-format",
    ),
    (
        "B1: scheduler describe, pubsubTarget.data leaf not allowlisted",
        "gcloud scheduler jobs describe j --format='value(pubsubTarget.data)'",
        "describe-unmasked-format",
    ),
    (
        "B1: scheduler describe, httpTarget.uri leaf not allowlisted "
        "(query-string tokens)",
        "gcloud scheduler jobs describe j --format='value(httpTarget.uri)'",
        "describe-unmasked-format",
    ),
    (
        "B1: `.` wildcard field is always unsafe regardless of family",
        "gcloud scheduler jobs describe j --format='yaml(.)'",
        "describe-unmasked-format",
    ),
    (
        "B1: `*` wildcard field is always unsafe regardless of family",
        "gcloud scheduler jobs describe j --format='yaml(*)'",
        "describe-unmasked-format",
    ),
    (
        "B1: an unknown/unenumerated field is denied (allowlist, not "
        "blocklist) even though it doesn't look unsafe",
        "gcloud scheduler jobs describe j --format='yaml(totallyBenignField)'",
        "describe-unmasked-format",
    ),
    # --- B2: gcloud uses the LAST --format value, and a single value can
    # itself concatenate multiple projections; --flags-file can set an
    # unsafe --format with no visible token.
    (
        "B2: two --format tokens -- gcloud applies the last (unsafe) one",
        "gcloud scheduler jobs describe j --format='table(name)' "
        "--format=json",
        "describe-multiple-format",
    ),
    (
        "B2: combined value 'table(name) json()' is not one clean projection",
        "gcloud scheduler jobs describe j --format='table(name) json()'",
        "describe-unmasked-format",
    ),
    (
        "B2: scheduler list --flags-file, no visible --format token at all",
        "gcloud scheduler jobs list --flags-file=f",
        "list-flags-file",
    ),
    (
        "B2: scheduler describe --flags-file alongside a safe-looking format",
        "gcloud scheduler jobs describe j --format='table(name)' "
        "--flags-file=f",
        "describe-flags-file",
    ),
    (
        "B2: two --format tokens on a list verb",
        "gcloud scheduler jobs list --format='table(name)' --format=yaml",
        "list-multiple-format",
    ),
    # --- B3: --log-http (any spelling) and CLOUDSDK_CORE_LOG_HTTP leak the
    # full response body to stderr regardless of --format, and apply to
    # EVERY gcloud verb, not only the describe/list family.
    (
        "B3: describe with a safe --format but --log-http still leaks the "
        "raw response",
        "gcloud scheduler jobs describe j --format='value(name)' --log-http",
        "log-http-leaks-response",
    ),
    (
        "B3: scheduler jobs list --log-http",
        "gcloud scheduler jobs list --log-http",
        "log-http-leaks-response",
    ),
    (
        "B3: CLOUDSDK_CORE_LOG_HTTP=1 env prefix",
        "CLOUDSDK_CORE_LOG_HTTP=1 gcloud scheduler jobs list",
        "log-http-leaks-response",
    ),
    (
        "B3: --log-http=true explicit value spelling",
        "gcloud scheduler jobs list --log-http=true",
        "log-http-leaks-response",
    ),
    (
        "B3: --log-http applies to an UNRELATED gcloud verb too, not just "
        "scheduler/run/functions",
        "gcloud projects list --log-http",
        "log-http-leaks-response",
    ),
    # --- B5 (round 2 fix round): two routes around the --log-http rule that
    # B3's leading-env-prefix-on-the-SAME-segment check and the per-invocation
    # --log-http flag check both miss.
    (
        "B5: export CLOUDSDK_CORE_LOG_HTTP in a SEPARATE segment before the "
        "gcloud call -- properties.py reads the var from the process env, "
        "not from argv position, so this reaches the identical property",
        "export CLOUDSDK_CORE_LOG_HTTP=1; gcloud scheduler jobs list",
        "log-http-leaks-response",
    ),
    (
        "B5: `env VAR=1 gcloud ...` -- env's own leading-assignment form, "
        "not a leading-token-on-the-gcloud-segment form",
        "env CLOUDSDK_CORE_LOG_HTTP=1 gcloud scheduler jobs list",
        "log-http-leaks-response",
    ),
    (
        "B5: set -a; VAR=1; set +a; gcloud ... -- exported via `set -a` in "
        "a separate segment, same reachability as the export form",
        "set -a; CLOUDSDK_CORE_LOG_HTTP=1; set +a; gcloud scheduler jobs list",
        "log-http-leaks-response",
    ),
    (
        "B5: gcloud config set core/log_http true -- PERSISTENT, machine-"
        "wide (written to the active named configuration), unlike the "
        "per-invocation --log-http flag",
        "gcloud config set core/log_http true",
        "config-set-log-http",
    ),
    (
        "B5: gcloud config set log_http true --configuration=x -- the "
        "unqualified property spelling, plus an explicit --configuration",
        "gcloud config set log_http true --configuration=x",
        "config-set-log-http",
    ),
    (
        "B5: a global-flag-prefixed config set core/log_http -- mirrors the "
        "in-change --http-timeout/config-set-account regression class",
        "gcloud --http-timeout 30 config set core/log_http true",
        "config-set-log-http",
    ),
    # --- round 3 fix round item 2: _mentions_gcloud tightened to a real
    # program-token check must NOT lose any genuine detection -- a real
    # gcloud invocation in a DIFFERENT segment than the env assignment, or
    # reached via a full interpreter path, must still be denied exactly as
    # before.
    (
        "round 3 item 2 (still denied): export in one segment, a REAL "
        "gcloud invocation (program token, not just a text mention) in the "
        "next -- the exact B5 shape this check exists for, must survive "
        "the tripwire tightening",
        "export CLOUDSDK_CORE_LOG_HTTP=1; gcloud run services list",
        "log-http-leaks-response",
    ),
    (
        "round 3 item 2 (still denied): env-prefixed assignment ahead of a "
        "full-path gcloud invocation (/usr/bin/gcloud) -- the program-token "
        "walk must match a path-suffixed program, not only the bare token",
        "CLOUDSDK_CORE_LOG_HTTP=1 /usr/bin/gcloud scheduler jobs list",
        "log-http-leaks-response",
    ),
    # --- B4: Cloud Run revisions and jobs-executions(-tasks) describe/list
    # were claimed as covered (docstring, knowledge doc, test comments) but
    # weren't.
    (
        "B4: run revisions describe, bare",
        "gcloud run revisions describe r",
        "describe-unmasked-format",
    ),
    (
        "B4: run revisions list, full-dump format",
        "gcloud run revisions list --format=yaml",
        "list-unmasked-format",
    ),
    (
        "B4: run jobs executions describe, bare",
        "gcloud run jobs executions describe e",
        "describe-unmasked-format",
    ),
    (
        "B4: run jobs executions tasks describe, bare",
        "gcloud run jobs executions tasks describe t",
        "describe-unmasked-format",
    ),
    (
        "B4: run jobs executions list, full-dump format",
        "gcloud run jobs executions list --format=yaml",
        "list-unmasked-format",
    ),
    (
        "B4: run jobs executions tasks list, full-dump format",
        "gcloud run jobs executions tasks list --format=json",
        "list-unmasked-format",
    ),
    # --- In-change: hidden global value-taking flags before the subcommand
    # path must not mask the path -- mirrors the existing B1 (--quiet/
    # --verbosity) regression class, for the five flags the review found
    # missing from _GLOBAL_VALUE_FLAGS. The second case is the sharper one:
    # a bypass of the PRE-EXISTING identity gate, not just the #5890 gate.
    (
        "in-change: --http-timeout before scheduler describe masks the path",
        "gcloud --http-timeout 30 scheduler jobs describe j",
        "describe-unmasked-format",
    ),
    (
        "in-change: --http-timeout before config set account is a bypass "
        "of the identity gate itself",
        "gcloud --http-timeout 30 config set account x@y.com",
        "config-set-account",
    ),
    (
        "in-change: --authority-selector before config set account",
        "gcloud --authority-selector foo config set account x@y.com",
        "config-set-account",
    ),
    (
        "in-change: --authorization-token-file before config set account",
        "gcloud --authorization-token-file /tmp/t config set account x@y.com",
        "config-set-account",
    ),
    (
        "in-change: --credential-file-override before config set account",
        "gcloud --credential-file-override /tmp/c config set account x@y.com",
        "config-set-account",
    ),
    (
        "in-change: --universe-domain before config set account",
        "gcloud --universe-domain example.com config set account x@y.com",
        "config-set-account",
    ),
]


class TestIncidentShapedCommandsBlock:
    @pytest.mark.parametrize(
        "label,command,reason", _INCIDENT_SHAPED_BLOCK_CASES, ids=[c[0] for c in _INCIDENT_SHAPED_BLOCK_CASES]
    )
    def test_blocks_with_expected_reason(self, label, command, reason):
        block, got_reason = guard.decision(command)
        assert block is True, f"{label!r} should BLOCK: {command!r}"
        assert got_reason == reason, f"{label!r}: expected reason {reason!r}, got {got_reason!r}"

    # NOTE: an earlier version of this suite had a
    # `test_every_incident_shaped_case_would_be_missed_without_the_gate`
    # method here that claimed to prove these BLOCK assertions are exercising
    # real gate logic (vs. vacuously matching a gate that would allow
    # anyway). It did not: its core assertion was
    # `assert block != baseline_would_allow or True`, which the `or True`
    # makes UNCONDITIONALLY true regardless of `block`'s value, and its
    # second assertion (`assert block is True`) merely duplicated
    # `test_blocks_with_expected_reason` above. It was deleted rather than
    # fixed in place, since a genuine "would this suite catch a regression"
    # proof needs an actual gate-absent code path to compare against, not a
    # per-test simulated baseline — that proof is the real revert-and-rerun
    # performed by hand during implementation (see the task's own red/green
    # report), not something this file can honestly claim to demonstrate on
    # its own.


# ===========================================================================
# Sanctioned per-invocation scoping forms + read-only verbs: ALLOW.
# ===========================================================================

_ALLOWED_CASES = [
    ("--account= before the subcommand", "gcloud --account=svc@example.com config list"),
    ("--account= after the subcommand", "gcloud config list --account=svc@example.com"),
    (
        "--impersonate-service-account=",
        "gcloud --impersonate-service-account=sa@x.iam.gserviceaccount.com projects list",
    ),
    (
        "impersonate flag placed after the subcommand path",
        "gcloud projects list --impersonate-service-account=sa@x.iam.gserviceaccount.com",
    ),
    (
        "CLOUDSDK_CORE_ACCOUNT env prefix",
        "CLOUDSDK_CORE_ACCOUNT=svc@example.com gcloud config list",
    ),
    ("auth login --no-activate", "gcloud auth login --no-activate"),
    ("auth login with account AND --no-activate", "gcloud auth login someone@example.com --no-activate"),
    ("auth list (read-only)", "gcloud auth list"),
    ("config get-value account (read-only)", "gcloud config get-value account"),
    ("config get-value core/account (read-only)", "gcloud config get-value core/account"),
    ("an unrelated gcloud subcommand", "gcloud projects list"),
    ("an unrelated config set", "gcloud config set project my-project"),
    ("a plain git command", "git status"),
    ("a plain non-gcloud command", "ls -la"),
    ("redirect to an unrelated file", "echo hi > /tmp/notes.txt"),
    (
        "cp to a filename that merely contains the ADC substring elsewhere",
        "cp /tmp/application_default_credentials.json.bak /tmp/other.json",
    ),
    ("empty command", "   "),
    # --- B2 regression cases: space-separated `--account <value>` is this
    # repo's own documented runbook spelling (repo_tooling/demo_video/
    # RUNBOOK.md, README.md, narrate.py, HANDOFF_2026-09-10.md all use this
    # exact form) and must resolve to ALLOW for a non-mutating verb, exactly
    # like the `=`-joined spelling already does.
    (
        "--account <value> (space-separated) scoping a read-only verb -- this "
        "repo's own documented runbook form",
        "gcloud --account cursor-agent@example-org.iam.gserviceaccount.com "
        "secrets versions access latest --secret=x",
    ),
    (
        "--account <value> (space-separated) before an unrelated config list",
        "gcloud --account svc@example.com config list",
    ),
    (
        "--impersonate-service-account <value> (space-separated) scoping a "
        "read-only verb",
        "gcloud --impersonate-service-account sa@x.iam.gserviceaccount.com projects list",
    ),
    # --- B1 regression cases: a global flag (value-taking or boolean) before
    # the subcommand path must not itself cause an ALLOW-worthy command to be
    # (mis-)blocked -- the fix must not overcorrect into a new false positive.
    ("--quiet before an unrelated read-only verb", "gcloud --quiet projects list"),
    ("-q before an unrelated read-only verb", "gcloud -q auth list"),
    ("--verbosity=debug before an unrelated config list", "gcloud --verbosity=debug config list"),
    (
        "--verbosity debug (space-separated) before an unrelated config list",
        "gcloud --verbosity debug config list",
    ),
    (
        "--quiet before config set of an unrelated (non-account) property",
        "gcloud --quiet config set project my-project",
    ),
    # --- N3 false-positive guards: the expanded writer-program coverage
    # must not start flagging unrelated copy/move/link/sync/dd usage.
    (
        "mv into a directory, unrelated source filename",
        "mv /tmp/other-file.json ~/.config/gcloud/",
    ),
    (
        "cp into a directory, unrelated source filename",
        "cp /tmp/notes.txt /Users/x/backups/",
    ),
    (
        "ln -s with a single positional arg (no explicit link name/dir)",
        "ln -s /tmp/application_default_credentials.json",
    ),
    (
        "dd with an unrelated of= destination",
        "dd if=/tmp/key.json of=/tmp/other-output.json",
    ),
    (
        "rsync between two unrelated paths",
        "rsync /tmp/src.txt /tmp/dest.txt",
    ),
    # --- N4 false-positive guards: the no-trailing-slash directory-dest
    # detection must not misfire on an ordinary renamed-copy destination
    # (a dest basename WITH a `.`-extension is a real filename, not a dir).
    (
        "mv to a dest with a file extension, unrelated source",
        "mv /tmp/notes.txt /Users/x/backups",
    ),
    (
        "cp to a renamed destination filename (has an extension, not a dir)",
        "cp /tmp/key.json /tmp/key-backup.json",
    ),
    # --- B3 false-positive guards: alpha/beta track stripping must not
    # itself cause an unrelated command to be (mis-)blocked.
    ("alpha track, unrelated read-only verb", "gcloud alpha projects list"),
    ("beta track, unrelated config list", "gcloud beta config list"),
    (
        "alpha track, config set of an unrelated (non-account) property",
        "gcloud alpha config set project my-project",
    ),
    # --- B4 false-positive guard: --no-activate alone (no --update-adc)
    # must still allow, exactly as before this fix.
    ("auth login --no-activate, no --update-adc", "gcloud auth login --no-activate"),
    # --- B5 false-positive guard: config configurations create WITH
    # --no-activate must allow, mirroring auth login's own escape.
    (
        "config configurations create with --no-activate",
        "gcloud config configurations create foo --no-activate",
    ),
    (
        "an unrelated config configurations list",
        "gcloud config configurations list",
    ),
    # --- B6 false-positive guards: `config unset` of an unrelated property,
    # and any other gcloud verb that merely shares a word with `revoke`/
    # `unset`, must not be (mis-)blocked.
    (
        "an unrelated config unset (non-account property)",
        "gcloud config unset compute/zone",
    ),
    (
        "an unrelated config unset (project)",
        "gcloud config unset project",
    ),
    (
        "config unset with no property at all",
        "gcloud config unset",
    ),
    (
        "alpha track, config unset of an unrelated property",
        "gcloud alpha config unset project",
    ),
    # --- B7 false-positive guards (#5890): the safe
    # masked-projection --format form, and the "list needs no --format at
    # all" asymmetry, must not themselves become new false positives.
    (
        "scheduler jobs describe with a safe table() projection -- the "
        "documented safe form",
        "gcloud scheduler jobs describe my-scheduler-job "
        "--format='table(name,schedule,state)'",
    ),
    (
        "scheduler jobs describe with a safe table() projection, double-quoted",
        "gcloud scheduler jobs describe my-scheduler-job "
        '--format="table(name,schedule,state)"',
    ),
    (
        "run services describe with a safe json() projection naming only metadata.name",
        "gcloud run services describe my-svc --format='json(metadata.name)'",
    ),
    (
        "functions describe with a safe yaml() projection naming benign fields",
        "gcloud functions describe my-fn "
        "--format='yaml(httpsTrigger.securityLevel,serviceAccountEmail)'",
    ),
    (
        "run jobs describe with a safe value() projection",
        "gcloud run jobs describe my-run-job --format='value(status.conditions[0].type)'",
    ),
    (
        "scheduler jobs describe with a safe csv() projection",
        "gcloud scheduler jobs describe my-scheduler-job --format='csv(name,state)'",
    ),
    (
        "scheduler jobs describe, safe projection, --format given as a "
        "separate quoted token",
        "gcloud scheduler jobs describe my-scheduler-job "
        "--format 'table(name,schedule,state)'",
    ),
    (
        "scheduler jobs describe, safe projection placed BEFORE the subcommand path",
        "gcloud --format='table(name,schedule,state)' scheduler jobs describe my-scheduler-job",
    ),
    (
        "scheduler jobs describe under the alpha track, safe projection",
        "gcloud alpha scheduler jobs describe my-scheduler-job "
        "--format='table(name,schedule,state)'",
    ),
    (
        "scheduler jobs describe, safe projection alongside an unrelated "
        "--project flag",
        "gcloud scheduler jobs describe my-scheduler-job --project=x "
        "--format='table(name,schedule,state)'",
    ),
    (
        "scheduler jobs list, bare (no --format at all -- default table "
        "output is already a summary)",
        "gcloud scheduler jobs list",
    ),
    (
        "run services list, bare",
        "gcloud run services list --region=us-central1",
    ),
    (
        "run jobs list, bare",
        "gcloud run jobs list",
    ),
    (
        "functions list, bare",
        "gcloud functions list",
    ),
    (
        "scheduler jobs list with a safe table() projection",
        "gcloud scheduler jobs list --format='table(name,schedule,state)'",
    ),
    (
        "functions list under the alpha track, bare",
        "gcloud alpha functions list",
    ),
    (
        "an unrelated scheduler subcommand (not describe/list)",
        "gcloud scheduler jobs pause my-scheduler-job",
    ),
    (
        "an unrelated run subcommand (not describe/list)",
        "gcloud run deploy my-svc --image=gcr.io/x/y",
    ),
    # === #5890 round 2 false-positive guards ==============
    (
        "B1: scheduler describe, safe leaf field httpTarget.httpMethod (a "
        "literal allowlisted dotted leaf, not a parent-key match)",
        "gcloud scheduler jobs describe j "
        "--format='table(name,httpTarget.httpMethod)'",
    ),
    (
        "B1: run services describe, safe leaf status.url",
        "gcloud run services describe s --format='json(status.url)'",
    ),
    (
        "B1: run services describe, safe leaf "
        "spec.template.spec.serviceAccountName",
        "gcloud run services describe s "
        "--format='yaml(spec.template.spec.serviceAccountName)'",
    ),
    (
        "B4: run revisions describe, safe leaf projection",
        "gcloud run revisions describe r --format='table(metadata.name)'",
    ),
    (
        "B4: run jobs executions describe, safe leaf projection",
        "gcloud run jobs executions describe e "
        "--format='table(metadata.name,status.conditions[0].type)'",
    ),
    (
        "B4: run jobs executions tasks describe, safe leaf projection",
        "gcloud run jobs executions tasks describe t "
        "--format='table(metadata.name)'",
    ),
    (
        "B4: run revisions list, bare (no --format)",
        "gcloud run revisions list",
    ),
    (
        "B4: run jobs executions list, bare (no --format)",
        "gcloud run jobs executions list",
    ),
    (
        "in-change: --http-timeout before an unrelated read-only verb",
        "gcloud --http-timeout 30 projects list",
    ),
    (
        "in-change: --universe-domain before an unrelated config list",
        "gcloud --universe-domain example.com config list",
    ),
    (
        "single --format token with a safe value is NOT flagged as "
        "'multiple' -- only 2+ tokens trip that check",
        "gcloud scheduler jobs describe j --format='table(name,schedule,state)'",
    ),
    # --- round 3 fix round item 2: _mentions_gcloud tightened from a bare
    # whole-word TEXT match to a real program-token check. These commands
    # all contain the raw substring "gcloud" (as a filename, in a --k
    # selector) but never actually INVOKE gcloud as a program -- pre-fix,
    # each was denied outright as a false positive (see this module's
    # #5890 round 3 item 2 fix-round note).
    (
        "round 3 item 2: grep of this module's own filename, which contains "
        "'gcloud' as a substring, alongside the CLOUDSDK_CORE_LOG_HTTP name",
        "grep -rn CLOUDSDK_CORE_LOG_HTTP hooks/block_gcloud_identity.py",
    ),
    (
        "round 3 item 2: cat of a file literally named gcloud.log piped to "
        "grep for the env var name -- 'gcloud' is a filename substring only",
        "cat gcloud.log | grep CLOUDSDK_CORE_LOG_HTTP",
    ),
    (
        "round 3 item 2: pytest -k selector naming this test file's own "
        "module (block_gcloud_identity) alongside the env var name",
        "python3 -m pytest hooks/tests/test_block_gcloud_identity.py -k CLOUDSDK_CORE_LOG_HTTP",
    ),
]


class TestSanctionedFormsAllow:
    @pytest.mark.parametrize("label,command", _ALLOWED_CASES, ids=[c[0] for c in _ALLOWED_CASES])
    def test_allows(self, label, command):
        block, reason = guard.decision(command)
        assert block is False, f"{label!r} should ALLOW: {command!r} (reason={reason!r})"


# ===========================================================================
# Compound commands: first-blocking-segment-wins, mirroring
# block_branch_ops.decision()'s own contract.
# ===========================================================================


class TestCompoundCommands:
    def test_blocking_segment_after_safe_prefix(self):
        block, reason = guard.decision(
            "cd /tmp && gcloud config set account other@example.com"
        )
        assert block is True
        assert reason == "config-set-account"

    def test_safe_segments_only_allow(self):
        block, _ = guard.decision("gcloud auth list && gcloud projects list")
        assert block is False

    def test_second_segment_blocks_even_if_first_is_safe(self):
        block, reason = guard.decision(
            "gcloud auth list; gcloud auth application-default login"
        )
        assert block is True
        assert reason == "auth-application-default-login"

    def test_pipe_separated_segments(self):
        block, reason = guard.decision(
            "echo hi | cat && gcloud config configurations activate other"
        )
        assert block is True
        assert reason == "config-configurations-activate"

    def test_scheduler_describe_blocks_after_safe_prefix(self):
        block, reason = guard.decision(
            "cd /tmp && gcloud scheduler jobs describe my-job"
        )
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_safe_scheduler_describe_compound_allows(self):
        block, _ = guard.decision(
            "gcloud auth list && gcloud scheduler jobs describe my-job "
            "--format='table(name,schedule,state)'"
        )
        assert block is False

    def test_family_for_command_matches_the_actually_blocking_segment(self):
        # #5890 round 3 fix round, item 3: a SAFE
        # scheduler-job `list` (with a masked --format, so it does not
        # itself block) followed by an UNMASKED run-service `describe` (the
        # segment that actually blocks) must derive the RUN-SERVICE family,
        # not scheduler-job -- `_family_for_command` used to return the
        # first segment matching ANY verb group, regardless of whether that
        # segment was the one decision() actually blocked on.
        cmd = (
            "gcloud scheduler jobs list --format='value(name)' && "
            "gcloud run services describe s"
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"
        assert guard._family_for_command(cmd) == "run-service"

    def test_family_for_command_message_hint_matches_blocking_segment_not_first_match(self):
        # The end-to-end version of the test above: the deny MESSAGE's
        # extracted hint must pass decision() when substituted into the
        # SEGMENT THAT ACTUALLY BLOCKED (run services describe), not into
        # the safe scheduler-job list segment that merely matched first.
        cmd = (
            "gcloud scheduler jobs list --format='value(name)' && "
            "gcloud run services describe s"
        )
        block, reason = guard.decision(cmd)
        assert block is True
        msg = guard._message_for(reason, cmd)
        marker = "instead: --format='"
        assert marker in msg
        start = msg.index(marker) + len(marker)
        end = msg.index("'", start)
        hint = msg[start:end]
        retry_cmd = (
            "gcloud scheduler jobs list --format='value(name)' && "
            "gcloud run services describe s --format='" + hint + "'"
        )
        retry_block, retry_reason = guard.decision(retry_cmd)
        assert retry_block is False, (
            f"hint {hint!r} (derived from the mismatched-family bug) still "
            f"fails on retry ({retry_reason!r}) -- command was {retry_cmd!r}"
        )


# ===========================================================================
# Helper-function unit coverage: _format_value / _is_safe_format_value.
# ===========================================================================


class TestFormatValueExtraction:
    def test_equals_form(self):
        value, present, multiple = guard._format_value(["--format=yaml"])
        assert (value, present, multiple) == ("yaml", True, False)

    def test_space_separated_form(self):
        value, present, multiple = guard._format_value(["--format", "json"])
        assert (value, present, multiple) == ("json", True, False)

    def test_absent(self):
        value, present, multiple = guard._format_value(
            ["scheduler", "jobs", "describe", "x"]
        )
        assert (value, present, multiple) == (None, False, False)

    def test_trailing_flag_with_no_value(self):
        value, present, multiple = guard._format_value(["describe", "x", "--format"])
        assert (value, present, multiple) == ("", True, False)

    def test_finds_format_anywhere_in_argv(self):
        value, present, multiple = guard._format_value(
            ["--project=x", "describe", "my-job", "--format=yaml", "--quiet"]
        )
        assert (value, present, multiple) == ("yaml", True, False)

    # --- B2: gcloud applies the LAST --format value, not the first; 2+
    # tokens are flagged via `multiple`.
    def test_two_format_tokens_returns_the_last_value_and_flags_multiple(self):
        value, present, multiple = guard._format_value(
            ["--format=table(name)", "--format=json"]
        )
        assert value == "json"  # the LAST one, mirroring gcloud's own precedence
        assert present is True
        assert multiple is True

    def test_three_format_tokens_still_returns_the_last_and_flags_multiple(self):
        value, present, multiple = guard._format_value(
            ["--format", "yaml", "--format=table(name)", "--format=json"]
        )
        assert value == "json"
        assert multiple is True

    def test_single_format_token_never_flags_multiple(self):
        _, _, multiple = guard._format_value(["--format=table(name,schedule,state)"])
        assert multiple is False


class TestHasFlagsFile:
    def test_equals_form(self):
        assert guard._has_flags_file(["--flags-file=f"]) is True

    def test_space_separated_form(self):
        assert guard._has_flags_file(["--flags-file", "f"]) is True

    def test_absent(self):
        assert guard._has_flags_file(["--format=yaml"]) is False


class TestHasLogHttp:
    # ROUND 3 fix round item 5: `test_cloudsdk_env_prefix` /
    # `test_cloudsdk_env_prefix_absent` (which tested the now-removed
    # `_has_cloudsdk_core_log_http_env` helper) were deleted along with that
    # helper -- see block_gcloud_identity.py's comment at its former
    # definition site for the reachability argument (decision()'s own
    # top-level raw-text CLOUDSDK_CORE_LOG_HTTP tripwire always fires first,
    # making the per-segment env-prefix helper genuinely dead code). The
    # equivalent behavior is still covered end-to-end by
    # `_INCIDENT_SHAPED_BLOCK_CASES`' "B3: CLOUDSDK_CORE_LOG_HTTP=1 env
    # prefix" case via `decision()` itself.
    def test_bare_flag(self):
        assert guard._has_log_http(["gcloud", "projects", "list", "--log-http"]) is True

    def test_equals_true_spelling(self):
        assert guard._has_log_http(["gcloud", "projects", "list", "--log-http=true"]) is True

    def test_absent(self):
        assert guard._has_log_http(["gcloud", "projects", "list"]) is False

    # P3-4 (round 4 fix round): the OLD `_INCIDENT_SHAPED_BLOCK_CASES` case
    # for `env CLOUDSDK_CORE_LOG_HTTP=1 gcloud scheduler jobs list` only ever
    # ran through `decision()`, whose top-level raw-text
    # `"CLOUDSDK_CORE_LOG_HTTP" in command` tripwire fires BEFORE the
    # per-segment loop ever reaches `_evaluate_gcloud_argv` -- so that test
    # passing proved nothing about whether the EVALUATOR itself (specifically
    # `_is_gcloud`/`_find_gcloud_argv`'s handling of an `env` wrapper) could
    # find the gcloud invocation on its own. This test closes that gap
    # directly: it calls `_evaluate_gcloud_argv` on the wrapped argv WITH NO
    # `CLOUDSDK_CORE_LOG_HTTP` text anywhere (so decision()'s raw-text
    # tripwire, which this test deliberately never goes through, could not
    # be the thing making it pass even if it were exercised) -- proving the
    # B2 program-token scan genuinely finds `gcloud` past the `env` wrapper
    # and evaluates its `--log-http` FLAG (a real, still-reachable check,
    # unlike the removed env-var helper).
    def test_evaluator_finds_log_http_flag_past_an_env_wrapper(self):
        block, reason = guard._evaluate_gcloud_argv(
            ["env", "FOO=1", "gcloud", "projects", "list", "--log-http"]
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_evaluator_finds_config_set_account_past_an_env_wrapper(self):
        # The identity-mutation counterpart of the case above -- B2's fix is
        # general (the shared `_find_gcloud_argv` helper), not scoped only
        # to --log-http, so this is the evaluator-level proof for the OTHER
        # hazard class B2 also closed.
        block, reason = guard._evaluate_gcloud_argv(
            ["env", "gcloud", "config", "set", "account", "other@example.com"]
        )
        assert block is True
        assert reason == "config-set-account"

    # ---- P3-2 (round 4 fix round): over-blocking on the mitigation forms --
    def test_explicit_false_value_does_not_leak(self):
        assert guard._has_log_http(["gcloud", "projects", "list", "--log-http=false"]) is False

    def test_explicit_no_value_does_not_leak(self):
        assert guard._has_log_http(["gcloud", "projects", "list", "--log-http=no"]) is False

    def test_explicit_zero_value_does_not_leak(self):
        assert guard._has_log_http(["gcloud", "projects", "list", "--log-http=0"]) is False

    def test_no_log_http_flag_does_not_leak(self):
        assert guard._has_log_http(["gcloud", "projects", "list", "--no-log-http"]) is False

    def test_last_flag_wins_true_then_false(self):
        assert (
            guard._has_log_http(["gcloud", "projects", "list", "--log-http", "--log-http=false"])
            is False
        )

    def test_last_flag_wins_false_then_true(self):
        assert (
            guard._has_log_http(["gcloud", "projects", "list", "--log-http=false", "--log-http"])
            is True
        )

    def test_decision_allows_log_http_equals_false(self):
        block, _ = guard.decision("gcloud scheduler jobs list --log-http=false")
        assert block is False

    def test_decision_allows_unset_cloudsdk_core_log_http(self):
        block, _ = guard.decision("unset CLOUDSDK_CORE_LOG_HTTP; gcloud scheduler jobs list")
        assert block is False

    def test_decision_allows_env_dash_u_cloudsdk_core_log_http(self):
        block, _ = guard.decision("env -u CLOUDSDK_CORE_LOG_HTTP gcloud scheduler jobs list")
        assert block is False

    def test_decision_still_denies_unset_then_reset(self):
        # An unset FOLLOWED BY a real assignment must still deny -- the
        # mitigation-form allowance must not let a later re-assignment slip
        # through just because an earlier unset appeared somewhere in text.
        block, reason = guard.decision(
            "unset CLOUDSDK_CORE_LOG_HTTP; CLOUDSDK_CORE_LOG_HTTP=1; gcloud scheduler jobs list"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_config_set_log_http_message_advises_a_form_that_is_actually_allowed(self):
        # ROUND 6 CORRECTION (P3-1): the prior version of this test asserted
        # the message recommends --log-http=false -- but --log-http is a
        # strict zero-argument boolean flag (StoreBooleanProperty, nargs=0
        # on the live installed SDK); passing =value to it is a real
        # argparse error ("ignored explicit argument"), so that was never
        # actually usable advice. The message must recommend --no-log-http
        # (the real, argparse-accepted opt-out) instead.
        msg = guard._message_for("config-set-log-http")
        assert "--no-log-http" in msg
        block, _ = guard.decision("gcloud scheduler jobs list --no-log-http")
        assert block is False

    def test_log_http_equals_false_is_harmless_but_not_the_recommended_form(self):
        # --log-http=false is never actually usable against real gcloud (it
        # errors out on a zero-argument flag before any HTTP call happens),
        # so this gate's own choice to treat it as FALSE rather than TRUE is
        # a harmless defensive default, not real advice -- round 6, P3-1.
        # This gate still does not deny it (nothing to leak: gcloud itself
        # refuses the command), but the deny MESSAGE must never recommend
        # this spelling (covered by the test above).
        block, _ = guard.decision("gcloud scheduler jobs list --log-http=false")
        assert block is False


# ===========================================================================
# P3-1 (round 4 fix round): `gcloud config set format|core/format` and
# `CLOUDSDK_CORE_FORMAT` -- the format-property counterpart of
# config-set-log-http/CLOUDSDK_CORE_LOG_HTTP, denied defensively.
# ===========================================================================


class TestFormatPropertyAndEnvOverride:
    def test_config_set_format_denies(self):
        block, reason = guard.decision("gcloud config set format json")
        assert block is True
        assert reason == "config-set-format"

    def test_config_set_core_format_denies(self):
        block, reason = guard.decision("gcloud config set core/format yaml")
        assert block is True
        assert reason == "config-set-format"

    def test_config_set_unrelated_property_allows(self):
        block, _ = guard.decision("gcloud config set project myproj")
        assert block is False

    def test_cloudsdk_core_format_env_prefix_denies(self):
        block, reason = guard.decision("CLOUDSDK_CORE_FORMAT=json gcloud scheduler jobs list")
        assert block is True
        assert reason == "format-env-override"

    def test_cloudsdk_core_format_export_separate_segment_denies(self):
        block, reason = guard.decision(
            "export CLOUDSDK_CORE_FORMAT=json; gcloud scheduler jobs list"
        )
        assert block is True
        assert reason == "format-env-override"

    def test_cloudsdk_core_format_unset_mitigation_allows(self):
        block, _ = guard.decision("unset CLOUDSDK_CORE_FORMAT; gcloud scheduler jobs list")
        assert block is False

    def test_cloudsdk_core_format_env_dash_u_mitigation_allows(self):
        block, _ = guard.decision("env -u CLOUDSDK_CORE_FORMAT gcloud scheduler jobs list")
        assert block is False

    def test_grep_of_cloudsdk_core_format_name_with_no_gcloud_allows(self):
        block, _ = guard.decision("grep -rn CLOUDSDK_CORE_FORMAT hooks/block_gcloud_identity.py")
        assert block is False

    def test_message_names_the_reason_and_persistence(self):
        msg = guard._message_for("config-set-format")
        assert "config-set-format" in msg
        msg2 = guard._message_for("format-env-override")
        assert "format-env-override" in msg2
        assert "CLOUDSDK_CORE_FORMAT" in msg2


# ===========================================================================
# P2-1 (round 4 fix round, non-blocking finding): `run worker-pools
# describe|list`, `run worker-pools revisions describe|list`, hidden `run
# configurations describe`, and `functions deploy`'s own unmasked default
# dump.
# ===========================================================================


class TestP2OneNewVerbGroups:
    def test_worker_pools_describe_denies_bare(self):
        block, reason = guard.decision("gcloud run worker-pools describe wp")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_worker_pools_describe_masked_allows(self):
        block, _ = guard.decision(
            "gcloud run worker-pools describe wp "
            "--format='table(metadata.name,status.conditions[0].type)'"
        )
        assert block is False

    def test_worker_pools_list_bare_allows(self):
        block, _ = guard.decision("gcloud run worker-pools list")
        assert block is False

    def test_worker_pools_list_full_dump_denies(self):
        block, reason = guard.decision("gcloud run worker-pools list --format=json")
        assert block is True
        assert reason == "list-unmasked-format"

    def test_worker_pools_revisions_describe_denies_bare(self):
        block, reason = guard.decision("gcloud run worker-pools revisions describe rev")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_worker_pools_revisions_list_bare_allows(self):
        block, _ = guard.decision("gcloud run worker-pools revisions list")
        assert block is False

    def test_configurations_describe_denies_bare(self):
        block, reason = guard.decision("gcloud run configurations describe cfg")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_configurations_describe_masked_allows(self):
        block, _ = guard.decision(
            "gcloud run configurations describe cfg --format='table(metadata.name,status.url)'"
        )
        assert block is False

    def test_configurations_list_bare_allows(self):
        # list's own default is already a safe summary table -- no entry
        # needed, matching every other list verb's "already safe" shape.
        block, _ = guard.decision("gcloud run configurations list")
        assert block is False

    def test_functions_deploy_denies_bare(self):
        block, reason = guard.decision(
            "gcloud functions deploy myfn --runtime=python312 --trigger-http"
        )
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_functions_deploy_masked_allows(self):
        block, _ = guard.decision(
            "gcloud functions deploy myfn --runtime=python312 --trigger-http "
            "--format='table(name,state,status)'"
        )
        assert block is False


class TestIsSafeFormatValue:
    @pytest.mark.parametrize(
        "value,family",
        [
            ("table(name,schedule,state)", "scheduler-job"),
            ("yaml(name)", "scheduler-job"),
            ("json(metadata.name)", "run-service"),
            ("value(status.conditions[0].type)", "run-job"),
            ("csv(name,state)", "scheduler-job"),
            ("TABLE(name,schedule,state)", "scheduler-job"),  # kind is case-insensitive
            ("table(httpTarget.httpMethod)", "scheduler-job"),  # allowlisted dotted leaf
            ("table(HTTPTARGET.HTTPMETHOD)", "scheduler-job"),  # field match is case-insensitive too
        ],
    )
    def test_safe_projections(self, value, family):
        assert guard._is_safe_format_value(value, family) is True

    @pytest.mark.parametrize(
        "value,family",
        [
            ("", "scheduler-job"),
            ("   ", "scheduler-job"),
            ("yaml", "scheduler-job"),
            ("json", "scheduler-job"),
            ("text", "scheduler-job"),
            ("table", "scheduler-job"),
            ("default", "scheduler-job"),
            ("table()", "scheduler-job"),
            ("yaml(httpTarget.headers)", "scheduler-job"),
            ("json(spec.template.spec.containers[].env)", "run-service"),
            ("yaml(serviceConfig.oidcToken)", "function"),
            ("value(metadata.annotations.SECRET)", "run-service"),
            ("csv(Authorization)", "scheduler-job"),
            ("not-a-projection-at-all", "scheduler-job"),
            # ROUND 2 (B1): a PARENT key is denied even though it contains no
            # unsafe-looking substring -- this is the allowlist behavior the
            # old substring-blocklist design could not express.
            ("yaml(httpTarget)", "scheduler-job"),
            ("json(httpTarget,name)", "scheduler-job"),
            ("value(appEngineHttpTarget)", "scheduler-job"),
            ("yaml(spec)", "run-service"),
            ("json(spec.template.spec.containers)", "run-service"),
            ("yaml(template)", "run-service"),
            ("json(serviceConfig)", "function"),
            ("json(buildConfig)", "function"),
            ("value(httpTarget.body)", "scheduler-job"),
            ("value(pubsubTarget.attributes)", "scheduler-job"),
            ("value(pubsubTarget.data)", "scheduler-job"),
            ("value(httpTarget.uri)", "scheduler-job"),
            # `.` / `*` wildcard fields are always unsafe.
            ("yaml(.)", "scheduler-job"),
            ("yaml(*)", "scheduler-job"),
            # An unrecognized family has no allowlist at all -- always unsafe.
            ("table(name)", "not-a-real-family"),
            # A field that isn't unsafe-LOOKING but also isn't on the
            # allowlist must still be denied (allowlist, not blocklist).
            ("yaml(totallyBenignField)", "scheduler-job"),
        ],
    )
    def test_unsafe_or_malformed(self, value, family):
        assert guard._is_safe_format_value(value, family) is False

    # #5936 item 2: the three Cloud Run networking annotation leaves.
    @pytest.mark.parametrize(
        "value",
        [
            'value(spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector")',
            'value(spec.template.metadata.annotations."run.googleapis.com/vpc-access-egress")',
            'value(metadata.annotations."run.googleapis.com/ingress")',
            'table(metadata.name,spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector")',
        ],
    )
    def test_run_service_networking_annotation_leaves_allowed(self, value):
        assert guard._is_safe_format_value(value, "run-service") is True

    @pytest.mark.parametrize(
        "value",
        [
            # the parent annotations map can carry arbitrary values: still denied
            "value(spec.template.metadata.annotations)",
            "json(metadata.annotations)",
            # an allowlisted leaf never licenses a secret-bearing one beside it
            'json(spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector",spec.template.spec.containers[].env)',
            # a different annotation key is not on the allowlist
            'value(spec.template.metadata.annotations."run.googleapis.com/secrets")',
            # quoted keys match case-sensitively in gcloud, so a case variant of
            # an allowed key names a DIFFERENT annotation: denied (finding 1)
            'value(metadata.annotations."run.googleapis.com/INGRESS")',
            'value(spec.template.metadata.annotations."Run.googleapis.com/vpc-access-connector")',
        ],
    )
    def test_run_service_other_annotations_still_denied(self, value):
        assert guard._is_safe_format_value(value, "run-service") is False

    def test_ws13a_a1_command_allowed_end_to_end(self):
        block, _ = guard.decision(
            "gcloud run services describe agency-backend --region us-central1 "
            "--account=ops@example.com --project=example-project "
            """--format='value(spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector")'"""
        )
        assert block is False

    def test_ws13a_a1_projection_plus_env_denied_end_to_end(self):
        block, reason = guard.decision(
            "gcloud run services describe agency-backend --region us-central1 "
            """--format='json(spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector",spec.template.spec.containers[].env)'"""
        )
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_never_raises_on_garbage(self):
        for bad in (None, 12345, [], {}):
            assert guard._is_safe_format_value(bad, "scheduler-job") is False  # type: ignore[arg-type]

    def test_never_raises_on_garbage_family(self):
        assert guard._is_safe_format_value("table(name)", None) is False  # type: ignore[arg-type]
        assert guard._is_safe_format_value("table(name)", "") is False


# ===========================================================================
# Escape hatch + inline tripwire — same convention as block_branch_ops.py /
# block_head_overwrite.py, same literal var name.
# ===========================================================================


class TestEscapeHatchAndTripwire:
    def test_inline_tripwire_always_blocks_regardless_of_env(self, monkeypatch):
        monkeypatch.setenv(guard.ESCAPE_VAR, "1")
        block, reason = guard.decision(
            "gcloud config set account $CSA_ALLOW_GIT_STATE_OPS"
        )
        assert block is True
        assert reason == "inline-escape-var-forbidden"

    def test_escape_var_name_matches_block_branch_ops(self):
        import block_branch_ops as bbo

        assert guard.ESCAPE_VAR == bbo.ESCAPE_VAR

    def test_main_escape_hatch_allows_through(self, sandbox, monkeypatch, capsys):
        monkeypatch.setenv("CSA_ENFORCE", "1")
        monkeypatch.setenv(guard.ESCAPE_VAR, "1")
        rc, out = _run_main(
            monkeypatch, _ev("gcloud config set account other@example.com"), capsys
        )
        assert rc == 0
        assert out == ""
        log_lines = sandbox.log_file.read_text().splitlines()
        assert any(
            '"escape-allowed"' in ln and "block_gcloud_identity" in ln for ln in log_lines
        )


# ===========================================================================
# B1 (#5890 round 4 fix round): a group-level flag before
# the verb (`run services --region R describe`) must not hide the path.
# Cross-product: every `run` verb group this module covers x every
# group-level flag `run` actually declares, placed BEFORE the verb, for both
# `describe` and `list --format=json` -- each paired with the correctly
# masked command in the SAME placement.
# ===========================================================================

# The 4 `run` verb groups covered by _DESCRIBE_VERB_GROUPS/_LIST_VERB_GROUPS,
# with a resource-id token for describe (positional) and a safe masked
# --format for the paired allow case.
_RUN_DESCRIBE_GROUPS_FOR_B1: tuple[tuple[str, ...], ...] = (
    ("run", "services", "describe"),
    ("run", "jobs", "describe"),
    ("run", "jobs", "executions", "describe"),
    ("run", "revisions", "describe"),
)
_RUN_LIST_GROUPS_FOR_B1: tuple[tuple[str, ...], ...] = (
    ("run", "services", "list"),
    ("run", "jobs", "list"),
    ("run", "jobs", "executions", "list"),
    ("run", "revisions", "list"),
)

# Verified against the real installed CLI (SDK 574.0.0) and the SDK's own
# source (`googlecloudsdk/command_lib/run/flags.py`'s
# `AddPlatformAndLocationFlags`/`AddRegionArg`, called from each `run`
# subcommand group's own `__init__.py`) -- see `_RUN_GROUP_VALUE_FLAGS`'s
# sourcing comment in block_gcloud_identity.py for the full citation.
_B1_GROUP_LEVEL_FLAGS: tuple[tuple[str, str], ...] = (
    ("--region", "us-central1"),
    ("--platform", "managed"),
    ("--cluster", "my-cluster"),
    ("--cluster-location", "us-central1"),
    ("--context", "my-context"),
    ("--kubeconfig", "/tmp/kc"),
)

_B1_DESCRIBE_CASES: list[tuple[str, str]] = []
for _grp in _RUN_DESCRIBE_GROUPS_FOR_B1:
    for _flag, _val in _B1_GROUP_LEVEL_FLAGS:
        _grp_str = " ".join(_grp[:-1])  # group, no verb yet
        _id = f"B1-describe:{_grp_str}:{_flag}"
        _bare = f"gcloud {_grp_str} {_flag} {_val} describe res"
        # `metadata.name` is a safe leaf field on every `run-*` describe
        # family (`run-service`/`run-job`/`run-revision`/`run-execution`),
        # unlike `status.url` (run-service only) -- using it here keeps this
        # matrix's masked case valid regardless of which family the group
        # actually maps to.
        _masked = _bare + " --format='value(metadata.name)'"
        _B1_DESCRIBE_CASES.append((_id + ":bare", _bare, True))
        _B1_DESCRIBE_CASES.append((_id + ":masked", _masked, False))

_B1_LIST_CASES: list[tuple[str, str]] = []
for _grp in _RUN_LIST_GROUPS_FOR_B1:
    for _flag, _val in _B1_GROUP_LEVEL_FLAGS:
        _grp_str = " ".join(_grp[:-1])
        _id = f"B1-list:{_grp_str}:{_flag}"
        _full_dump = f"gcloud {_grp_str} {_flag} {_val} list --format=json"
        _masked = f"gcloud {_grp_str} {_flag} {_val} list --format='value(metadata.name)'"
        _B1_LIST_CASES.append((_id + ":full-dump", _full_dump, True))
        _B1_LIST_CASES.append((_id + ":masked", _masked, False))

_B1_ALL_CASES = _B1_DESCRIBE_CASES + _B1_LIST_CASES


class TestGroupLevelFlagBeforeVerbDoesNotHidePath:
    @pytest.mark.parametrize(
        "label,command,should_block",
        _B1_ALL_CASES,
        ids=[c[0] for c in _B1_ALL_CASES],
    )
    def test_group_level_flag_placement(self, label, command, should_block):
        block, reason = guard.decision(command)
        assert block is should_block, f"{label}: {command!r} -> block={block} reason={reason!r}"

    def test_scheduler_has_no_group_level_flag_hazard(self):
        # `scheduler jobs` has NO group-level flags at all (confirmed live:
        # `gcloud scheduler jobs --location X describe` errors "unrecognized
        # arguments") -- a --location BEFORE the verb is simply an unknown
        # subcommand-local-shaped flag with no ambiguity to resolve, and the
        # bare verb (no masked format) still denies via the ordinary
        # describe-unmasked-format path, exactly as if the flag were absent.
        block, reason = guard.decision("gcloud scheduler jobs describe j")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_functions_has_no_group_level_flag_hazard(self):
        block, reason = guard.decision("gcloud functions describe fn")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_multiple_group_level_flags_stacked(self):
        # --cluster and --cluster-location together, both before the verb --
        # B1's variant walk must branch correctly even with 2 unknown flags
        # in a row, not just 1.
        block, reason = guard.decision(
            "gcloud run services --cluster c --cluster-location us-central1 describe svc"
        )
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_group_level_flag_after_the_verb_still_works_as_before(self):
        # The flag doesn't have to be BEFORE the verb to matter -- confirm
        # the ordinary post-verb placement (already correct pre-B1) still
        # works via the fix, not just the pre-existing single-reading path.
        block, reason = guard.decision(
            "gcloud run services describe svc --region us-central1"
        )
        assert block is True
        assert reason == "describe-unmasked-format"


# ===========================================================================
# B2 (#5890 round 4 fix round): a gcloud invocation hidden
# behind a wrapper, shell keyword, or quoted command substitution must not
# be invisible to this gate. Cross-product: every wrapper/keyword x every
# gcloud shape (bare describe, masked list, --log-http, config set account).
# ===========================================================================

_B2_GCLOUD_SHAPES: tuple[tuple[str, str, bool, str], ...] = (
    ("bare-describe", "gcloud scheduler jobs describe j", True, "describe-unmasked-format"),
    (
        "list-format-json",
        "gcloud scheduler jobs list --format=json",
        True,
        "list-unmasked-format",
    ),
    (
        "log-http",
        "gcloud scheduler jobs list --log-http",
        True,
        "log-http-leaks-response",
    ),
    (
        "config-set-account",
        "gcloud config set account other@example.com",
        True,
        "config-set-account",
    ),
)


def _wrap_env(inner: str) -> str:
    return f"env {inner}"


def _wrap_env_var(inner: str) -> str:
    return f"env FOO=1 {inner}"


def _wrap_sudo(inner: str) -> str:
    return f"sudo {inner}"


def _wrap_command(inner: str) -> str:
    return f"command {inner}"


def _wrap_exec(inner: str) -> str:
    return f"exec {inner}"


def _wrap_time(inner: str) -> str:
    return f"time {inner}"


def _wrap_timeout(inner: str) -> str:
    return f"timeout 60 {inner}"


def _wrap_nohup(inner: str) -> str:
    return f"nohup {inner}"


def _wrap_for_do(inner: str) -> str:
    return f"for x in a; do {inner}; done"


def _wrap_if_then(inner: str) -> str:
    return f"if {inner}; then echo ok; fi"


def _wrap_brace(inner: str) -> str:
    return f"{{ {inner}; }}"


def _wrap_bang(inner: str) -> str:
    return f"! {inner}"


def _wrap_xargs(inner: str) -> str:
    return f"xargs -n1 {inner} < f"


def _wrap_bash_c(inner: str) -> str:
    return f"bash -c '{inner}'"


def _wrap_eval(inner: str) -> str:
    return f"eval '{inner}'"


def _wrap_dollar_paren_quoted(inner: str) -> str:
    return f'out="$({inner})"; echo "$out"'


def _wrap_backtick_quoted(inner: str) -> str:
    return f'echo "`{inner}`"'


_B2_WRAPPERS: tuple[tuple[str, object], ...] = (
    ("env", _wrap_env),
    ("env-var", _wrap_env_var),
    ("sudo", _wrap_sudo),
    ("command", _wrap_command),
    ("exec", _wrap_exec),
    ("time", _wrap_time),
    ("timeout-N", _wrap_timeout),
    ("nohup", _wrap_nohup),
    ("for-do", _wrap_for_do),
    ("if-then", _wrap_if_then),
    ("brace", _wrap_brace),
    ("bang", _wrap_bang),
    ("xargs", _wrap_xargs),
    ("bash-c", _wrap_bash_c),
    ("eval", _wrap_eval),
    ("dollar-paren-quoted", _wrap_dollar_paren_quoted),
    ("backtick-quoted", _wrap_backtick_quoted),
)

_B2_ALL_CASES: list[tuple[str, str, bool, str]] = []
for _wname, _wfn in _B2_WRAPPERS:
    for _sname, _scmd, _sblock, _sreason in _B2_GCLOUD_SHAPES:
        _wrapped = _wfn(_scmd)
        _B2_ALL_CASES.append((f"{_wname}:{_sname}", _wrapped, _sblock, _sreason))


class TestWrapperShellKeywordAndSubstitutionNeverHidesGcloud:
    @pytest.mark.parametrize(
        "label,command,should_block,expected_reason",
        _B2_ALL_CASES,
        ids=[c[0] for c in _B2_ALL_CASES],
    )
    def test_wrapped_gcloud_shape(self, label, command, should_block, expected_reason):
        block, reason = guard.decision(command)
        assert block is should_block, f"{label}: {command!r} -> block={block} reason={reason!r}"
        if should_block:
            assert reason == expected_reason, f"{label}: {command!r} -> reason={reason!r}"

    def test_heredoc_body_fed_to_bash_direct(self):
        cmd = "bash <<'EOF'\ngcloud scheduler jobs describe j\nEOF"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_heredoc_body_fed_to_bash_via_pipe(self):
        cmd = "cat <<'EOF' | bash\ngcloud scheduler jobs describe j\nEOF"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_heredoc_body_with_masked_format_allows(self):
        cmd = "bash <<'EOF'\ngcloud scheduler jobs describe j --format='value(name)'\nEOF"
        block, _ = guard.decision(cmd)
        assert block is False

    def test_bash_c_with_masked_format_allows(self):
        # Double-quoted --format value nests safely inside the single-quote
        # bash -c wrapper (unlike an inner single-quote, which would
        # prematurely close the wrapper's own quoting).
        cmd = 'bash -c "gcloud scheduler jobs describe j --format=\'value(name)\'"'
        block, _ = guard.decision(cmd)
        assert block is False

    def test_dollar_paren_with_masked_format_allows(self):
        # Single-quoted --format value nests safely inside the double-quote
        # $(...) wrapper.
        cmd = "out=\"$(gcloud scheduler jobs describe j --format='value(name)')\"; echo \"$out\""
        block, _ = guard.decision(cmd)
        assert block is False

    def test_cloudsdk_core_log_http_through_bash_c_wrapper(self):
        # The real incident shape: the env var assignment and the gcloud
        # call are BOTH inside the same bash -c string.
        cmd = "bash -c 'export CLOUDSDK_CORE_LOG_HTTP=1; gcloud run services list'"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_cloudsdk_core_log_http_before_bash_c_wrapper(self):
        # The env var is set OUTSIDE the wrapper, in a preceding segment --
        # `_mentions_gcloud_anywhere` must still find the nested gcloud call
        # to correctly scope the raw-text tripwire.
        cmd = "export CLOUDSDK_CORE_LOG_HTTP=1; bash -c 'gcloud run services list'"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "log-http-leaks-response"


class TestWrapperFalsePositiveDoesNotBreakUnrelatedRecoveryForms:
    """The ALLOW-side recovery/documentation forms this module has always
    kept green must stay green even with B2's widened scanning -- these are
    the exact commands the cold round-4 review listed as "must stay
    working": a docs grep, a pytest -k selector, git commit -F naming these
    files, masked describes, bare lists, and heredoc notes about this
    module."""

    def test_grep_of_module_source_mentioning_the_env_var_name(self):
        block, _ = guard.decision(
            "grep -rn 'CLOUDSDK_CORE_LOG_HTTP' ~/.claude/hooks/block_gcloud_identity.py"
        )
        assert block is False

    def test_pytest_k_selector_mentioning_the_env_var_name(self):
        block, _ = guard.decision(
            "python3 -m pytest ~/.claude/hooks/tests/test_block_gcloud_identity.py "
            "-k CLOUDSDK_CORE_LOG_HTTP -q"
        )
        assert block is False

    def test_git_commit_naming_this_modules_files(self):
        block, _ = guard.decision(
            "git commit -F /tmp/msg.txt -- hooks/block_gcloud_identity.py "
            "knowledge/gcloud_identity_is_machine_wide.md"
        )
        assert block is False

    def test_rg_search_of_knowledge_docs(self):
        block, _ = guard.decision(
            "rg -n 'gcloud scheduler jobs describe' ~/.claude/knowledge/"
        )
        assert block is False

    def test_heredoc_note_mentioning_gcloud_as_inert_text_no_interpreter(self):
        # A heredoc fed to `cat` (not a shell interpreter) -- inert text,
        # never executed, must stay allowed exactly as before B2.
        cmd = "cat > /tmp/notes.md <<'EOF'\nRun this:\ngcloud scheduler jobs describe my-job\nEOF"
        block, _ = guard.decision(cmd)
        assert block is False

    def test_echo_of_gcloud_identity_mutation_is_the_documented_false_positive(self):
        # B2's own documented, ACCEPTED tradeoff (see
        # `_find_gcloud_argv`'s own docstring): scanning every token for a
        # `gcloud` program token -- rather than tracking a specific
        # wrapper's own arity -- means `echo gcloud config set account x`
        # (where "gcloud config set account x" is merely echo's own
        # ARGUMENT, never actually executed as a program) IS treated as a
        # real gcloud invocation and denied. This is the accepted rare
        # false positive, not a bug: a security gate erring toward
        # DENYING an ambiguous shape is the correct direction, and this
        # exact case is called out by name in this module's own docstring.
        block, reason = guard.decision("echo gcloud config set account x")
        assert block is True
        assert reason == "config-set-account"

    def test_echo_of_an_unrelated_gcloud_verb_is_the_same_documented_false_positive(self):
        # The read-only-shaped counterpart of the case above -- confirms the
        # false positive is a genuine token-scan artifact (it fires
        # regardless of which gcloud verb follows), not something special
        # about identity-mutation verbs specifically.
        block, reason = guard.decision("echo gcloud auth list")
        assert block is False
        assert reason == "no-gcloud-identity-mutation"


class TestUntokenizableFailsClosed:
    def test_unbalanced_quote_in_a_gcloud_segment_blocks(self):
        block, reason = guard.decision("gcloud config set account 'unterminated")
        assert block is True
        assert reason == "untokenizable-segment-with-gcloud"

    def test_unbalanced_quote_with_no_gcloud_mention_allows(self):
        # An untokenizable segment that never mentions gcloud at all has
        # nothing for this gate to guard -- no fail-closed concern.
        block, _ = guard.decision("echo 'unterminated")
        assert block is False


# ===========================================================================
# #5890 round 2: mutant-killing coverage for the new
# deny-message branches, the list-unsafe-projection shape (not just
# full-dump), and the empty-field-list check under the new allowlist design.
# ===========================================================================


class TestRound2MessageBranches:
    def test_describe_multiple_format_message_names_the_reason(self):
        msg = guard._message_for("describe-multiple-format")
        assert "describe-multiple-format" in msg
        assert "--format" in msg

    def test_list_multiple_format_message_names_the_reason(self):
        msg = guard._message_for("list-multiple-format")
        assert "list-multiple-format" in msg

    def test_describe_flags_file_message_names_the_reason(self):
        msg = guard._message_for("describe-flags-file")
        assert "describe-flags-file" in msg
        assert "flags-file" in msg

    def test_list_flags_file_message_names_the_reason(self):
        msg = guard._message_for("list-flags-file")
        assert "list-flags-file" in msg

    def test_log_http_message_names_the_reason(self):
        msg = guard._message_for("log-http-leaks-response")
        assert "log-http-leaks-response" in msg
        assert "--log-http" in msg

    def test_config_set_log_http_message_names_the_reason(self):
        # #5890 round 3 fix round, item 1: `config-set-log-http`
        # used to have no dedicated branch and fell into the generic
        # "reserved for the operator" fallback, whose text reads like every
        # OTHER identity-mutation reason -- indistinguishable from
        # config-set-account, auth-revoke, etc. It is a genuinely different
        # hazard class (a persistent property write causing a future
        # response-body leak, not an identity mutation), so its own message
        # must name the reason and explain the persistent/machine-wide
        # response-leak mechanism distinctly.
        msg = guard._message_for("config-set-log-http")
        assert "config-set-log-http" in msg
        assert "log_http" in msg

    def test_config_set_log_http_message_is_not_the_identity_mutation_text(self):
        # Must not read as a copy of the identity-mutation family's message
        # (config-set-account, config-configurations-activate, etc.) -- this
        # is a persistent RESPONSE-LEAK hazard, not an account/ADC identity
        # change, and the message must say so rather than reuse that phrasing.
        msg = guard._message_for("config-set-log-http")
        assert "active account" not in msg
        assert "re-identif" not in msg
        assert "response" in msg.lower()

    def test_config_set_log_http_message_notes_persistence_and_machine_wide_scope(self):
        msg = guard._message_for("config-set-log-http")
        assert "persist" in msg.lower()
        assert "#5310" in msg

    def test_describe_unmasked_format_message_gives_a_working_safe_form_with_no_command(self):
        # No `command` given (the pre-round-2-B6 call shape every direct
        # `_message_for(reason)` caller in this file still uses elsewhere) ->
        # falls back to the scheduler-job example, which is still correct
        # advice for SOME family even though it isn't tailored.
        msg = guard._message_for("describe-unmasked-format")
        assert "table(name,schedule,state)" in msg

    def test_list_unmasked_format_message_gives_a_working_safe_form_with_no_command(self):
        msg = guard._message_for("list-unmasked-format")
        assert "table(name,schedule,state)" in msg

    def test_list_unmasked_format_message_no_longer_claims_full_dump_only(self):
        # ROUND 2 (D1): the old message text said "with a full-dump --format",
        # but `list-unmasked-format` also fires on an explicit UNSAFE
        # PROJECTION naming a field outside the family's allowlist (see
        # TestListUnsafeProjectionNotJustFullDump above) -- not only a bare
        # yaml/json/text full dump. The message must not claim a narrower
        # trigger than the code actually has.
        msg = guard._message_for("list-unmasked-format")
        assert "full-dump" not in msg


# ===========================================================================
# ROUND 2 fix (B6): the suggested safe --format hint must actually pass
# decision() for the SPECIFIC family the denied command belongs to, not just
# for scheduler-job. `_safe_format_hint()` used to return one shared example
# (`table(name,schedule,state)`) regardless of family -- `name`/`schedule`/
# `state` are scheduler-job-only top-level fields, so an agent following that
# advice on any of the other 6 verb groups (run-service, run-job,
# run-revision, run-execution, function... 6 of 7 families) was denied AGAIN
# by the message meant to unblock it. `test_describe_unmasked_format_message_
# still_gives_a_working_safe_form` (pre-round-2 name) asserted exactly the
# broken shared string and never checked it against decision() at all -- a
# lock-in test whose name claimed the opposite of what it proved.
#
# For EVERY covered describe/list verb group: deny the bare verb, extract the
# --format hint from the deny message, substitute it into the SAME command,
# and assert decision() now ALLOWS it. This is a genuine round-trip through
# the real message text an agent actually reads, not a hand-picked example
# checked only against _is_safe_format_value in isolation.
# ===========================================================================

# `verb_command` is the bare verb path with no --format at all (a resource
# name token `j` is appended for `describe`, which requires a positional
# resource id; `list` takes none). `deny_command` is what's actually run to
# TRIGGER the deny this test starts from: `describe`'s bare verb already
# denies (gcloud's own default describe output is a full dump); `list`'s own
# default is already a safe summary table, so a bare `list` is ALLOWED by
# design -- an explicit bare full-dump `--format=yaml` is added instead to
# reach a genuinely denied starting point.
#
# P3-4 (#5890 round 4 fix round): the 14 (group, family)
# pairs below are a FIXED LITERAL list, deliberately NOT derived from
# `guard._DESCRIBE_VERB_GROUPS`/`guard._LIST_VERB_GROUPS` the way an earlier
# version of this constant was. Deriving from the module's own tuples meant
# a verb group silently DELETED from the module (whether by accident or a
# future refactor) would just as silently shrink this parametrize list --
# the test suite would keep passing with narrower coverage and nobody would
# notice a covered command dropped out of the matrix. Pinning to a literal
# list makes that shape a LOUD failure instead:
# `test_pinned_list_matches_module_verb_groups` below fails the moment the
# two disagree, in EITHER direction (module has an entry this list doesn't,
# or vice versa) -- so a genuine module change (adding/removing a verb
# group) requires a deliberate edit to this literal list too, not a silent
# pass-through.
_DESCRIBE_GROUPS_LITERAL: tuple[tuple[tuple[str, ...], str], ...] = (
    (("scheduler", "jobs", "describe"), "scheduler-job"),
    (("run", "services", "describe"), "run-service"),
    (("run", "jobs", "describe"), "run-job"),
    (("run", "revisions", "describe"), "run-revision"),
    (("run", "jobs", "executions", "tasks", "describe"), "run-execution"),
    (("run", "jobs", "executions", "describe"), "run-execution"),
    (("functions", "describe"), "function"),
    # P2-1 (round 4 fix round): worker-pools / configurations / functions
    # deploy, added alongside the module's own new verb-group entries.
    (("run", "worker-pools", "revisions", "describe"), "run-worker-pool"),
    (("run", "worker-pools", "describe"), "run-worker-pool"),
    (("run", "configurations", "describe"), "run-service"),
    (("functions", "deploy"), "function"),
)
_LIST_GROUPS_LITERAL: tuple[tuple[tuple[str, ...], str], ...] = (
    (("scheduler", "jobs", "list"), "scheduler-job"),
    (("run", "services", "list"), "run-service"),
    (("run", "jobs", "list"), "run-job"),
    (("run", "revisions", "list"), "run-revision"),
    (("run", "jobs", "executions", "tasks", "list"), "run-execution"),
    (("run", "jobs", "executions", "list"), "run-execution"),
    (("functions", "list"), "function"),
    (("run", "worker-pools", "revisions", "list"), "run-worker-pool"),
    (("run", "worker-pools", "list"), "run-worker-pool"),
)


def test_pinned_list_matches_module_verb_groups():
    # P3-4: this is what makes the LITERAL lists above safe to hardcode --
    # any drift between them and the module's own `_DESCRIBE_VERB_GROUPS`/
    # `_LIST_VERB_GROUPS` fails HERE, loudly, rather than silently shrinking
    # `_ALL_VERB_GROUPS_WITH_FAMILY`'s parametrize coverage below.
    assert _DESCRIBE_GROUPS_LITERAL == guard._DESCRIBE_VERB_GROUPS
    assert _LIST_GROUPS_LITERAL == guard._LIST_VERB_GROUPS


# `functions deploy` is excluded from this auto-generated matrix: unlike
# every other DESCRIBE-shaped entry, `deploy` does not accept a bare
# positional resource-id with no other flags (`gcloud functions deploy j`
# alone is a real-world argument error -- deploy needs --runtime/--trigger-*
# etc.), so the mechanical "`group + (resource-id,)`" construction below
# would build an invalid command for it. It gets its own dedicated
# round-trip test (`TestFunctionsDeployHintRoundTrips` below) instead.
_DEPLOY_SHAPED_ENTRIES = frozenset({("functions", "deploy")})
_ALL_VERB_GROUPS_WITH_FAMILY: tuple[tuple[str, str, str], ...] = tuple(
    (" ".join(("gcloud",) + group + ("j",)), " ".join(("gcloud",) + group + ("j",)), family)
    for group, family in _DESCRIBE_GROUPS_LITERAL
    if group not in _DEPLOY_SHAPED_ENTRIES
) + tuple(
    (" ".join(("gcloud",) + group), " ".join(("gcloud",) + group) + " --format=yaml", family)
    for group, family in _LIST_GROUPS_LITERAL
)


class TestFunctionsDeployHintRoundTrips:
    def test_hint_extracted_from_deny_message_then_allows(self):
        deny_command = (
            "gcloud functions deploy myfn --runtime=python312 --trigger-http"
        )
        block, reason = guard.decision(deny_command)
        assert block is True
        assert reason == "describe-unmasked-format"

        msg = guard._message_for(reason, deny_command)
        marker = "instead: --format='"
        assert marker in msg
        start = msg.index(marker) + len(marker)
        end = msg.index("'", start)
        hint_value = msg[start:end]

        retry_command = deny_command + " --format='" + hint_value + "'"
        retry_block, retry_reason = guard.decision(retry_command)
        assert retry_block is False, (
            f"hint {hint_value!r} still fails on retry ({retry_reason!r}) -- {retry_command!r}"
        )


class TestSafeFormatHintPassesDecisionForEveryFamily:
    @pytest.mark.parametrize(
        "verb_command,deny_command,family",
        _ALL_VERB_GROUPS_WITH_FAMILY,
        ids=[c for c, _, _ in _ALL_VERB_GROUPS_WITH_FAMILY],
    )
    def test_hint_extracted_from_deny_message_then_allows(self, verb_command, deny_command, family):
        # Step 1: the starting command (bare describe, or list with an
        # explicit full-dump --format) is denied.
        block, reason = guard.decision(deny_command)
        assert block is True, f"{deny_command!r} should have been denied first"
        assert reason in ("describe-unmasked-format", "list-unmasked-format")

        # Step 2: extract the hint from the REAL deny message text (the exact
        # string an agent actually reads), the same way `_message_for` builds
        # it -- passing `command=deny_command` so the family-specific branch
        # is exercised, not the no-command fallback.
        msg = guard._message_for(reason, deny_command)
        marker = "instead: --format='"
        assert marker in msg, f"deny message for {family!r} has no extractable hint: {msg!r}"
        start = msg.index(marker) + len(marker)
        end = msg.index("'", start)
        hint_value = msg[start:end]

        # Step 3: substitute the extracted hint into the bare VERB command
        # (never append onto the deny command, which would carry a second
        # --format and trip describe/list-multiple-format instead) and
        # assert decision() now ALLOWS it -- the actual bar B6 sets: an agent
        # that follows the message must not be denied again.
        retry_command = verb_command + " --format='" + hint_value + "'"
        retry_block, retry_reason = guard.decision(retry_command)
        assert retry_block is False, (
            f"family {family!r}: hint {hint_value!r} extracted from the deny "
            f"message still does not pass decision() ({retry_reason!r}) -- "
            f"command was {retry_command!r}"
        )


# ===========================================================================
# #5890 round 3, round-3-review BLOCKER: the test class
# above (`TestSafeFormatHintPassesDecisionForEveryFamily`) calls
# `guard._message_for(reason, deny_command)` DIRECTLY -- it never touches the
# real dispatcher call site an agent's actual denied command goes through,
# `hooks/pretooluse_bash.py`'s `_gcloud_identity_block`, which (before this
# round's fix) called `bgi._message_for(reason)` with NO `command` argument.
# With no `command`, `_family_for_command` always returns `None`, so all 6 of
# 7 non-scheduler-job families' deny messages silently fell back to the
# scheduler-job hint (`table(name,schedule,state)`) -- an agent that read the
# REAL message text (as opposed to a direct `_message_for(reason, cmd)` call
# in a test) and followed its advice was denied again on retry, for every
# family except scheduler-job. This class reproduces the identical
# round-trip as the class above, but through `pretooluse_bash._gcloud_
# identity_block` -- the actual registered dispatcher entry point
# (`hooks/pretooluse_bash.py`'s `resolve_block` calls it directly) -- so a
# regression at that specific call site (e.g. the `_message_for(reason)` ->
# `_message_for(reason, command)` argument silently dropped again) is caught
# by THIS suite, not only by a direct-call test that can never see it.
# ===========================================================================


class TestDispatcherGcloudIdentityBlockHintRoundTripsForEveryFamily:
    """Round-trip the SAME 14 describe/list verb groups
    (`_ALL_VERB_GROUPS_WITH_FAMILY`, defined above) through the real
    dispatcher entry point `pretooluse_bash._gcloud_identity_block`, not
    `guard._message_for` directly. Proven RED against the pre-fix dispatcher
    (`bgi._message_for(reason)` with no `command`): 12 of these 14 cases
    failed (every family except scheduler-job, which happens to be the
    hard-coded fallback `_safe_format_hint`/`_family_for_command` return when
    no family can be derived)."""

    @pytest.mark.parametrize(
        "verb_command,deny_command,family",
        _ALL_VERB_GROUPS_WITH_FAMILY,
        ids=[c for c, _, _ in _ALL_VERB_GROUPS_WITH_FAMILY],
    )
    def test_dispatcher_hint_extracted_from_real_block_message_then_allows(
        self, verb_command, deny_command, family
    ):
        # Step 1: the starting command is denied via the REAL dispatcher
        # entry point, not guard.decision() directly -- pretooluse_bash's
        # _gcloud_identity_block wraps bgi.decision() and is what an agent's
        # actual denied Bash call resolves through.
        block = pbash._gcloud_identity_block(deny_command)
        assert block is not None, f"{deny_command!r} should have been denied first"
        assert block.reason in ("describe-unmasked-format", "list-unmasked-format")

        # Step 2: extract the hint from the block's own .message -- the
        # EXACT text an agent actually reads under enforcement (built via
        # `_Block(..., bgi._message_for(reason, command), ...)` inside
        # `_gcloud_identity_block`), not a hand-constructed call to
        # `_message_for` in this test.
        marker = "instead: --format='"
        assert marker in block.message, (
            f"dispatcher deny message for {family!r} has no extractable hint: "
            f"{block.message!r}"
        )
        start = block.message.index(marker) + len(marker)
        end = block.message.index("'", start)
        hint_value = block.message[start:end]

        # Step 3: substitute the extracted hint into the bare VERB command and
        # assert the dispatcher now ALLOWS it (returns None, meaning gate 1c
        # does not block) -- the real bar: an agent that reads and follows
        # the actual dispatcher-emitted message must not be denied again.
        retry_command = verb_command + " --format='" + hint_value + "'"
        retry_block = pbash._gcloud_identity_block(retry_command)
        assert retry_block is None, (
            f"family {family!r}: hint {hint_value!r} extracted from the REAL "
            f"dispatcher deny message still gets denied again on retry "
            f"({retry_block.reason if retry_block else None!r}) -- command "
            f"was {retry_command!r}"
        )


class TestListUnsafeProjectionNotJustFullDump:
    """`list` denies an EXPLICIT unsafe projection too, not only a bare
    yaml/json/text full dump -- proven RED pre-fix by the same allowlist gap
    B1 covers for `describe` (a projection naming an unsafe/unenumerated
    field was allowed on `list` exactly as it was on `describe`)."""

    def test_scheduler_list_with_unsafe_projection_denies(self):
        block, reason = guard.decision(
            "gcloud scheduler jobs list --format='value(httpTarget.headers)'"
        )
        assert block is True
        assert reason == "list-unmasked-format"

    def test_run_services_list_with_parent_key_projection_denies(self):
        block, reason = guard.decision(
            "gcloud run services list --format='yaml(spec)'"
        )
        assert block is True
        assert reason == "list-unmasked-format"


class TestEmptyFieldListStillUnsafeUnderAllowlist:
    """The empty-field-list case (`table()`) must stay denied under the
    allowlist rewrite. ROUND 2 CORRECTION (D1): an earlier version of this
    docstring claimed these tests catch a mutant that drops the explicit
    `if not fields_raw: return False` guard in `_is_safe_format_value`. That
    claim is false, and no test below (or added here) actually catches that
    specific mutant: `"".split(",")` returns `[""]`, so even with the guard
    removed, the per-field loop still runs once over the single empty-string
    token, which is caught by the SEPARATE `_ALWAYS_UNSAFE_FIELD_TOKENS`
    membership check (`""` is a member) before any allowlist lookup. The
    explicit `fields_raw` guard is therefore genuinely redundant with that
    membership check for a fully-empty field list, not the load-bearing
    protection this docstring used to claim -- a mutant that removes it
    survives (verified by hand: `_is_safe_format_value("table()", ...)` is
    still `False` with that one line deleted, because the fields loop and
    the always-unsafe-token check take over). These tests still correctly
    lock in the observable BEHAVIOR (empty parens denied), which is real and
    load-bearing; they just don't kill the mutant the old docstring named."""

    def test_empty_parens_denied_on_describe(self):
        block, reason = guard.decision("gcloud scheduler jobs describe j --format='table()'")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_empty_parens_denied_directly(self):
        assert guard._is_safe_format_value("table()", "scheduler-job") is False

    def test_whitespace_only_field_list_denied(self):
        assert guard._is_safe_format_value("table(   )", "scheduler-job") is False


# ===========================================================================
# main() end-to-end: log-only default, enforce emits deny, kill switch,
# malformed JSON, non-Bash tool, parse-error fail-closed.
# ===========================================================================


def test_main_log_only_default(sandbox, monkeypatch, capsys):
    rc, out = _run_main(
        monkeypatch, _ev("gcloud config set account other@example.com"), capsys
    )
    assert rc == 0
    assert out == ""
    log_lines = sandbox.log_file.read_text().splitlines()
    assert any(
        '"would-block"' in ln and "block_gcloud_identity" in ln for ln in log_lines
    )


def test_main_enforce_emits_deny(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(
        monkeypatch, _ev("gcloud config set account other@example.com"), capsys
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "block_gcloud_identity" in payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "--account=" in payload["hookSpecificOutput"]["permissionDecisionReason"]


def test_main_enforce_allows_legitimate_pattern(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(
        monkeypatch, _ev("gcloud --account=svc@example.com config list"), capsys
    )
    assert rc == 0
    assert out == ""


def test_kill_switch_short_circuits_before_anything(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_DISABLE_HOOKS", "1")
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(
        monkeypatch, _ev("gcloud config set account other@example.com"), capsys
    )
    assert rc == 0
    assert out == ""
    assert not sandbox.log_file.exists()


def test_non_bash_tool_never_blocks(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    rc, out = _run_main(
        monkeypatch,
        _ev("gcloud config set account other@example.com", tool_name="Read"),
        capsys,
    )
    assert rc == 0
    assert out == ""


def test_malformed_json_with_no_gcloud_mention_degrades_to_allow(monkeypatch, capsys):
    rc, out = _run_main(monkeypatch, "{not valid json", capsys)
    assert rc == 0
    assert out == ""


def test_malformed_json_mentioning_gcloud_fails_closed_under_enforce(
    sandbox, monkeypatch, capsys
):
    monkeypatch.setenv("CSA_ENFORCE", "1")
    raw = '{"tool_name": "Bash", "tool_input": {"command": "gcloud config set account x'
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = guard.main()
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "parse-error-with-gcloud-token" in payload["hookSpecificOutput"]["permissionDecisionReason"]


def test_malformed_json_mentioning_gcloud_log_only_default(sandbox, monkeypatch, capsys):
    raw = '{"tool_name": "Bash", "tool_input": {"command": "gcloud config set account x'
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = guard.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert out == ""
    log_lines = sandbox.log_file.read_text().splitlines()
    assert any(
        '"would-block"' in ln and "parse-error-with-gcloud-token" in ln for ln in log_lines
    )


# ===========================================================================
# decision() never raises on garbage input.
# ===========================================================================


@pytest.mark.parametrize(
    "command",
    ["", None, 12345, [], "gcloud", "gcloud config", "gcloud config set"],
)
def test_decision_never_raises_on_garbage(command):
    try:
        block, reason = guard.decision(command)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - the assertion below is the real check
        pytest.fail(f"decision() raised on {command!r}: {exc!r}")
    assert isinstance(block, bool)
    assert isinstance(reason, str)


def test_find_adc_overwrite_never_raises_on_garbage():
    for bad_command in ("", "gcloud", None, 12345, []):
        assert guard._find_adc_overwrite(bad_command) is None  # type: ignore[arg-type]


def test_gcloud_segments_never_raises_on_garbage():
    for bad_command in ("", None, 12345, []):
        assert guard._gcloud_segments(bad_command) == []  # type: ignore[arg-type]


# ===========================================================================
# ROUND 6 (#5890, round-5 review): B1-B4, P2-1..P2-4,
# P3-1..P3-3. FALSIFIABILITY: each fix below was confirmed to go RED against
# the round-5 snapshot (`r5/block_gcloud_identity.py.r5`) and GREEN against
# this round's fix, by hand, outside this file, mirroring this file's own
# documented falsifiability convention (see the module docstring above).
# ===========================================================================


class TestB1PathVariantsBounded:
    """B1: `_gcloud_command_path_variants` must never take more than a
    small, fixed amount of WORK -- asserted here on deterministic variant/
    iteration COUNTS (P3-e, round 7: wall-clock assertions are flaky on a
    loaded machine for reasons unrelated to the code under test; a count is
    deterministic and exercises the exact same bound)."""

    def test_many_unknown_flags_on_allowed_run_deploy_produces_one_variant_and_allows(self):
        # `run deploy` is never a describe/list family member, so
        # `_is_plausible_run_group_prefix` (B1-r6) finishes the branching
        # walk immediately -- exactly ONE completed branch (`["run",
        # "deploy"]`, implausible the instant "deploy" fails to match any
        # group's 2nd element) regardless of flag count. The function always
        # ALSO includes the single-reading `base_path` as element 0 (its own
        # documented, unconditional ordering guarantee) -- so the total
        # count is 2, not 1: the fixed base reading plus the one distinct
        # branch-walk result, never growing with flag count either way.
        argv = ["gcloud", "run", "deploy", "api"]
        for i in range(40):
            argv += [f"--unknown-flag-{i}", f"value{i}"]
        variants = guard._gcloud_command_path_variants(argv)
        assert len(variants) == 2
        assert list(variants[1]) == ["run", "deploy"]

        cmd = "gcloud run deploy api " + " ".join(
            f"--unknown-flag-{i} value{i}" for i in range(40)
        )
        block, _ = guard.decision(cmd)
        assert block is False

    def test_many_unknown_flags_on_blocked_describe_denies_with_bounded_variants(self):
        flags = " ".join("--no-log-http" for _ in range(40))
        cmd = f"gcloud run services describe s {flags}"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"
        # --no-log-http is a recognized GLOBAL boolean flag (never branches
        # at all), so the variant count stays at 1 regardless of how many
        # copies appear.
        argv = ["gcloud", "run", "services", "describe", "s"] + ["--no-log-http"] * 40
        variants = guard._gcloud_command_path_variants(argv)
        assert len(variants) == 1

    def test_variant_walk_is_bounded_in_variant_count(self):
        # Directly exercise the variant function: even with far more
        # unrecognized flags than the old exponential walk could tolerate,
        # the number of returned variants must stay small.
        argv = ["gcloud", "run", "services"]
        for i in range(50):
            argv += [f"--unknown{i}", f"v{i}"]
        argv += ["describe", "s"]
        variants = guard._gcloud_command_path_variants(argv)
        assert len(variants) <= guard._MAX_PATH_VARIANTS + 2

    def test_extreme_unknown_flag_count_fails_closed_not_open(self):
        # Past the variant cap, a `run` command must never be silently
        # ALLOWED just because enumeration gave up -- it denies as
        # ambiguous instead (never a timeout, never a silent allow).
        argv = ["gcloud", "run", "services"]
        for i in range(80):
            argv += [f"--unknown{i}", f"v{i}"]
        argv += ["describe", "s"]
        block, reason = guard._evaluate_gcloud_argv(argv)
        assert block is True
        assert reason == "run-path-too-ambiguous"

    def test_run_path_too_ambiguous_has_a_deny_message(self):
        msg = guard._message_for("run-path-too-ambiguous")
        assert "run-path-too-ambiguous" in msg
        assert "block_gcloud_identity" in msg


class TestB2SetRunUnsetSequenceDenies:
    """B2: a set/run/unset "clean up after debugging" pattern must still
    deny -- the gcloud call in the middle genuinely ran with the var set."""

    def test_export_then_list_then_unset_semicolon_denies(self):
        block, reason = guard.decision(
            "export CLOUDSDK_CORE_LOG_HTTP=1; gcloud run services list; unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_export_then_list_then_unset_double_amp_denies(self):
        block, reason = guard.decision(
            "export CLOUDSDK_CORE_LOG_HTTP=1 && gcloud run services list && unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_export_in_subshell_then_list_then_unset_denies(self):
        block, reason = guard.decision(
            "( export CLOUDSDK_CORE_LOG_HTTP=1 ) ; gcloud run services list ; unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_env_assignment_then_list_then_falsy_reset_denies(self):
        block, reason = guard.decision(
            "CLOUDSDK_CORE_LOG_HTTP=1 gcloud projects list; CLOUDSDK_CORE_LOG_HTTP=false"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_format_env_set_run_unset_semicolon_denies(self):
        block, reason = guard.decision(
            "export CLOUDSDK_CORE_FORMAT=json; gcloud run services list; unset CLOUDSDK_CORE_FORMAT"
        )
        assert block is True
        assert reason == "format-env-override"

    def test_pure_unset_before_gcloud_still_allows(self):
        # The mitigation form itself (unset BEFORE the call, nothing else
        # sets it) must still be allowed -- B2's fix must not regress this.
        block, _ = guard.decision("unset CLOUDSDK_CORE_LOG_HTTP; gcloud scheduler jobs list")
        assert block is False

    def test_env_dash_u_before_gcloud_still_allows(self):
        block, _ = guard.decision("env -u CLOUDSDK_CORE_LOG_HTTP gcloud scheduler jobs list")
        assert block is False

    def test_unset_then_real_reset_still_denies(self):
        # Unchanged existing behavior: an unset FOLLOWED BY a real
        # assignment must still deny.
        block, reason = guard.decision(
            "unset CLOUDSDK_CORE_LOG_HTTP; CLOUDSDK_CORE_LOG_HTTP=1; gcloud scheduler jobs list"
        )
        assert block is True
        assert reason == "log-http-leaks-response"


class TestB3InterpreterSpellings:
    """B3: common shell-interpreter spellings for running a command string
    must all be recognized, not just a bare `bash -c`."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "bash -lc 'gcloud run services describe s'",
            "bash -ec 'gcloud run services describe s'",
            "bash -euxc 'gcloud run services describe s'",
            "sh -ec 'gcloud run services describe s'",
        ],
    )
    def test_clustered_short_options_extract_command_string(self, cmd):
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_dash_c_double_dash_extracts_the_real_command_not_the_dashes(self):
        block, reason = guard.decision("bash -c -- 'gcloud run services describe s'")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_here_string_double_angle_triple_extracts_command(self):
        block, reason = guard.decision("bash <<< 'gcloud run services describe s'")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_here_string_double_quoted_extracts_command(self):
        block, reason = guard.decision('bash <<< "gcloud run services describe s"')
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_here_string_no_space_before_quote_extracts_command(self):
        # shlex has no special <<< handling and glues a no-space `<<<'...'`
        # into ONE token (`<<<gcloud run services describe s`) -- this shape
        # must still be recognized (found via the reviewer's c3.txt repro).
        block, reason = guard.decision("bash <<<'gcloud run services describe s'")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_here_string_no_space_safe_command_still_allows(self):
        block, _ = guard.decision("bash <<<'gcloud auth list'")
        assert block is False

    @pytest.mark.parametrize("interp", ["dash", "ksh", "mksh", "fish", "csh", "tcsh"])
    def test_additional_interpreters_recognized(self, interp):
        block, reason = guard.decision(f"{interp} -c 'gcloud run services describe s'")
        assert block is True
        assert reason == "describe-unmasked-format"

    @pytest.mark.parametrize(
        "cmd",
        [
            "bash -lc 'gcloud scheduler jobs list'",
            "bash <<< 'gcloud scheduler jobs list'",
            "dash -c 'gcloud scheduler jobs list'",
        ],
    )
    def test_safe_command_via_new_interpreter_spelling_still_allows(self, cmd):
        block, _ = guard.decision(cmd)
        assert block is False

    def test_dash_c_identity_mutation_via_clustered_options_denies(self):
        block, reason = guard.decision("bash -lc 'gcloud config set account other@example.com'")
        assert block is True
        assert reason == "config-set-account"

    def test_nested_command_substitution_inside_dash_c_body_fails_closed(self):
        # A -c body whose OWN $(...) mentions gcloud must fail closed.
        block, reason = guard.decision("bash -c 'echo $(gcloud run services describe s)'")
        assert block is True

    def test_first_non_option_arg_skips_o_optname_pair(self):
        assert guard._first_non_option_arg(["-o", "pipefail", "cmd string"], 0) == "cmd string"

    def test_first_non_option_arg_skips_double_dash(self):
        assert guard._first_non_option_arg(["--", "cmd string"], 0) == "cmd string"

    def test_first_non_option_arg_returns_none_when_exhausted(self):
        assert guard._first_non_option_arg(["-o", "pipefail"], 0) is None


class TestP2OneQuotedRegionsAndLiteralHeredocsSkipped:
    """P2-1: a `$(...)`/backtick found only inside a single-quoted region,
    or inside a literal (quoted-delimiter) heredoc body NOT fed to an
    interpreter, must never be treated as a real nested gcloud invocation."""

    def test_gh_issue_comment_heredoc_idiom_allows(self):
        cmd = (
            "gh issue comment 5890 --body \"$(cat <<'EOF'\n"
            "some text with `gcloud run services describe s` inline\n"
            "EOF\n)\""
        )
        block, reason = guard.decision(cmd)
        assert block is False
        assert reason == "no-gcloud-identity-mutation"

    def test_git_commit_dash_F_heredoc_idiom_allows(self):
        cmd = "git commit -F - <<'EOF'\nfixed `gcloud run services describe s` handling\nEOF"
        block, _ = guard.decision(cmd)
        assert block is False

    def test_cat_redirect_heredoc_allows(self):
        cmd = "cat > msg <<'EOF'\nsee `gcloud run services describe s`\nEOF"
        block, _ = guard.decision(cmd)
        assert block is False

    def test_printf_single_quoted_dollar_paren_allows(self):
        block, _ = guard.decision("printf '...$(gcloud run services describe s)...'")
        assert block is False

    def test_grep_single_quoted_dollar_paren_allows(self):
        block, _ = guard.decision("grep '$(gcloud run services describe' docs/")
        assert block is False

    def test_double_quoted_substitution_still_denies(self):
        # Regression guard: double quotes must still be scanned.
        block, reason = guard.decision('echo "$(gcloud scheduler jobs describe j)"')
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_top_level_backtick_still_denies(self):
        block, reason = guard.decision("echo `gcloud scheduler jobs describe j`")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_unquoted_heredoc_expansion_still_denies(self):
        block, reason = guard.decision("cat <<EOF\n$(gcloud scheduler jobs describe j)\nEOF")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_quoted_heredoc_fed_to_interpreter_still_denies(self):
        block, reason = guard.decision("bash <<'EOF'\ngcloud scheduler jobs describe j\nEOF")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_masked_describe_inside_double_quotes_still_allows(self):
        block, _ = guard.decision(
            "echo \"$(gcloud scheduler jobs describe j --format='value(name)')\""
        )
        assert block is False

    def test_backtick_config_set_still_denies(self):
        block, reason = guard.decision("echo `gcloud config set account x`")
        assert block is True
        assert reason == "config-set-account"

    def test_large_legitimate_heredoc_with_many_literal_shift_operators_allows(self):
        # A big commit-message-style heredoc whose OWN body text repeats
        # "<<" many times as ordinary prose must still be allowed -- this
        # is also P3-2's own quadratic-cost regression guard. Asserted on a
        # deterministic COUNT (P3-e, round 7): the heredoc is fed to `cat`,
        # not an interpreter, so `_extract_shell_heredoc_bodies` must find
        # ZERO real bodies to extract regardless of how many `<<`-shaped
        # substrings the (inert) body text itself contains -- proving the
        # scan cost is bounded by the number of REAL heredocs (one), never
        # by the number of `<<`-shaped substrings in the text (3,000).
        body = "line about gcloud auth list and x << y and $HOME\n" * 3000
        cmd = "cat > /tmp/m <<'EOF'\n" + body + "EOF"
        extracted, ambiguous = guard._extract_shell_heredoc_bodies(cmd)
        assert extracted == []
        assert ambiguous is False

        block, reason = guard.decision(cmd)
        assert block is False
        assert reason == "no-gcloud-identity-mutation"


class TestP2TwoEveryGcloudSlicEvaluated:
    """P2-2: every argv slice starting at a gcloud-shaped token must be
    evaluated, not just the first, so an earlier path/flag-value ending in
    "/gcloud" cannot hide a REAL gcloud invocation later in the same argv."""

    def test_docker_volume_mount_then_real_describe_denies(self):
        cmd = (
            "docker run -v ~/.config/gcloud:/root/.config/gcloud IMAGE "
            "gcloud run services describe s"
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_sudo_preserve_env_flag_value_then_real_config_set_denies(self):
        cmd = "sudo --preserve-env=/x/gcloud gcloud config set account x"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "config-set-account"

    def test_docker_volume_mount_with_only_safe_gcloud_call_allows(self):
        cmd = (
            "docker run -v ~/.config/gcloud:/root/.config/gcloud IMAGE "
            "gcloud auth list"
        )
        block, _ = guard.decision(cmd)
        assert block is False


class TestP2ThreePerFamilyHintForWrappedAndNestedShapes:
    """P2-3: the per-family deny-message hint must round-trip for a command
    blocked ONLY via a wrapped (shell-keyword) or nested (bash -c) shape,
    not just top-level segments."""

    def test_wrapped_group_flag_shape_resolves_a_family(self):
        family = guard._safe_family_for_command("do gcloud run jobs --region r describe j")
        assert family == "run-job"

    def test_nested_bash_c_shape_resolves_a_family(self):
        family = guard._safe_family_for_command("bash -c 'gcloud run services describe s'")
        assert family == "run-service"

    def test_wrapped_group_flag_hint_round_trips(self):
        block, reason = guard.decision("do gcloud run jobs --region r describe j")
        assert block is True
        # Applying the family's own real safe hint to the original shape
        # must now be allowed.
        hint = guard._safe_format_hint("run-job")
        fixed = f"do gcloud run jobs --region r describe j {hint}"
        fixed_block, _ = guard.decision(fixed)
        assert fixed_block is False

    def test_nested_bash_c_hint_round_trips(self):
        block, reason = guard.decision("bash -c 'gcloud run services describe s'")
        assert block is True
        hint = guard._safe_format_hint("run-service")
        fixed_cmd = f"bash -c \"gcloud run services describe s {hint}\""
        fixed_block, _ = guard.decision(fixed_cmd)
        assert fixed_block is False


class TestP3OneLogHttpAdviceIsCorrect:
    """P3-1: `--log-http` is a strict zero-argument boolean flag
    (StoreBooleanProperty, nargs=0); the real opt-out is `--no-log-http`,
    never `--log-http=false`."""

    def test_config_set_log_http_message_recommends_no_log_http(self):
        msg = guard._message_for("config-set-log-http")
        assert "--no-log-http" in msg

    def test_no_log_http_flag_is_the_working_opt_out(self):
        block, _ = guard.decision("gcloud scheduler jobs list --no-log-http")
        assert block is False

    def test_log_http_equals_false_still_harmless_not_denied(self):
        # Not the recommended form, but this gate's own defensive scoring
        # must not turn it into a false positive either (gcloud itself
        # refuses this shape before any HTTP call happens).
        block, _ = guard.decision("gcloud scheduler jobs list --log-http=false")
        assert block is False


class TestP3TwoHeredocExtractorBounded:
    """P3-2: the heredoc extractor must be bounded/linear, not quadratic.
    Asserted on deterministic COUNTS (P3-e, round 7), not wall-clock --
    each of these has a real, checkable count that a quadratic regression
    would not change (the bug was cost, not a wrong count), so a count
    assertion exercises the identical code path a timing assertion would,
    without the flakiness of a shared/loaded machine."""

    def test_many_unquoted_shift_operator_candidates_fails_closed_past_opener_cap(self):
        # None of the 3,000 `a<<bN` fragments are real heredoc openers (no
        # valid delimiter line follows any of them), so the extractor finds
        # zero BODIES -- but it must still count each one as an "opener
        # candidate" scanned (P3-b, round 7: a false opener with no
        # matching close now resumes the scan via `pos = m.end(); continue`
        # instead of `break`-ing out entirely, so it no longer silently
        # exits after the FIRST fake candidate). With 3,000 candidates and
        # only `_MAX_HEREDOC_OPENERS_SCANNED` (32) tolerated, this
        # deterministically trips the opener-count cap and fails CLOSED --
        # a real behavior change from round 6 (where the old `break`
        # accidentally kept this case fast by stopping at the first fake
        # opener, never re-examining any of the other 2,999): denying here
        # is the intended, correct consequence of no longer letting a false
        # opener silently truncate the scan.
        cmd = "echo " + " ".join(f"a<<b{i}" for i in range(3000)) + " ; gcloud auth list"
        extracted, ambiguous = guard._extract_shell_heredoc_bodies(cmd)
        assert extracted == []
        assert ambiguous is True

        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "untokenizable-segment-with-gcloud"

    def test_few_unquoted_shift_operator_candidates_under_cap_still_allows(self):
        # Well under the opener cap, a command with a handful of harmless
        # `<<`-shaped fragments must still be allowed normally.
        cmd = "echo " + " ".join(f"a<<b{i}" for i in range(5)) + " ; gcloud auth list"
        block, reason = guard.decision(cmd)
        assert block is False
        assert reason == "no-gcloud-identity-mutation"

    def test_large_heredoc_body_decision_is_deterministic(self):
        body = "line about gcloud auth list and x << y and $HOME\n" * 3000
        cmd = "cat > /tmp/m <<'EOF'\n" + body + "EOF"
        block, reason = guard.decision(cmd)
        assert block is False
        assert reason == "no-gcloud-identity-mutation"

    def test_extreme_opener_count_fails_closed_not_open(self):
        # Past the opener cap, a command that genuinely mentions gcloud
        # inside interpreter-fed heredocs must fail closed, never silently
        # allow.
        cmd = "\n".join(
            f"cat <<X{i} | bash\ngcloud auth list\nX{i}" for i in range(500)
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "untokenizable-segment-with-gcloud"

    def test_extract_shell_heredoc_bodies_never_raises_on_garbage(self):
        for bad in ("", None, 12345, []):
            out, ambiguous = guard._extract_shell_heredoc_bodies(bad)  # type: ignore[arg-type]
            assert isinstance(out, list)
            assert isinstance(ambiguous, bool)


class TestP3ThreeDocstringsAccurate:
    """P3-3: nested-extraction error handling and cross-function docstring
    claims must match actual behavior."""

    def test_decision_segments_and_nested_error_fails_closed_for_whole_command(self, monkeypatch):
        # An exception raised inside `_decision_segments_and_nested` (which
        # has no try/except of its own around its `_gcloud_segments` call,
        # or around its own recursive call) must propagate up through
        # decision()'s own OUTER try/except and fail OPEN for the WHOLE
        # command -- NOT silently degrade to (False, "") for just the
        # offending nested text the way an earlier docstring claimed. This
        # test pins the ACTUAL, verified fail-open result: block is False
        # and reason is the specific "decision-error" sentinel
        # decision()'s own except-clause returns -- not merely "some bool,
        # some string" (ROUND 8 CORRECTION, P3: a prior version of this
        # test asserted only `isinstance(block, bool)` /
        # `isinstance(reason, str)`, which is VACUOUS -- it would pass
        # whether `block` came back True or False, and that prior version
        # ALSO monkeypatched the wrong target: `_lib._split_segments` is
        # guarded by a LOCAL try/except at every one of its call sites
        # inside this module, including inside `_decision_segments_and_
        # nested` itself, so raising there never actually reached
        # decision()'s outer guard at all -- the prior test's own name and
        # comment described a fail-open that its actual monkeypatch target
        # never triggered. `_gcloud_segments` itself, by contrast, is called
        # directly with no wrapping try/except at this call site (its OWN
        # internal try/except only guards its own body, not a caller who
        # replaces the function entirely), so replacing the function itself
        # (not one of its internals) is what actually reaches the
        # uncaught-recursive-call path the docstring describes.
        def raising_gcloud_segments(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(guard, "_gcloud_segments", raising_gcloud_segments)
        block, reason = guard.decision("bash -c 'gcloud run services describe s'")
        assert block is False
        assert reason == "decision-error"

    # ROUND 8 (P3): test_mentions_gcloud_is_not_called_by_decision_segments_
    # and_nested was removed here -- it was a source-text lock-in test
    # (asserting a literal substring appears in `inspect.getsource(...)`),
    # which pins an implementation detail of HOW the docstring claim is
    # satisfied rather than testing observable BEHAVIOR. A future
    # refactor that preserves the same behavior through different code
    # (e.g. renaming the pre-check regex, or restructuring the early-exit
    # check) would fail this test despite being correct, and a change that
    # broke the actual behavior while keeping the substring present would
    # pass it despite being wrong. The behavior this was trying to protect
    # (this function never denies a command for the bare mention of
    # "gcloud" with no invocation anywhere) is already covered by the
    # module's own program-token-vs-text-mention test coverage elsewhere in
    # this file (see TestWrapperFalsePositiveDoesNotBreakUnrelatedRecoveryForms
    # and the P2-4/gap-list behavioral tests), which assert on `decision()`'s
    # actual return value, not on source text.


# ===========================================================================
# ROUND 7 (#5890, warm round-6 review of round 6): B1-r6,
# P2-a, P2-b, P3-a, P3-b, P3-c, P3-d, P3-e. FALSIFIABILITY: each fix below
# was confirmed to go RED against the round-6 snapshot
# (`r6/block_gcloud_identity.py.r6`) and GREEN against this round's fix, by
# hand, outside this file, mirroring this file's own documented
# falsifiability convention.
# ===========================================================================


class TestB1r6OrdinaryRunVerbsNeverDenied:
    """B1-r6: an ordinary, non-describe/list `run` command (`update`,
    `update-traffic`, `execute`, `create`, `deploy`) must never be denied as
    `run-path-too-ambiguous` regardless of how many real, space-separated
    flags it carries -- the round-6 fix's own variant cap wrongly treated
    "starts with run and contains a covered keyword token" as ambiguous
    even when the path had ALREADY diverged from every covered group."""

    @pytest.mark.parametrize(
        "verb_and_id",
        [
            "services update api",
            "jobs update myjob",
            "services update-traffic api",
            "worker-pools update w",
        ],
    )
    def test_twenty_plus_unknown_space_separated_flags_allowed(self, verb_and_id):
        pairs = [
            ("--memory", "1Gi"), ("--cpu", "2"), ("--min-instances", "1"),
            ("--max-instances", "10"), ("--concurrency", "80"), ("--timeout", "300"),
            ("--service-account", "sa@p.iam"), ("--set-env-vars", "A=1"),
            ("--vpc-connector", "c"), ("--vpc-egress", "all-traffic"), ("--ingress", "all"),
            ("--execution-environment", "gen2"), ("--labels", "a=b"), ("--tag", "t"),
            ("--add-cloudsql-instances", "p:r:i"), ("--set-secrets", "K=k:latest"),
            ("--description", "svc"), ("--no-traffic", None), ("--async", None),
            ("--revision-suffix", "v2"), ("--clear-labels", None),
        ]
        toks = []
        for f, v in pairs:
            toks.append(f)
            if v:
                toks.append(v)
        cmd = f"gcloud run {verb_and_id} --region us-central1 " + " ".join(toks)
        block, reason = guard.decision(cmd)
        assert block is False, f"wrongly denied ({reason}): {cmd[:120]}"

    def test_jobs_execute_with_twelve_flags_allowed(self):
        flags = " ".join(f"--f{i} v{i}" for i in range(12))
        block, reason = guard.decision(f"gcloud run jobs execute j --region r {flags}")
        assert block is False, reason

    def test_services_list_with_twelve_flags_and_masked_format_allowed(self):
        flags = " ".join(f"--f{i} v{i}" for i in range(12))
        block, reason = guard.decision(
            f"gcloud run services describe s --format='value(status.url)' {flags}"
        )
        assert block is False, reason

    def test_services_list_with_twelve_unknown_flags_and_no_format_allowed(self):
        # list's own default is already safe (a summary table); many
        # unrecognized flags must not turn that into a deny.
        flags = " ".join(f"--f{i} v{i}" for i in range(12))
        block, reason = guard.decision(f"gcloud run services list {flags}")
        assert block is False, reason

    def test_group_flag_describe_still_denied(self):
        # The B1 (round 4) group-level-flag-before-the-verb fix must still
        # work -- B1-r6 must not have narrowed coverage of a REAL
        # describe/list ambiguity, only the FALSE one.
        block, reason = guard.decision("gcloud run services --region us-central1 describe s")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_unmasked_describe_with_many_unknown_flags_still_denied(self):
        # A genuinely unmasked describe must still deny even with many
        # extra unknown flags -- B1-r6 only stops PATH ambiguity from
        # causing a false deny, it must never suppress a real one.
        flags = " ".join(f"--f{i} v{i}" for i in range(12))
        block, reason = guard.decision(f"gcloud run services describe s {flags}")
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_recovery_pair_ambiguous_describe_eq_spelled_gets_normal_verdict(self):
        # RECOVERY PAIR: construct a command that is STILL genuinely
        # ambiguous under B1-r6's own narrower rule (every unrecognized
        # flag's VALUE is itself a plausible group keyword, so many
        # branches all remain plausible simultaneously) -- confirm it
        # denies as run-path-too-ambiguous, then confirm the SAME command
        # with every flag re-spelled as --flag=value clears the ambiguity
        # and gets the ordinary masked-format verdict.
        vals = ["services", "jobs", "revisions", "worker-pools", "configurations", "describe", "list"]
        space_flags = " ".join(f"--unk{i} {vals[i % len(vals)]}" for i in range(60))
        ambiguous_cmd = f"gcloud run {space_flags}"
        block, reason = guard.decision(ambiguous_cmd)
        assert block is True
        assert reason == "run-path-too-ambiguous"

        eq_flags = " ".join(f"--unk{i}={vals[i % len(vals)]}" for i in range(60))
        eq_cmd = f"gcloud run {eq_flags}"
        eq_block, eq_reason = guard.decision(eq_cmd)
        assert eq_block is False
        assert eq_reason == "no-gcloud-identity-mutation"

    def test_run_path_too_ambiguous_message_recommends_eq_spelling(self):
        msg = guard._message_for("run-path-too-ambiguous")
        assert "--flag=value" in msg or "flag=value" in msg

    def test_is_plausible_run_group_prefix_never_raises_on_garbage(self):
        for bad in ((), None, 12345, []):
            try:
                guard._is_plausible_run_group_prefix(bad)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"raised on {bad!r}: {exc!r}")


class TestP2aQuotedHeredocInsideSubstitutionApostrophe:
    """P2-a: a `$(...)` substitution whose OWN inner text contains a
    quoted-delimiter heredoc body (not fed to an interpreter) must not have
    that body's own apostrophes/quotes corrupt the outer `$(...)` depth
    walk's quote-tracking state."""

    def test_gh_issue_comment_apostrophe_in_heredoc_body_allows(self):
        cmd = (
            "gh issue comment 5890 --body \"$(cat <<'EOF'\n"
            "It's fixed: the gcloud gate now needs a masked --format.\n"
            "EOF\n)\""
        )
        block, reason = guard.decision(cmd)
        assert block is False
        assert reason == "no-gcloud-identity-mutation"

    def test_gh_issue_comment_apostrophe_and_backtick_mention_allows(self):
        cmd = (
            "gh issue comment 5890 --body \"$(cat <<'EOF'\n"
            "It's fixed: `gcloud run services describe s` now needs a masked --format.\n"
            "EOF\n)\""
        )
        block, _ = guard.decision(cmd)
        assert block is False

    def test_dollar_paren_inside_unquoted_heredoc_still_denies(self):
        # Regression guard: an UNQUOTED-delimiter heredoc still performs
        # real substitution inside its own body -- this must still deny.
        cmd = "cat <<EOF\n$(gcloud scheduler jobs describe j)\nEOF"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_real_dollar_paren_describe_inside_double_quotes_still_denies(self):
        block, reason = guard.decision('echo "$(gcloud scheduler jobs describe j)"')
        assert block is True
        assert reason == "describe-unmasked-format"


class TestP2bEnvVarAssignmentRemovalBothDirections:
    """P2-b: `_env_var_assignment_or_removal_is_active` must match its own
    docstring in BOTH directions: a falsy assignment alone is safe, and any
    occurrence not covered by a recognized assignment/removal is truthy."""

    def test_falsy_env_prefix_assignment_allows(self):
        block, reason = guard.decision("CLOUDSDK_CORE_LOG_HTTP=0 gcloud projects list")
        assert block is False
        assert reason == "no-gcloud-identity-mutation"

    def test_falsy_export_assignment_allows(self):
        block, _ = guard.decision("export CLOUDSDK_CORE_LOG_HTTP=0; gcloud projects list")
        assert block is False

    def test_falsy_string_false_export_assignment_allows(self):
        block, _ = guard.decision("export CLOUDSDK_CORE_LOG_HTTP=false; gcloud projects list")
        assert block is False

    def test_bare_export_then_unset_still_denies(self):
        # A bare `export VAR` (no `=`) does not clear the var to any known
        # value -- it is an unrecognized shape and must be treated as
        # truthy, even when followed by an `unset`.
        block, reason = guard.decision(
            "export CLOUDSDK_CORE_LOG_HTTP; gcloud projects list; unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_read_heredoc_assignment_then_unset_still_denies(self):
        block, reason = guard.decision(
            "read CLOUDSDK_CORE_LOG_HTTP <<< 1; export CLOUDSDK_CORE_LOG_HTTP; "
            "gcloud projects list; unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_parameter_expansion_default_assignment_then_unset_still_denies(self):
        block, reason = guard.decision(
            ": ${CLOUDSDK_CORE_LOG_HTTP:=1}; export CLOUDSDK_CORE_LOG_HTTP; "
            "gcloud projects list; unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_pure_unset_alone_still_allows(self):
        block, _ = guard.decision("unset CLOUDSDK_CORE_LOG_HTTP; gcloud projects list")
        assert block is False

    def test_env_dash_u_alone_still_allows(self):
        block, _ = guard.decision("env -u CLOUDSDK_CORE_LOG_HTTP gcloud projects list")
        assert block is False

    def test_truthy_assignment_then_unset_still_denies(self):
        # Every occurrence must be safe -- one truthy occurrence anywhere
        # (even alongside an unset) still denies (B2, round 6 -- must not
        # regress).
        block, reason = guard.decision(
            "export CLOUDSDK_CORE_LOG_HTTP=1; gcloud run services list; "
            "unset CLOUDSDK_CORE_LOG_HTTP"
        )
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_falsy_format_env_assignment_allows(self):
        block, _ = guard.decision("export CLOUDSDK_CORE_FORMAT=0; gcloud run services list")
        assert block is False

    def test_env_var_assignment_or_removal_is_active_never_raises_on_garbage(self):
        for bad in (None, 12345, []):
            try:
                guard._env_var_assignment_or_removal_is_active(bad, "CLOUDSDK_CORE_LOG_HTTP")  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"raised on {bad!r}: {exc!r}")


class TestP3aSliceCapFailsClosed:
    """P3-a: hitting `_MAX_GCLOUD_SLICES` must deny outright, never evaluate
    only the first N slices as if nothing else existed."""

    def test_twenty_docker_mounts_then_real_describe_denies(self):
        vols = " ".join(f"-v /h{i}/gcloud:/c{i}/gcloud" for i in range(20))
        cmd = f"docker run {vols} img gcloud run services describe s"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "untokenizable-segment-with-gcloud"

    def test_twenty_docker_mounts_then_identity_mutation_denies(self):
        vols = " ".join(f"-v /h{i}/gcloud:/c{i}/gcloud" for i in range(20))
        cmd = f"docker run {vols} img gcloud config set account x"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "untokenizable-segment-with-gcloud"

    def test_few_gcloud_shaped_tokens_still_evaluates_normally(self):
        # Regression guard: well under the cap, normal evaluation proceeds.
        cmd = "docker run -v ~/.config/gcloud:/root/.config/gcloud img gcloud auth list"
        block, _ = guard.decision(cmd)
        assert block is False

    def test_find_all_gcloud_argv_slices_never_raises_on_garbage(self):
        for bad in (None, 12345, [1, 2, 3]):
            try:
                slices, truncated = guard._find_all_gcloud_argv_slices(bad)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"raised on {bad!r}: {exc!r}")
                continue
            assert isinstance(slices, list)
            assert isinstance(truncated, bool)


class TestP3bFalseHeredocOpenerDoesNotEndTheScan:
    """P3-b: a false `<<`-shaped opener with no matching close (and not fed
    to an interpreter) must not end the WHOLE scan -- a later, genuinely
    dangerous heredoc after it must still be examined."""

    def test_arithmetic_shift_then_piped_describe_denies(self):
        cmd = "echo $((1<<b))\ncat <<'EOF' | bash\ngcloud run services describe s\nEOF"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_piped_describe_alone_still_denies(self):
        cmd = "cat <<'EOF' | bash\ngcloud run services describe s\nEOF"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"


class TestP3cSpanScanIsBoundedByCharacterNotSpanCount:
    """P3-c: the substitution scanner's span-membership check must cost
    O(log spans) per queried position (round 8: bisect over pre-sorted
    starts), not O(spans) per position -- so total scan cost does not
    multiply span count by text length."""

    def test_span_end_if_in_any_returns_end_when_covered(self):
        sorted_spans, starts = guard._sorted_spans_with_starts([(0, 10), (20, 30)])
        assert guard._span_end_if_in_any(5, sorted_spans, starts) == 10

    def test_span_end_if_in_any_returns_none_when_not_covered(self):
        sorted_spans, starts = guard._sorted_spans_with_starts([(0, 10), (20, 30)])
        assert guard._span_end_if_in_any(15, sorted_spans, starts) is None

    def test_span_end_if_in_any_never_raises_on_garbage(self):
        assert guard._span_end_if_in_any(0, [], None) is None  # type: ignore[arg-type]

    def test_sorted_spans_with_starts_sorts_by_start(self):
        sorted_spans, starts = guard._sorted_spans_with_starts([(20, 30), (0, 10), (5, 8)])
        assert starts == [0, 5, 20]
        assert sorted_spans == [(0, 10), (5, 8), (20, 30)]

    def test_two_thousand_quoted_paths_commit_decision_is_deterministic(self):
        # Not a timing assertion (P3-e) -- exercises the same code path the
        # reviewer's perf6.py measured (1.30s pre-fix on their machine), but
        # asserted only on the correct, deterministic verdict. Runtime is
        # covered separately by the orchestrator's own perf script, not by
        # this suite.
        paths = " ".join(f"'src/module_{i}/file_{i}.py'" for i in range(2000))
        cmd = f"git commit -F /tmp/msg -- 'hooks/block_gcloud_identity.py' {paths}"
        block, reason = guard.decision(cmd)
        assert block is False
        assert reason == "no-gcloud-identity-mutation"

    def test_span_membership_cost_is_bounded_not_linear_in_span_count(self):
        # ROUND 8 (P3): a genuine, deterministic COUNT-based proxy for the
        # O(len*spans) vs O(len*log(spans)) distinction -- not wall-clock
        # (P3-e). Each span's start/end int is wrapped so every `<=`/`<`
        # comparison against a scanned position increments a shared
        # counter; the total comparison count across a long command with
        # many spans must stay within a bound that scales with
        # log(span_count) per queried position, not with span_count itself
        # (a plain-list `+` concatenation of a counting-LIST subclass loses
        # the subclass, which is why this counts COMPARISONS on the span
        # VALUES themselves rather than list access -- verified this
        # actually discriminates the three implementations before relying
        # on it: measured 1,872,540 comparisons on r6, 630,750 on r7's real
        # implementation, 12,066 on this round's fix, for the identical
        # 500-span input against a 25,000 bound).
        import unittest.mock as mock

        class _CountingInt(int):
            def __le__(self, other):
                _CountingInt._n += 1
                return int.__le__(self, other)

            def __lt__(self, other):
                _CountingInt._n += 1
                return int.__lt__(self, other)

            _n = 0

        n_spans = 500
        # Many short single-quoted spans spread across a long text, so most
        # queried positions are OUTSIDE any span -- the case where an
        # O(len*spans) scan actually bites (most work is "not found").
        paths = " ".join(f"'p{i}'" for i in range(n_spans))
        cmd = f"grep -rn x {paths}"

        real_spans = guard._single_quoted_spans(cmd)
        assert len(real_spans) == n_spans
        wrapped_spans = [(_CountingInt(s), _CountingInt(e)) for s, e in real_spans]

        with mock.patch.object(guard, "_single_quoted_spans", return_value=wrapped_spans):
            guard._extract_command_substitutions(cmd)

        assert _CountingInt._n < 50 * n_spans, (
            f"comparisons={_CountingInt._n} for {n_spans} spans -- "
            "span-membership check is not bounded"
        )


# ===========================================================================
# ROUND 8 (#5890, cold trust-architect review of E7): B1-r7
# (a real REGRESSION from round 7's own B1-r6 fix), B2 (the quote-span scan),
# plus P3 cheap fixes. FALSIFIABILITY: each fix below was confirmed to go RED
# against the round-7 snapshot (`r7/block_gcloud_identity.py.r7`) and GREEN
# against this round's fix, by hand, outside this file, mirroring this
# file's own documented falsifiability convention.
# ===========================================================================


class TestB1r7AlphaBetaTrackPrefixStrippedBeforePlausibilityCheck:
    """B1-r7: `_is_plausible_run_group_prefix` must strip a leading
    alpha/beta release-track element before checking plausibility -- the
    round-7 branching walk never stripped it anywhere, so `gcloud beta run
    services --region ... describe ...` (and every alpha/beta-prefixed
    group-flag describe/list) was judged implausible on its very first
    token ("beta"/"alpha" != "run") and silently ALLOWED, a real regression
    from round 6, which had no such gap."""

    _TRACKS = ["", "alpha", "beta"]
    _FLAG_STYLES = [
        ("known", "--region us-central1"),
        ("unknown", "--foo bar"),
    ]
    _VERB_SHAPES = [
        ("services_describe", "services", "describe svc", "run-service"),
        ("jobs_describe", "jobs", "describe j", "run-job"),
        ("services_list_json", "services", "list --format=json", "run-service"),
    ]

    @pytest.mark.parametrize("track", _TRACKS)
    @pytest.mark.parametrize("flag_style_name,flag_style", _FLAG_STYLES)
    @pytest.mark.parametrize("verb_name,resource,verb_tail,family", _VERB_SHAPES)
    def test_cross_product_all_deny(self, track, flag_style_name, flag_style, verb_name, resource, verb_tail, family):
        track_tok = f"{track} " if track else ""
        cmd = f"gcloud {track_tok}run {resource} {flag_style} {verb_tail}"
        block, reason = guard.decision(cmd)
        assert block is True, f"wrongly allowed: {cmd!r}"
        assert reason in ("describe-unmasked-format", "list-unmasked-format"), (
            f"wrong reason {reason!r} for {cmd!r}"
        )

    @pytest.mark.parametrize("track", _TRACKS)
    @pytest.mark.parametrize("flag_style_name,flag_style", _FLAG_STYLES)
    @pytest.mark.parametrize("verb_name,resource,verb_tail,family", _VERB_SHAPES)
    def test_cross_product_masked_recovery_pair_allows(
        self, track, flag_style_name, flag_style, verb_name, resource, verb_tail, family
    ):
        # RECOVERY PAIR: the identical shape, masked with the family's own
        # real safe --format hint, must allow.
        track_tok = f"{track} " if track else ""
        hint = guard._safe_format_hint(family)
        if "--format=json" in verb_tail:
            verb_tail = verb_tail.replace("--format=json", hint)
        else:
            verb_tail = f"{verb_tail} {hint}"
        cmd = f"gcloud {track_tok}run {resource} {flag_style} {verb_tail}"
        block, _ = guard.decision(cmd)
        assert block is False, f"masked form wrongly denied: {cmd!r}"

    def test_reviewer_exact_repro_cases_all_deny(self):
        cases = [
            "gcloud run services --region us-central1 describe svc",
            "gcloud beta run services --region us-central1 describe svc",
            "gcloud alpha run services --region us-central1 describe svc",
            "gcloud beta run jobs --region r describe j",
            "gcloud alpha run services --region us-central1 list --format=json",
            "gcloud beta run services describe svc",
            "gcloud --quiet beta run services --platform managed describe svc",
            "gcloud beta run services --foo bar describe svc",
            "gcloud run services --foo bar describe svc",
        ]
        for c in cases:
            block, _ = guard.decision(c)
            assert block is True, f"wrongly allowed: {c!r}"

    def test_ordinary_alpha_beta_prefixed_non_describe_list_still_allows(self):
        # Regression guard: B1-r6's own fix (ordinary run verbs never deny
        # regardless of flag count) must still hold for alpha/beta-prefixed
        # commands too.
        cases = [
            "gcloud beta run services update api --region us-central1 --memory 1Gi --cpu 2",
            "gcloud alpha run jobs update myjob --region us-central1 --memory 1Gi",
        ]
        for c in cases:
            block, _ = guard.decision(c)
            assert block is False, f"wrongly denied: {c!r}"

    def test_is_plausible_run_group_prefix_strips_track_prefix(self):
        assert guard._is_plausible_run_group_prefix(("beta", "run")) is True
        assert guard._is_plausible_run_group_prefix(("alpha", "run")) is True
        assert guard._is_plausible_run_group_prefix(("beta", "run", "services", "describe")) is True
        assert guard._is_plausible_run_group_prefix(("beta", "run", "deploy")) is False


class TestB2SingleQuotedSpansHeredocAndEscapeAware:
    """B2: `_single_quoted_spans` must skip heredoc bodies (any delimiter
    kind), honor backslash escapes outside quotes, and fail CLOSED (skip
    NOTHING) on an unterminated span -- the round-6/7 version had none of
    these, so a prose apostrophe in ANY heredoc body opened a false
    single-quoted region that ran to end-of-text, hiding every later real
    substitution from `_extract_command_substitutions`."""

    def test_repro_1_notes_heredoc_then_config_set_account_denies(self):
        cmd = (
            "cat > /tmp/notes.md <<'EOF'\nIt's the deploy note\nEOF\n"
            'X="$(gcloud config set account other@x.com)"'
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "config-set-account"

    def test_repro_2_notes_heredoc_then_describe_json_denies(self):
        cmd = (
            "cat > /tmp/notes.md <<'EOF'\nIt's the deploy note\nEOF\n"
            'SVC_JSON="$(gcloud run services describe api --format=json)"'
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_repro_3_git_commit_heredoc_dont_then_describe_json_denies(self):
        cmd = (
            "git commit -F - -- a.py <<'EOF'\nfix: don't leak\nEOF\n"
            'JSON="$(gcloud run services describe api --format=json)"'
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_repro_4_log_http_env_then_heredoc_then_projects_list_denies(self):
        cmd = (
            "export CLOUDSDK_CORE_LOG_HTTP=1\ncat > n.md <<'EOF'\nit's\nEOF\n"
            'OUT="$(gcloud projects list)"'
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "log-http-leaks-response"

    def test_repro_5_even_apostrophe_count_still_denies(self):
        cmd = (
            "cat > /tmp/notes.md <<'EOF'\nIt's the deploy note\nEOF\n"
            "gcloud run services list --format='value(metadata.name)'; "
            'J="$(gcloud run services describe api)"'
        )
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_repro_6_escaped_apostrophe_then_describe_denies(self):
        cmd = "echo don\\'t; URL=\"$(gcloud run services describe api)\""
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "describe-unmasked-format"

    def test_recovery_gh_comment_heredoc_idiom_still_allows(self):
        cmd = (
            "gh issue comment 5890 --body \"$(cat <<'EOF'\n"
            "It's fixed: the gcloud gate now needs a masked --format.\n"
            "EOF\n)\""
        )
        block, _ = guard.decision(cmd)
        assert block is False

    def test_recovery_git_commit_dash_F_heredoc_still_allows(self):
        cmd = "git commit -F - <<'EOF'\nfixed `gcloud run services describe s` handling\nEOF"
        block, _ = guard.decision(cmd)
        assert block is False

    def test_recovery_grep_single_quoted_dollar_paren_still_allows(self):
        block, _ = guard.decision("grep '$(gcloud run services describe' docs/")
        assert block is False

    def test_single_quoted_spans_skips_heredoc_body_apostrophe(self):
        text = "cat <<'EOF'\nIt's the note\nEOF\necho 'real'"
        spans = guard._single_quoted_spans(text)
        # The only real single-quoted spans are the heredoc's own 'EOF'
        # delimiter and the final echo 'real' -- never anything inside the
        # heredoc BODY.
        body_start = text.index("It's")
        body_end = text.index("\nEOF")
        for start, end in spans:
            assert not (body_start <= start < body_end), (
                f"span {(start, end)} starts inside the heredoc body"
            )

    def test_single_quoted_spans_honors_backslash_escape_outside_quotes(self):
        text = "echo don\\'t x"
        spans = guard._single_quoted_spans(text)
        assert spans == []

    def test_single_quoted_spans_fails_closed_on_unterminated_quote(self):
        text = "echo 'unterminated"
        assert guard._single_quoted_spans(text) == []

    def test_single_quoted_spans_still_finds_real_quotes(self):
        text = "echo 'a' 'b'"
        spans = guard._single_quoted_spans(text)
        assert len(spans) == 2

    def test_all_heredoc_body_spans_covers_unquoted_delimiter_too(self):
        text = "cat <<EOF\nIt's\nEOF"
        spans = guard._all_heredoc_body_spans(text)
        assert len(spans) == 1
        start, end = spans[0]
        assert text[start:end] == "It's\n"

    def test_single_quoted_spans_never_raises_on_garbage(self):
        for bad in (None, 12345, []):
            try:
                guard._single_quoted_spans(bad)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"raised on {bad!r}: {exc!r}")

    def test_all_heredoc_body_spans_never_raises_on_garbage(self):
        for bad in (None, 12345, []):
            try:
                guard._all_heredoc_body_spans(bad)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover
                pytest.fail(f"raised on {bad!r}: {exc!r}")


class TestP3UntokenizableMessageGivesAccurateAdvice:
    """P3: the `untokenizable-segment-with-gcloud` message must not claim
    every cause is a balanced-quoting problem -- it also covers the slice
    cap, heredoc-opener cap, depth cap, and substitution-ambiguity cases."""

    def test_message_covers_multiple_causes(self):
        msg = guard._message_for("untokenizable-segment-with-gcloud")
        assert "gcloud-shaped tokens" in msg or "Docker" in msg
        assert "heredoc" in msg.lower()
        assert "balanced quotes" in msg

    def test_slice_cap_case_still_denies_with_this_reason(self):
        vols = " ".join(f"-v /h{i}/gcloud:/c{i}/gcloud" for i in range(20))
        cmd = f"docker run {vols} img gcloud run services describe s"
        block, reason = guard.decision(cmd)
        assert block is True
        assert reason == "untokenizable-segment-with-gcloud"


class TestP3StaleCommentsCorrected:
    """P3: stale comments describing retired behavior must match the
    actual, current code."""

    def test_env_var_check_comment_no_longer_claims_last_occurrence_wins(self):
        # The stale phrase may still appear as part of the ROUND-8
        # correction's own explanation of what changed (a historical
        # reference), but the comment must no longer ASSERT it as the
        # function's current behavior -- checked here by confirming the
        # corrected, accurate description of the actual current rule is
        # present instead.
        import inspect

        src = inspect.getsource(guard.decision)
        assert "STALE COMMENT FIXED" in src
        assert "truthy if ANY occurrence" in src

    def test_gcloud_segments_docstring_no_longer_claims_fixed_wrapper_walk(self):
        import inspect

        src = inspect.getsource(guard._gcloud_segments)
        assert "walk past any leading env-assignment" not in src
