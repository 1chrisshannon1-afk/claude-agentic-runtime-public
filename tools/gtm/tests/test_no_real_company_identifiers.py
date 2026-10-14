"""Data-exposure guard: `tools/gtm/` is in the runtime mirror's publish set
(`.mirror/config.json`'s `include`), so no real company identifier (account
ids, page ids, real domains) may ever be committed into it. Fixtures use
shape-matched synthetic stand-ins instead.

This test knows the real identifiers only as SHA-256 fingerprints, so its own
source never carries a real value. It extracts every candidate token from
every tools/gtm source, test, schema and README file (never `contracts/` or
`CONTRACTS.md`, which the publish gate's redaction handles) and fails if any
token's fingerprint matches a known real identifier.

RED-check: put any real identifier whose fingerprint is listed below into any
file under tools/gtm (outside contracts/) and this fails, naming the file.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_GTM_DIR = Path(__file__).resolve().parents[1]

# sha256(identifier) -> what it is (generic labels only; never the company).
_REAL_IDENTIFIER_SHA256 = {
    "f3590e7033fabdd3189c2b47783219f3924f82163674f44db62f06840df83c0e": "company A remodeling domain",
    "5e8f951519cc07c5e537acaae392408bb7ab961982ce822291c4bcfa73060a40": "company A restoration domain",
    "2e6a835620b8fb1f17c5a583aab332d5fa22deda32a55137a9de46d3bb43eb43": "company A Facebook Page id",
    "b9c86bc87e4d9754586d259a2dabc6aafe6b4933e8e98ebc96e3d2eb4ab783fa": "company A GBP location id",
    "03054f531f33c61b47b020d40cf9432636505d4172c0be313ae4caab83ed9e03": "company A GBP second location id",
    "83f8997fec2dd7641ac233e17f202276d0e4fd8d24897ca42c4f745c5baa506a": "company A Google Ads customer id",
    "6a70d081b421ffa218ac92571281a48318c99ed22a3d9b13c66df65d7e802d9a": "company A Google Ads customer id (no dashes)",
    "22e022a2790ed8596351caaddc5e3a07f07c7c9102561e9d1a5775ee95948c65": "company A Ads conversion id",
    "aebf4b91f05f94c14e90e755482ffddfa978ae5fd6bd9675dc650c9acbaf472c": "company A GA4 property id",
    "8e5bf4efdb64c62959463d581ce8ec710d18376dee30877c6b9a60edbe4d54fd": "company A GTM container id",
    "0a400054c1207faa46bfee7fb5c042adfde89d068a34a2c2d7fb532acee009ef": "company A Meta pixel id",
    "7d30d635a1330b7e58844432d14adc28852dbf8fb92202c8b1a5510f41ff1b75": "company B Facebook Page id",
}

# Digit runs (optionally dash-separated) and domain names.
_TOKEN_RE = re.compile(r"\d[\d-]{5,}\d|[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|co)\b", re.IGNORECASE)


def _scanned_files() -> list[Path]:
    files = []
    for path in sorted(_GTM_DIR.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".json", ".md"}:
            continue
        rel = path.relative_to(_GTM_DIR)
        if rel.parts[0] == "contracts" or rel.name == "CONTRACTS.md" or "__pycache__" in rel.parts:
            continue
        files.append(path)
    return files


def _real_identifier_hits(text: str) -> set[str]:
    hits = set()
    for token in _TOKEN_RE.findall(text):
        digest = hashlib.sha256(token.lower().encode()).hexdigest()
        if digest in _REAL_IDENTIFIER_SHA256:
            hits.add(_REAL_IDENTIFIER_SHA256[digest])
    return hits


def test_no_tools_gtm_file_carries_a_known_real_identifier():
    offenders = [
        f"{path.relative_to(_GTM_DIR)}: {sorted(hits)}"
        for path in _scanned_files()
        if (hits := _real_identifier_hits(path.read_text(encoding="utf-8", errors="replace")))
    ]
    assert offenders == [], "real company identifier(s) found in tools/gtm:\n" + "\n".join(offenders)


def test_scanner_detects_a_fingerprinted_identifier():
    # Positive control built from a synthetic value whose fingerprint is
    # added only for this check, so the scanner is proven able to fire.
    synthetic = "555-000-1234"
    _REAL_IDENTIFIER_SHA256[hashlib.sha256(synthetic.encode()).hexdigest()] = "synthetic control"
    try:
        assert _real_identifier_hits(f"account id {synthetic} here") == {"synthetic control"}
        assert _real_identifier_hits("account id 555-000-9999 here") == set()
    finally:
        del _REAL_IDENTIFIER_SHA256[hashlib.sha256(synthetic.encode()).hexdigest()]
