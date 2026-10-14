"""Regenerate ``whatwg_url_fixture.json`` — WHATWG ground truth for a fixed
URL-spelling matrix, computed by shelling out to Node's real ``URL`` parser
ONCE, so the pytest suite itself never requires node at run time (it only
reads the cached JSON file this script writes).

Fix-round-7 (2026-09-11): this fixture backs the backslash/whitespace/
control-char divergence class between Python's ``urlsplit`` and a WHATWG/
Chromium URL parser (see ``block_prod_mutations.py``'s WHATWG section). Each
entry is ``{raw, host, pathname, port, ok}`` (or ``{raw, ok: false, error}``
for an input Node's parser rejects outright).

Regenerate with: ``python3 hooks/tests/whatwg_url_fixture.py``
(requires ``node`` on PATH; the test suite does not). Diff the result
against the checked-in fixture before trusting a change — a real fixture
drift (Node/V8's URL parser behavior changing across versions) is a signal
this module's own pre-normalization rules may need a matching update, not
something to regenerate-and-forget.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE_PATH = os.path.join(_HERE, "whatwg_url_fixture.json")

# The fixed spelling matrix. Kept in sync with the generator's own inline
# list (this Python copy is authoritative for what the fixture SHOULD
# contain; the .js generator historically ran once by hand — this function
# is the reproducible, checked-in equivalent so `git diff` on a regenerate
# is meaningful).
URLS: list[str] = [
    "https://admin-staging.example.com\\api\\x",
    "https://admin-staging.example.com:443\\api\\x",
    "https://admin-staging.example.com/api\\x",
    "https://admin-staging.example.com\\/api/x",
    "https://admin-sta\tging.example.com/api/x",
    "https://admin-staging.example.com/ap\ti/x",
    "https://admin-staging.example.com/api/x\n",
    "https://admin-staging.example.com/a\rpi/x",
    "https://admin-staging.example.com/api\n/x",
    "   https://admin-staging.example.com/api/x",
    "https://admin-staging.example.com/api/x   ",
    "\x01https://admin-staging.example.com/api/x",
    "HTTPS://ADMIN-STAGING.EXAMPLE.COM/API/X",
    "https://admin-staging.example.com:8443/api/x",
    "https://admin-staging.example.com//api/x",
    "https://admin-staging.example.com/./api/x",
    "https://admin-staging.example.com/a/../api/x",
    "https://admin-staging.example.com/%61pi/x",
    "https://admin-staging.example.com/api/v1%2f..%2f..%2fout",
    "https://admin-staging.example.com/health",
    "https://admin-staging.example.com/health/",
    "https://admin-staging.example.com/health?x=1",
    # --- Fix-round-8 (2026-09-11): C0-control/DEL axis, representative
    # entries per position -- the fix-round-8 dispatch's own live-hook-
    # confirmed repro is the PORT entry below (0x1f in port position used to
    # ALLOW a POST it should have denied). The existing "\x01https://..."
    # entry above already covers a LEADING control character (stripped by
    # WHATWG's own leading-C0-or-space trim); these add HOST, PORT (the
    # actual gap), PATH, QUERY, and FRAGMENT positions, plus 0x7F DEL and a
    # TRAILING control character, none of which this fixture covered before.
    "https://admin\x01-staging.example.com/api/x",  # host, mid-string
    "https://admin-staging.example.com:\x1f8443/api/x",  # port -- the repro axis
    "https://admin-staging.example.com:\x00443/api/x",  # port, NUL
    "https://admin-staging.example.com/api\x1f/x",  # path
    "https://admin-staging.example.com/api/x?q=\x1f1",  # query
    "https://admin-staging.example.com/api/x#\x1ffrag",  # fragment
    "https://admin-staging.example.com/api/x\x7f",  # trailing, DEL
    "https://admin\x7f-staging.example.com/api/x",  # host, DEL
    # --- Fix-round-15 (2026-09-12): duplicate-slash + dot-segment axis --
    # the round-8 review BLOCKER's own repro class. WHATWG pops the EMPTY
    # segment a "//" produces when a following ".." resolves against it
    # (`/admin//..` -> `/admin/`), never the real preceding segment the way
    # posixpath.normpath's POSIX-style collapse-then-resolve order would.
    "https://admin-staging.example.com/admin//..",
    "https://admin-staging.example.com/api//..",
    "https://admin-staging.example.com/a/../admin/x",
    "https://admin-staging.example.com/admin/./x",
    "https://admin-staging.example.com/admin/x/..",
]

_NODE_SCRIPT = r"""
const fs = require('fs');
const urls = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
const out = [];
for (const raw of urls) {
  let entry = { raw };
  try {
    const u = new URL(raw);
    entry.host = u.hostname;
    entry.pathname = u.pathname;
    entry.port = u.port;
    entry.ok = true;
  } catch (e) {
    entry.ok = false;
    entry.error = e.message;
  }
  out.push(entry);
}
process.stdout.write(JSON.stringify(out, null, 2) + "\n");
"""


def regenerate() -> list[dict]:
    """Shell out to node once, return the parsed fixture list. Raises
    RuntimeError with a clear message if node is unavailable."""
    node = shutil.which("node")
    if not node:
        raise RuntimeError(
            "whatwg_url_fixture.regenerate(): 'node' not found on PATH — "
            "this fixture can only be REGENERATED with node available; "
            "reading the already-checked-in JSON file does not need it."
        )
    urls_json = os.path.join(_HERE, "_whatwg_fixture_urls.tmp.json")
    with open(urls_json, "w", encoding="utf-8") as fh:
        json.dump(URLS, fh)
    try:
        proc = subprocess.run(
            [node, "-e", _NODE_SCRIPT, urls_json],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    finally:
        try:
            os.unlink(urls_json)
        except OSError:
            pass
    return json.loads(proc.stdout)


def load_fixture() -> list[dict]:
    """Read the checked-in fixture file (no node required)."""
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


if __name__ == "__main__":
    data = regenerate()
    with open(FIXTURE_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print(f"wrote {len(data)} entries to {FIXTURE_PATH}", file=sys.stderr)
