"""Self-check for `ohub config auth` — run directly, no framework:

    python3 selfcheck_config_auth.py

Verifies the token-source report and the redaction of `config show` /
`config get github_token` on the current machine.
"""

import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from obtainhub.core.config import Config, ConfigManager, keyring_backend_is_secure
import obtainhub.main as main_mod

FAKE_TOKEN = "ghp_selfcheck_deadbeef"


class FakeState:
    def __init__(self, state_file=None):
        self.state_file = state_file


class Args:
    def __init__(self, **kw):
        self.json = False
        self.key = None
        self.value = None
        self.token_source = "auto"
        self.__dict__.update(kw)


def run(action, isatty=False, **kw):
    tmp = tempfile.mkdtemp()
    manager = ConfigManager(config_dir=tmp)
    config = manager.load()
    config.github_token = FAKE_TOKEN
    manager._config = config
    manager.load = lambda: config
    buf = io.StringIO()
    # sys.stdout is buf inside redirect_stdout, so this is what main.py sees.
    buf.isatty = lambda: isatty
    with redirect_stdout(buf):
        main_mod.cmd_config(Args(config_action=action, **kw), manager, FakeState(Path(tmp) / "state.json"))
    return buf.getvalue()


failures = []

out = run("show")
assert_true = FAKE_TOKEN not in out
if not assert_true:
    failures.append("config show leaked the token")
if "hidden" not in out:
    failures.append("config show did not mark the token as hidden")

out = run("get", key="github_token")
if FAKE_TOKEN in out:
    failures.append("config get github_token leaked the token")

out = run("set", key="github_token", value=FAKE_TOKEN)
if FAKE_TOKEN in out:
    failures.append("config set echoed the token back")

out = run("auth")
if "keyring_backend" not in out:
    failures.append("config auth did not report the backend")
if str(keyring_backend_is_secure()).lower() not in out:
    failures.append("config auth did not report the secure flag")

for source in ("auto", "keyring", "env", "file", "plaintext-keyring"):
    out = run("auth", token_source=source)
    # Non-TTY output is JSON; TTY output is "key: value" lines. Accept either.
    if f'"{source}"' not in out and f"requested_source: {source}" not in out:
        failures.append(f"config auth --token-source {source} not honoured")

# TTY rendering path
out = run("auth", isatty=True)
if "requested_source: auto" not in out:
    failures.append("config auth TTY rendering missing")
if "keyring_backend: keyrings.alt.file.PlaintextKeyring" not in out:
    failures.append("config auth TTY rendering did not name the insecure backend")
if "[!]" not in out:
    failures.append("config auth did not warn about the insecure backend")

print("keyring backend secure:", keyring_backend_is_secure())
if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS: token never printed, auth reports backend and honours --token-source")
