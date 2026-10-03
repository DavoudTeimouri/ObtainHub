#!/usr/bin/env python3
"""Regression self-check for cross-installer double-install guards.

The EXE (Inno) and MSI (WiX) installers both target C:\\Program Files\\ObtainHub.
Neither originally knew about the other, so installing one after the other left
two entries in Apps & Features and two half-working uninstallers. These checks
fail if either side of the guard is removed.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIX_NS = "{http://schemas.microsoft.com/wix/2006/wi}"
MSI_UPGRADE_CODE = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"


def _check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail and not ok else ''}")
    return ok


def main() -> int:
    iss = (ROOT / "installer" / "setup.iss").read_text(encoding="utf-8")
    code = iss[iss.find("[Code]"):]

    checks: list[bool] = []

    # --- Inno side -------------------------------------------------------
    # Inno AppId is written as {{GUID} -- the double brace escapes a literal
    # one in the preprocessor, so there is no second closing brace.
    checks.append(_check(
        "iss: AppId matches MSI UpgradeCode",
        re.search(r"^AppId=\{\{%s\}\s*$" % re.escape(MSI_UPGRADE_CODE), iss, re.M) is not None,
        "AppId missing or does not match the MSI UpgradeCode",
    ))

    checks.append(_check(
        "iss: InitializeSetup blocks when the MSI is present",
        "InitializeSetup" in code
        and "MsiInstalled" in code
        and re.search(r"if MsiInstalled then", code) is not None,
    ))

    # The key is assembled by concatenation across wrapped lines, so assert on
    # its parts rather than one exact literal.
    checks.append(_check(
        "iss: MsiInstalled probes the MSI uninstall key under HKLM",
        re.search(r"MsiUninstallKey\s*=", code) is not None
        and "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" in code
        and MSI_UPGRADE_CODE in code
        and re.search(r"RegKeyExists\(\s*HKLM\s*,\s*MsiUninstallKey\s*\)", code, re.I) is not None,
    ))

    checks.append(_check(
        "iss: PATH matching compares whole entries, not substrings",
        "Pos(" not in code and "PathHasEntry" in code and "CompareText" in code
        and "Copy(CurrentPath, Offset" not in code,
        "a Pos() substring test would treat ObtainHubBackup as a match",
    ))

    checks.append(_check(
        "iss: uninstall removes the PATH entry it added",
        "CurUninstallStepChanged" in code and "usPostUninstall" in code,
    ))

    # --- MSI side --------------------------------------------------------
    wxs_path = ROOT / "installer" / "setup.wxs"
    try:
        wxs = ET.fromstring(wxs_path.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        print(f"FAIL  wxs: parses as XML -- {exc}")
        return 1

    searches = list(wxs.iter(WIX_NS + "RegistrySearch"))
    checks.append(_check("wxs: parses as XML", True))

    key = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{{{MSI_UPGRADE_CODE}}}_is1"
    checks.append(_check(
        "wxs: RegistrySearch probes the Inno uninstall key",
        any(s.get("Key", "").upper() == key.upper() and s.get("Format") == "exists"
            for s in searches),
    ))

    launches = list(wxs.iter(WIX_NS + "Launch"))
    checks.append(_check(
        "wxs: Launch condition blocks on the Inno search result",
        any("InnoUninstallEntrySearch" in (l.get("Condition") or "") and l.get("Message")
            for l in launches),
    ))

    parent_of = {child: parent for parent in wxs.iter() for child in parent}
    checks.append(_check(
        "wxs: RegistrySearch is a direct child of Product, not a Component",
        all(parent_of.get(s) is not None and parent_of[s].tag == WIX_NS + "Product"
            for s in searches),
    ))

    # --- shared ----------------------------------------------------------
    component_refs = [c.get("Id") for c in wxs.iter(WIX_NS + "ComponentRef")]
    defined = {e.get("Id") for e in wxs.iter() if e.get("Id")}
    checks.append(_check(
        "wxs: every ComponentRef resolves",
        all(r in defined for r in component_refs),
        f"unresolved: {[r for r in component_refs if r not in defined]}",
    ))

    wxs_raw = wxs_path.read_text(encoding="utf-8")
    checks.append(_check(
        "shared: both installers target the same folder",
        "autopf}" in iss and "ProgramFiles64Folder" in wxs_raw,
    ))

    failed = [c for c in checks if not c]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
