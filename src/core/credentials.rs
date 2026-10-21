//! The GitHub token lives in the OS credential store, not in `config.toml`.
//!
//! `config.toml` is a plain text file in a per-user config directory - easy to
//! read, easy to paste into a bug report, easy to end up in a backup. The
//! credential store (Windows Credential Manager) is where a secret belongs.
//!
//! Every function here is best-effort: a machine with no credential store
//! must still work, so the caller falls back to the config file.

use anyhow::Result;

/// The service name ObtainHub uses in the credential store.
#[cfg(windows)]
const SERVICE: &str = "obtainhub";
/// The account name ObtainHub uses in the credential store.
#[cfg(windows)]
const ACCOUNT: &str = "github_token";

/// The credential entry, or `None` when this machine has no credential store.
///
/// The `keyring` crate falls back to an **in-process mock** when the platform
/// has no backend - the write succeeds and the value is gone when the process
/// exits, which would lose the token. Only Windows (the platform this tool
/// ships for) has a real store, so only Windows uses the crate.
#[cfg(windows)]
fn entry() -> Option<keyring::Entry> {
    keyring::Entry::new(SERVICE, ACCOUNT).ok()
}

#[cfg(not(windows))]
fn entry() -> Option<keyring::Entry> {
    None
}

/// Store the GitHub token in the credential store.
///
/// `Ok(false)` means the token was NOT stored, so the caller must keep it in
/// the config file.
pub fn store_token(token: &str) -> Result<bool> {
    let Some(entry) = entry() else {
        return Ok(false);
    };
    if entry.set_password(token).is_err() {
        return Ok(false);
    }
    // Only report success when the value can be read back.
    Ok(entry.get_password().ok().as_deref() == Some(token))
}

/// Read the GitHub token from the credential store.
pub fn load_token() -> Option<String> {
    entry()?.get_password().ok()
}

/// Remove the GitHub token from the credential store.
///
/// `true` when an entry was removed, `false` when there was nothing to
/// remove or the store is not available.
pub fn delete_token() -> bool {
    let Some(entry) = entry() else {
        return false;
    };
    if entry.get_password().is_err() {
        return false;
    }
    entry.delete_credential().is_ok()
}

#[cfg(all(test, not(windows)))]
mod tests {
    use super::*;

    #[test]
    fn a_machine_without_a_credential_store_reports_failure() {
        // The keyring crate falls back to an in-process mock on this platform:
        // the write succeeds and the value is gone when the process exits.
        // Reporting success there would lose the token, so store_token has to
        // say no and the caller keeps it in the config file.
        assert!(!store_token("test-token").unwrap());
        assert!(load_token().is_none());
    }
}
