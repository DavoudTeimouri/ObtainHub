"""Tests for token storage hardening (Phase 7)."""

import io
import json
import os
import sys
import zipfile
from contextlib import redirect_stdout

import pytest

from obtainhub.core.config import Config, ConfigManager, keyring_backend_is_secure


@pytest.fixture
def plaintext_keyring(monkeypatch):
    """Force the insecure keyrings.alt PlaintextKeyring backend."""
    import keyring
    from keyring.backend import KeyringBackend

    class PlaintextKeyring(KeyringBackend):
        priority = 10
        store = {}

        def get_password(self, service, username):
            return self.store.get((service, username))

        def set_password(self, service, username, password):
            self.store[(service, username)] = password

        def delete_password(self, service, username):
            self.store.pop((service, username), None)

    backend = PlaintextKeyring()
    PlaintextKeyring.store = {}
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    yield backend
    PlaintextKeyring.store = {}


@pytest.fixture
def config_dir(tmp_path):
    return tmp_path / "config"


def test_keyring_backend_is_secure_false_for_plaintext(plaintext_keyring):
    """The insecure fallback backend must be reported as insecure."""
    assert keyring_backend_is_secure() is False


def test_save_refuses_plaintext_backend(config_dir, plaintext_keyring, monkeypatch):
    """Saving a token on a plaintext backend must fail loudly, not silently leak."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("OBTAINHUB_TOKEN", raising=False)

    manager = ConfigManager(config_dir=config_dir)
    config = Config()
    config.github_token = "ghp_secret"

    with pytest.raises(ValueError, match="PlaintextKeyring"):
        manager.save(config)

    # The secret must not have reached the plaintext store.
    assert plaintext_keyring.store.get(("obtainhub", "github_token")) is None
    # Nor the config file.
    if manager.config_file.exists():
        assert "ghp_secret" not in manager.config_file.read_text()


def test_save_allowed_when_env_token_present(config_dir, plaintext_keyring, monkeypatch):
    """With GITHUB_TOKEN exported the plaintext refusal is bypassed on purpose."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_env")

    manager = ConfigManager(config_dir=config_dir)
    config = Config()
    config.github_token = "ghp_secret"

    manager.save(config)  # must not raise

    saved = json.loads(manager.config_file.read_text())
    assert saved.get("github_token") == ""


def test_config_show_hides_token(config_dir, monkeypatch, tmp_path):
    """`config show` must never print the secret, in text or JSON mode."""
    import obtainhub.main as main_mod
    from obtainhub.core.config import ConfigManager as CM

    class Args:
        config_action = "show"
        json = False
        key = None
        value = None

    manager = CM(config_dir=config_dir)
    config = manager.load()
    config.github_token = "ghp_supersecret"
    manager._config = config

    # Patch the loader so cmd_config sees our in-memory token.
    monkeypatch.setattr(manager, "load", lambda: config)
    monkeypatch.setattr(main_mod, "ConfigManager", lambda **kw: manager, raising=False)

    buf = io.StringIO()
    with redirect_stdout(buf):
        main_mod.cmd_config(Args(), manager, _FakeState())
    out = buf.getvalue()

    assert "ghp_supersecret" not in out
    assert "hidden" in out


def test_config_get_hides_token(config_dir, monkeypatch):
    """`config get github_token` must not echo the secret."""
    import obtainhub.main as main_mod
    from obtainhub.core.config import ConfigManager as CM

    class Args:
        config_action = "get"
        json = False
        key = "github_token"
        value = None

    manager = CM(config_dir=config_dir)
    config = manager.load()
    config.github_token = "ghp_supersecret"
    manager._config = config
    monkeypatch.setattr(manager, "load", lambda: config)

    buf = io.StringIO()
    with redirect_stdout(buf):
        main_mod.cmd_config(Args(), manager, _FakeState())
    out = buf.getvalue()

    assert "ghp_supersecret" not in out
    assert "hidden" in out


def test_config_backup_metadata_omits_token(config_dir, tmp_path, monkeypatch):
    """The backup zip must not carry the GitHub token in plaintext."""
    import obtainhub.main as main_mod
    from obtainhub.core.config import ConfigManager as CM
    from obtainhub.core.state import StateManager

    manager = CM(config_dir=config_dir)
    config = manager.load()
    config.github_token = "ghp_supersecret"
    manager._config = config
    monkeypatch.setattr(manager, "load", lambda: config)

    out_zip = tmp_path / "backup.zip"
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    class Args:
        config_action = "backup"
        output = str(out_zip)
        include_downloads = False
        json = False
        key = None
        value = None

    buf = io.StringIO()
    with redirect_stdout(buf):
        main_mod.cmd_config(Args(), manager, _FakeState(state_dir / "state.json"))

    assert out_zip.exists()
    with zipfile.ZipFile(out_zip) as zf:
        names = zf.namelist()
        assert "metadata.json" in names
        raw = zf.read("metadata.json").decode()
    assert "ghp_supersecret" not in raw
    assert json.loads(raw)["github_token"] == ""


class _FakeState:
    """Minimal StateManager stand-in for config subcommands."""

    def __init__(self, state_file=None):
        self.state_file = state_file
