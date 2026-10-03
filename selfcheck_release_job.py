import re
import yaml

d = yaml.safe_load(open('.github/workflows/release.yml', encoding='utf-8'))
rel = d['jobs']['release']

RELEASE_ASSETS = ("ObtainHub.msi", "ObtainHub-Setup.exe")

BAD = []

for s in rel['steps']:
    name = s.get('name') or s.get('uses')
    run = s.get('run') or ''
    if not run:
        continue

    # Every gh invocation needs the tag. A `run:` block is its own PowerShell
    # process, so $tag set in another step is undefined here. This is what
    # produced "requires at least 2 arg(s), only received 1".
    if 'gh release' in run and '$tag' in run:
        if '$tag =' not in run and '$env:GITHUB_REF_NAME' not in run:
            BAD.append("%s: uses $tag but never assigns it in this step" % name)

    # A release that ships without its installers is the bug being fixed.
    if 'gh release upload' in run and 'exit 1' not in run:
        BAD.append("%s: uploads assets but cannot fail on a missing file" % name)

    # The SBOM is a CI artifact and an attestation subject, never a release
    # asset. All 31 prior releases ship exactly the MSI and the EXE.
    if 'gh release upload' in run:
        for a in RELEASE_ASSETS:
            if a not in run:
                BAD.append("%s: does not upload %s" % (name, a))
        if 'ObtainHub-sbom.json' in run:
            BAD.append(
                "%s: uploads ObtainHub-sbom.json, which is not a release asset"
                % name
            )

    if 'gh release create' in run:
        if 'gh release view' not in run:
            BAD.append("%s: gh release create fails when the release exists" % name)
        if '$LASTEXITCODE -ne 0' not in run:
            BAD.append("%s: gh release create/edit result is unchecked" % name)
        # A bare 'gh release view $tag *> $null' turns gh's "release not found"
        # on stderr into a terminating PowerShell NativeCommandError, so the
        # first-ever release run dies instead of falling through to create.
        if re.search(r"gh release view .*\*>\s*\$null", run):
            BAD.append(
                "%s: probes gh release view via redirection; stderr must be "
                "suppressed by cmd so a missing release is not an error" % name
            )

if BAD:
    print("FAIL")
    for b in BAD:
        print("  -", b)
    raise SystemExit(1)
print("PASS: release job assigns $tag per-step, fails on missing assets, "
      "handles an existing release, uploads only %s" % " + ".join(RELEASE_ASSETS))