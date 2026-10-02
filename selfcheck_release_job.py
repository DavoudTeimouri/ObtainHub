import yaml

d = yaml.safe_load(open('.github/workflows/release.yml', encoding='utf-8'))
rel = d['jobs']['release']

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

    if 'gh release create' in run:
        if 'gh release view' not in run:
            BAD.append("%s: gh release create fails when the release exists" % name)
        if '$LASTEXITCODE -ne 0' not in run:
            BAD.append("%s: gh release create/edit result is unchecked" % name)

if BAD:
    print("FAIL")
    for b in BAD:
        print("  -", b)
    raise SystemExit(1)
print("PASS: release job assigns $tag per-step, fails on missing assets, "
      "handles an existing release")