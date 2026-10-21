//! A small on-disk cache for the GitHub candidate search.
//!
//! `ohub check --candidates` searches GitHub once per installed app, with up
//! to four search terms per app. The answer barely changes between runs, so
//! it is kept for a day - the search is the slowest part of the command and
//! it eats the API rate limit.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// How long a cached candidate list stays valid.
const TTL: Duration = Duration::from_secs(24 * 60 * 60);

#[derive(Debug, Serialize, Deserialize, Default)]
struct Entry {
    /// When the entry was written, in seconds since the unix epoch.
    written_at: u64,
    repos: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Default)]
struct Cache {
    entries: HashMap<String, Entry>,
}

fn cache_path() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(std::env::temp_dir)
        .join("obtainhub")
        .join("candidate-cache.json")
}

fn key(app: &str) -> String {
    app.trim().to_lowercase()
}

/// The repos found for an app, if the cached entry is still fresh.
pub fn get(app: &str) -> Option<Vec<String>> {
    let cache = load().ok()?;
    let entry = cache.entries.get(&key(app))?;
    let now = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .ok()?
        .as_secs();
    if !is_fresh(entry, now) {
        return None;
    }
    Some(entry.repos.clone())
}

/// Whether an entry is still within the time to live.
fn is_fresh(entry: &Entry, now: u64) -> bool {
    now.saturating_sub(entry.written_at) <= TTL.as_secs()
}

/// Remember the repos found for an app.
///
/// A failure to write the cache is not a failure of the search, so the error
/// is returned and the caller decides - the cache is an optimisation, never a
/// requirement.
pub fn put(app: &str, repos: &[String]) -> Result<()> {
    let mut cache = load().unwrap_or_default();
    let written_at = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    cache.entries.insert(
        key(app),
        Entry {
            written_at,
            repos: repos.to_vec(),
        },
    );
    save(&cache)
}

fn load() -> Result<Cache> {
    let path = cache_path();
    if !path.exists() {
        return Ok(Cache::default());
    }
    let content = std::fs::read_to_string(&path)?;
    // A corrupt cache is not worth failing over - start again.
    Ok(serde_json::from_str(&content).unwrap_or_default())
}

fn save(cache: &Cache) -> Result<()> {
    let path = cache_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, serde_json::to_string_pretty(cache)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_entry_older_than_a_day_is_not_fresh() {
        let now = 2 * 24 * 60 * 60;
        let fresh = Entry {
            written_at: now - 60,
            repos: vec!["center2055/OnionHop".to_string()],
        };
        assert!(is_fresh(&fresh, now));
        let stale = Entry {
            written_at: now - 2 * 24 * 60 * 60,
            repos: vec![],
        };
        assert!(!is_fresh(&stale, now));
    }

    #[test]
    fn the_key_ignores_case_and_surrounding_space() {
        assert_eq!(key("OnionHop V3"), "onionhop v3");
        assert_eq!(key("  ripgrep "), "ripgrep");
    }
}
