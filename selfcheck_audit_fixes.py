"""Regression checks for the audit findings fixed on 2026-10-03.

Covers the defects that the existing suite missed: Zip Slip, non-atomic state
writes, manifest-sourced hooks, kwarg mismatch in config restore, and secret
redaction. Run directly: python selfcheck_audit_fixes.py
"""
import json
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

from obtainhub.core.local_apps import extract_archive
from obtainhub.core.state import StateManager
from obtainhub.core.logger import SecretRedactionFilter
from obtainhub.utils.helpers import parse_content_length

FAILS = []


def check(cond, label):
    if cond:
        print("ok   %s" % label)
    else:
        print("FAIL %s" % label)
        FAILS.append(label)


def _zip_with(root, members):
    z = root / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for m in members:
            zf.writestr(m, "data")
    return z


# 1. Zip Slip: traversal members must be rejected, not written outside dest.
with TemporaryDirectory() as td:
    root = Path(td)
    z = _zip_with(root, ["app/../../evil.txt"])
    dest = root / "a" / "b" / "dest"
    try:
        extract_archive(z, dest)
        blocked = False
    except ValueError:
        blocked = True
    check(blocked, "zip slip in single-top branch is rejected")
    check(
        not any(p.name == "evil.txt" for p in root.rglob("evil.txt") if dest not in p.parents),
        "no file written outside destination (single-top)",
    )

with TemporaryDirectory() as td:
    root = Path(td)
    z = _zip_with(root, ["one/../../evil.txt", "two/keep.txt"])
    dest = root / "a" / "b" / "dest"
    try:
        extract_archive(z, dest)
        blocked = False
    except ValueError:
        blocked = True
    check(blocked, "zip slip in extractall branch is rejected")

# Legitimate archives still extract.
with TemporaryDirectory() as td:
    root = Path(td)
    z = _zip_with(root, ["app/ohub.exe", "app/readme.txt"])
    dest = root / "dest"
    try:
        extract_archive(z, dest)
        ok = (dest / "ohub.exe").exists() and (dest / "readme.txt").exists()
    except Exception as e:
        ok = False
        print("   error: %s" % e)
    check(ok, "legitimate single-top archive still flattens")

# 2. state.save must be atomic: no truncation of the live file.
with TemporaryDirectory() as td:
    sf = Path(td) / "state.json"
    sm = StateManager(state_file=sf)
    sm.data = {
        "installed": {"keep/me": {"id": "keep/me", "name": "Keep", "version": "1.0.0"}},
        "manifest_cache": {},
        "check_history": {},
    }
    sm.save()
    original = sf.read_text()
    class Boom(dict):
        def items(self):
            raise RuntimeError("crash mid-dump")
    sm.data = {"installed": {"x/y": Boom(name="X")}}
    try:
        sm.save()
        saved = "no-raise"
    except RuntimeError:
        saved = "raised"
    check(saved == "raised", "state.save propagates the write failure")
    check(sf.read_text() == original, "state.json untouched after a failed save")
    check(not (Path(td) / "state.tmp").exists(), "temp file cleaned up after failure")


# 3. Remote manifests must not be able to inject install hooks.
from obtainhub.core import sources as _sources  # noqa: E402
from obtainhub.core.config import ManifestSource  # noqa: E402

HOSTILE = [{
    "name": "Evil",
    "version": "1.0.0",
    "url": "https://example.com/evil.exe",
    "hooks": {"pre_install": "powershell -enc SQBFAFgA"},
}]

src = ManifestSource(name="evil", url="https://example.com/m.json")


class _Resp:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return json.loads(json.dumps(HOSTILE))


class _Session:
    def get(self, url, **kwargs):
        return _Resp()


_orig = _sources.requests.get
_sources.requests.get = lambda url, **kwargs: _Resp()
try:
    entries = _sources._fetch_manifest(src)
finally:
    _sources.requests.get = _orig

check(bool(entries), "hostile manifest still yields an entry")
for e in entries:
    check(
        not (e.hooks or {}).get("pre_install"),
        "remote manifest cannot inject a pre_install hook",
    )
check(
    not hasattr(e, "hooks") or not (e.hooks or {}),
    "no hook payload survived ingestion",
)


# 4. config restore keyword arguments match the real signature.
import inspect  # noqa: E402

from obtainhub.core.self_uninstall import SelfUninstaller  # noqa: E402

params = set(inspect.signature(SelfUninstaller.restore_from_zip).parameters)
main_src = (Path(__file__).parent / "obtainhub" / "main.py").read_text(encoding="utf-8")
call = main_src.split("uninstaller.restore_from_zip(")[-1][:400]
for kw in ("target_config_dir", "target_state_dir", "target_download_dir"):
    check(kw in params, "signature accepts %s" % kw)
for kw in ("target_config_dir=", "target_state_dir=", "target_download_dir="):
    check(kw in call, "caller passes %s" % kw)
for bad in ("target_config=", "target_state=", "target_downloads="):
    check(bad not in call, "caller no longer passes %s" % bad)


# 5. Content-Length parsing never raises.
check(parse_content_length({"content-length": "not-a-number"}) == 0, "garbage Content-Length -> 0")
check(parse_content_length({}) == 0, "missing Content-Length -> 0")
check(parse_content_length({"content-length": "42"}) == 42, "valid Content-Length preserved")


# 6. Logger redacts secrets.
import logging  # noqa: E402

f = SecretRedactionFilter()
rec = logging.LogRecord("x", logging.INFO, "p", 1, "token ghp_abcdefghijklmnop1234567890", None, None)
f.filter(rec)
check("ghp_abcdefghijklmnop1234567890" not in rec.msg, "logger redacts ghp_ token")


print()
if FAILS:
    print("FAILED: %s" % ", ".join(FAILS))
    raise SystemExit(1)
print("PASS: audit fixes hold")