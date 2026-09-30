Release notes for ObtainHub 2.0.0.

## Highlights

ObtainHub 2.0.0 is a structural release. It adds a capability-sandboxed plugin
system, a hexagonal ports-and-adapters core, a scriptable CLI surface, binary
hardening, and a six-job CI pipeline. It also closes four ways the GitHub token
could leak, and fixes three latent breakages that made backup, restore and
self-uninstall fail outright.

## Breaking changes

- **Storing a token on a plaintext credential backend is now an error.** If no
  OS credential store is present, `keyring` silently selects
  `keyrings.alt.file.PlaintextKeyring`; ohub used to report success while writing
  the token unencrypted to disk. It now refuses and names the remedy. Export
  `GITHUB_TOKEN` to keep the secret out of any file.
- **`ohub config show` and `ohub config get github_token` redact the token** to
  `<set, N chars, hidden>`. `ohub config set github_token` no longer echoes the
  value. Scripts that parsed the raw token from stdout must read it from the
  environment or the credential store.
- **Backup archives no longer contain the token.** `ohub config backup` and
  `ohub self-uninstall --backup` previously wrote it into `metadata.json`.
  `ohub config restore` re-reads it from the credential store.

## New in this release

- `ohub config auth [--token-source auto|keyring|env|file|plaintext-keyring]`
  reports which store holds the token and whether it is protected at rest.
- Plugin sandbox with capability grants, signed manifests and a trusted-key
  registry, plus a subprocess runner and a worked `plugin.yaml` example.
- Ports and adapters: ABC contracts in `obtainhub/ports/`, implementations in
  `obtainhub/adapters/`, in-memory event bus in `core/event_bus.py`.
- Global `--json` / `--quiet` and per-command `--dry-run` / `--force`.
- `scripts/ohub.bash-completion` shell completion.
- `--onedir` build with ASLR, DEP, NXCOMPAT and CFG; UPX gated behind
  `OBTAINHUB_SIGNED_BUILD=1`.
- CI split into typecheck, security-audit, build, smoke-test, provenance and
  release, with a CycloneDX SBOM and SLSA provenance attestations.

## Fixes

- `ohub config backup`, `ohub config restore` and `ohub self-uninstall` all
  failed with an `IndentationError` in `core/self_uninstall.py`.
- `ohub config backup` raised `UnboundLocalError` on `shutil` and
  `NameError` on `__version__`.

## Upgrade

Download `ObtainHub-Setup.exe` or `ObtainHub.msi` from the release assets. The MSI
`MajorUpgrade` path handles the upgrade from 1.x. If you previously stored a
token in plaintext because your machine had no credential store, set
`GITHUB_TOKEN` in your environment or install an OS credential store, then run
`ohub config set github_token <token>`.
