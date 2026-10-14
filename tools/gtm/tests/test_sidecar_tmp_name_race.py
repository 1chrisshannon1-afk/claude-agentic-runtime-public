"""Major finding (#21-regression): `_write_sidecar_with_header` must never
use a FIXED temp filename (`<sidecar>.tmp`) -- two concurrent writers can
race `os.replace`, and one can raise `FileNotFoundError` when the other's
`os.replace` already consumed the shared tmp path first. Proven with real
concurrent threads hammering the same sidecar path, asserting zero
exceptions and a structurally valid sidecar left on disk at the end.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import activity_log  # noqa: E402


def test_concurrent_sidecar_writes_never_raise(tmp_path):
    """RED-check: revert _write_sidecar_with_header to
    `tmp = sidecar.with_suffix(sidecar.suffix + ".tmp")` (a fixed shared
    name) and this test is flaky-to-reliably-failing with
    FileNotFoundError raised from inside a worker thread, surfaced here
    via the `errors` list (never left to a background thread's default
    silent-warning exception handling)."""
    trail_path = tmp_path / "TOOL_TRAIL.jsonl"
    trail_path.write_text("", encoding="utf-8")

    errors: list[BaseException] = []

    def writer(i: int) -> None:
        try:
            for j in range(30):
                activity_log._write_sidecar_with_header(
                    trail_path, size=i * 100 + j, lines=j, ids={f"tu_{i}_{j}"}
                )
        except BaseException as exc:  # noqa: BLE001 - must capture every failure mode
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not any(t.is_alive() for t in threads), "a writer thread never finished"
    assert not errors, errors

    sidecar = activity_log._ids_sidecar_path(trail_path)
    assert sidecar.exists()
    # Whatever the last writer left behind, it must be a well-formed
    # sidecar: a header line followed by id lines -- never a partial or
    # corrupted write from a torn concurrent replace.
    header, ids = activity_log._read_sidecar_header_and_ids(sidecar)
    assert header is not None
    assert isinstance(header.get("size"), int)
    assert isinstance(header.get("lines"), int)
    assert ids  # some writer's id set landed intact

    # No stray .tmp files left behind by an interrupted/aborted write.
    leftover_tmp = list(sidecar.parent.glob(sidecar.name + ".*.tmp"))
    assert leftover_tmp == [], f"leftover tmp files: {leftover_tmp}"
