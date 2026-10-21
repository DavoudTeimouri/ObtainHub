//! Windows uninstall-registry scanning and change detection.
//!
//! Third-party installers (NSIS, MSI) register themselves under
//! `HKLM/HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`. Reading
//! that key before and after running an installer tells us where the app
//! really landed and how to uninstall it later.

/// One entry from the Windows uninstall registry.
#[derive(Debug, Clone, Default)]
pub struct UninstallEntry {
    pub display_name: String,
    pub display_version: String,
    pub install_location: String,
    pub uninstall_string: String,
}

impl UninstallEntry {
    /// Identity used to tell "same app, new version" from "different app".
    fn identity(&self) -> String {
        self.uninstall_string.to_lowercase()
    }

    /// Directory the app was installed to, if the installer recorded one.
    pub fn install_dir(&self) -> Option<std::path::PathBuf> {
        let loc = self.install_location.trim();
        if !loc.is_empty() {
            return Some(std::path::PathBuf::from(loc));
        }
        // Fall back to the directory holding the uninstaller.
        let s = self.uninstall_string.trim().trim_matches('"');
        if s.is_empty() {
            return None;
        }
        // MSI uninstall strings are "MsiExec.exe /I {GUID}" - no path to derive.
        if s.starts_with("MsiExec") || s.starts_with("msiexec") {
            return None;
        }
        std::path::Path::new(s)
            .parent()
            .map(|p| p.to_path_buf())
            .filter(|p| !p.as_os_str().is_empty())
    }
}

/// Snapshot every uninstall entry Windows knows about.
#[cfg(windows)]
pub fn scan_uninstall_entries() -> Vec<UninstallEntry> {
    use winreg::enums::*;
    use winreg::RegKey;

    let mut results = Vec::new();
    let uninstall_path = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall";

    for &root in &[HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER] {
        for &view in &[KEY_WOW64_64KEY, KEY_WOW64_32KEY] {
            let hklm = RegKey::predef(root);
            let Ok(uninstall_key) = hklm.open_subkey_with_flags(uninstall_path, KEY_READ | view) else {
                continue;
            };
            for subkey_name in uninstall_key.enum_keys().flatten() {
                let Ok(subkey) = uninstall_key.open_subkey_with_flags(&subkey_name, KEY_READ | view) else {
                    continue;
                };
                let display_name: String = subkey.get_value("DisplayName").unwrap_or_default();
                if display_name.is_empty() {
                    continue;
                }
                results.push(UninstallEntry {
                    display_name,
                    display_version: subkey.get_value("DisplayVersion").unwrap_or_default(),
                    install_location: subkey.get_value("InstallLocation").unwrap_or_default(),
                    uninstall_string: subkey.get_value("UninstallString").unwrap_or_default(),
                });
            }
        }
    }

    results
}

#[cfg(not(windows))]
pub fn scan_uninstall_entries() -> Vec<UninstallEntry> {
    Vec::new()
}

/// Find the uninstall entry that appeared (or changed version) between two
/// registry snapshots.
///
/// `name_hints` are candidate app names (repo name, product name). When
/// several entries changed, the hint decides which one belongs to us.
pub fn detect_install_change(
    before: &[UninstallEntry],
    after: &[UninstallEntry],
    name_hints: &[String],
) -> Option<UninstallEntry> {
    // Index "before" by identity so we can tell added from merely-changed.
    let before_map: std::collections::HashMap<String, UninstallEntry> = before
        .iter()
        .map(|e| (e.identity(), e.clone()))
        .collect();

    // Candidates: entries whose identity is new, or whose version changed.
    let mut candidates: Vec<UninstallEntry> = Vec::new();
    for entry in after {
        match before_map.get(&entry.identity()) {
            None => candidates.push(entry.clone()),
            Some(old) => {
                if old.display_version != entry.display_version
                    || old.install_location != entry.install_location
                {
                    candidates.push(entry.clone());
                }
            }
        }
    }

    if candidates.is_empty() {
        return None;
    }
    if candidates.len() == 1 {
        return candidates.into_iter().next();
    }

    // Several changed - pick the one that best matches a name hint.
    let hints: Vec<String> = name_hints
        .iter()
        .map(|h| h.to_lowercase())
        .filter(|h| h.len() >= 3)
        .collect();

    let mut best: Option<(usize, &UninstallEntry)> = None;
    for candidate in &candidates {
        let name = candidate.display_name.to_lowercase();
        let score = hints
            .iter()
            .filter(|h| name.contains(h.as_str()) || h.contains(&name))
            .count();
        if score > 0 && best.map(|(s, _)| score > s).unwrap_or(true) {
            best = Some((score, candidate));
        }
    }

    best.map(|(_, e)| e.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entry(name: &str, version: &str, uninstall: &str) -> UninstallEntry {
        UninstallEntry {
            display_name: name.to_string(),
            display_version: version.to_string(),
            install_location: String::new(),
            uninstall_string: uninstall.to_string(),
        }
    }

    #[test]
    fn detects_new_entry() {
        let before = vec![entry("Other", "1.0", "C:\\o\\u.exe")];
        let after = vec![
            entry("Other", "1.0", "C:\\o\\u.exe"),
            entry("OnionHop", "3.9", "C:\\p\\unins000.exe"),
        ];
        let found = detect_install_change(&before, &after, &["OnionHop".to_string()]);
        assert_eq!(found.unwrap().display_name, "OnionHop");
    }

    #[test]
    fn detects_version_change() {
        let before = vec![entry("OnionHop", "3.8", "C:\\p\\unins000.exe")];
        let after = vec![entry("OnionHop", "3.9", "C:\\p\\unins000.exe")];
        let found = detect_install_change(&before, &after, &["OnionHop".to_string()]);
        assert_eq!(found.unwrap().display_version, "3.9");
    }

    #[test]
    fn returns_none_when_nothing_changed() {
        let before = vec![entry("OnionHop", "3.9", "C:\\p\\unins000.exe")];
        let after = vec![entry("OnionHop", "3.9", "C:\\p\\unins000.exe")];
        assert!(detect_install_change(&before, &after, &["OnionHop".to_string()]).is_none());
    }

    #[test]
    fn picks_best_match_when_several_change() {
        let before = vec![];
        let after = vec![
            entry("Some Other Tool", "1.0", "C:\\x\\u.exe"),
            entry("OnionHop V3", "3.9", "C:\\p\\unins000.exe"),
        ];
        let found = detect_install_change(&before, &after, &["OnionHop".to_string()]);
        assert_eq!(found.unwrap().display_name, "OnionHop V3");
    }
}
