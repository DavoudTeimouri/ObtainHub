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
    /// `DisplayIcon` - usually the full path of the program's own icon, e.g.
    /// `C:\Program Files\App\App.exe,0`. The only reliable install location
    /// for the many apps that leave `InstallLocation` empty.
    pub display_icon: String,
}

/// Trim whitespace and quotes off a registry path value.
fn clean_path(raw: &str) -> Option<std::path::PathBuf> {
    let s = raw.trim().trim_matches('"').trim();
    if s.is_empty() {
        return None;
    }
    Some(std::path::PathBuf::from(s))
}

/// Parent directory of a Windows path.
///
/// The registry always holds Windows paths, so the split must not depend on
/// the separator the host OS happens to use.
fn windows_parent(path: &str) -> Option<String> {
    let trimmed = path.trim_end_matches(['\\', '/']);
    let idx = trimmed.rfind(['\\', '/'])?;
    let parent = &trimmed[..idx];
    if parent.is_empty() {
        None
    } else {
        Some(parent.to_string())
    }
}

/// Last segment of a Windows path (the file name).
fn windows_file_name(path: &str) -> &str {
    let trimmed = path.trim_end_matches(['\\', '/']);
    match trimmed.rfind(['\\', '/']) {
        Some(i) => &trimmed[i + 1..],
        None => trimmed,
    }
}

impl UninstallEntry {
    /// Identity used to tell "same app, new version" from "different app".
    fn identity(&self) -> String {
        self.uninstall_string.to_lowercase()
    }

    /// Directory the app was installed to.
    ///
    /// Windows offers three partial answers and no single one is right for
    /// every installer, so try them in order of how often each is correct and
    /// keep the first that actually exists on disk:
    /// 1. `InstallLocation` - right for most MSI and NSIS installs.
    /// 2. `DisplayIcon` - the program's own exe path; the only answer for the
    ///    many apps that leave `InstallLocation` empty.
    /// 3. The uninstaller path - NSIS drops `unins000.exe` next to the app.
    pub fn install_dir(&self) -> Option<std::path::PathBuf> {
        let located = clean_path(&self.install_location);
        if let Some(dir) = located.as_ref().filter(|p| p.is_dir()) {
            return Some(dir.clone());
        }
        if let Some(dir) = self.icon_dir().filter(|p| p.is_dir()) {
            return Some(dir);
        }
        if let Some(dir) = self.uninstaller_dir().filter(|p| p.is_dir()) {
            return Some(dir);
        }
        // Nothing on disk (app uninstalled, or a drive we cannot see) - show
        // the best guess rather than an empty path.
        located.or_else(|| self.icon_dir()).or_else(|| self.uninstaller_dir())
    }

    /// Install folder taken from `DisplayIcon` (`C:\App\App.exe,0`).
    fn icon_dir(&self) -> Option<std::path::PathBuf> {
        let icon = self.display_icon.trim().trim_matches('"');
        if icon.is_empty() {
            return None;
        }
        // Strip the trailing ",0" icon index, but only when what precedes it
        // still looks like a file path.
        let path = match icon.rsplit_once(',') {
            Some((head, _)) if head.ends_with(".exe") || head.ends_with(".dll") => head,
            _ => icon,
        };
        windows_parent(path).map(std::path::PathBuf::from)
    }

    /// Install folder taken from the uninstaller path.
    fn uninstaller_dir(&self) -> Option<std::path::PathBuf> {
        let s = self.uninstall_string.trim();
        if s.is_empty() {
            return None;
        }
        // MSI: "MsiExec.exe /I{GUID}" - no path to derive.
        if s.starts_with("MsiExec") || s.starts_with("msiexec") {
            return None;
        }
        // The exe path is the first token. Installers quote it, and a quoted
        // path may contain spaces ("C:\Program Files\App\uninstall.exe") - so
        // take the whole quoted string, not just the first word. Unquoted
        // paths run into the uninstaller's arguments, so cut at the exe.
        let exe = if s.starts_with('"') {
            s[1..].split('"').next().unwrap_or("")
        } else {
            match s.find(".exe") {
                Some(i) => &s[..i + 4],
                None => s.split_whitespace().next().unwrap_or(""),
            }
        }
        .trim_matches('"');
        if exe.is_empty() {
            return None;
        }
        let mut dir = windows_parent(exe)?;
        // Some installers put the uninstaller in a `bin` subfolder.
        if windows_file_name(&dir).eq_ignore_ascii_case("bin") {
            dir = windows_parent(&dir)?;
        }
        Some(std::path::PathBuf::from(dir))
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
                    display_icon: subkey.get_value("DisplayIcon").unwrap_or_default(),
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

/// Find the uninstall entry that belongs to a managed repository.
///
/// The repo id is `owner/Product`; Windows records the product under its
/// display name, which is often the product name plus a version suffix
/// ("OnionHop V3"). Match on the product part and prefer the shortest
/// display name, so "OnionHop V3" wins over "OnionHop V3 Helper".
///
/// `version` is the version we recorded for the app. When several entries
/// share a display name (an old install left behind next to a new one), the
/// version decides which one is the app we actually manage.
pub fn find_entry_for_repo<'a>(
    entries: &'a [UninstallEntry],
    repo: &str,
    version: Option<&str>,
) -> Option<&'a UninstallEntry> {
    let product = repo.rsplit('/').next().unwrap_or(repo).trim().to_lowercase();
    if product.is_empty() {
        return None;
    }

    let candidates: Vec<&UninstallEntry> = entries
        .iter()
        .filter(|e| {
            let name = e.display_name.trim().to_lowercase();
            !name.is_empty()
                && (name == product || name.starts_with(&product) || name.contains(&product))
        })
        .collect();
    if candidates.is_empty() {
        return None;
    }

    // The recorded version wins when it identifies exactly one entry.
    if let Some(v) = version {
        let wanted = crate::core::normalize_version(v).to_lowercase();
        if !wanted.is_empty() {
            if let Some(e) = candidates.iter().find(|e| {
                crate::core::normalize_version(&e.display_version).to_lowercase() == wanted
            }) {
                return Some(e);
            }
        }
    }

    // Exact display-name match, then the shortest name that starts with the
    // product, then the shortest name containing it.
    candidates
        .iter()
        .find(|e| e.display_name.trim().to_lowercase() == product)
        .or_else(|| {
            candidates
                .iter()
                .filter(|e| e.display_name.trim().to_lowercase().starts_with(&product))
                .min_by_key(|e| e.display_name.len())
        })
        .or_else(|| candidates.iter().min_by_key(|e| e.display_name.len()))
        .copied()
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
            display_icon: String::new(),
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

    #[test]
    fn finds_entry_by_repo_product_name() {
        let entries = vec![
            entry("Some Other Tool", "1.0", "C:/x/u.exe"),
            entry("OnionHop V3", "3.9", "C:/p/unins000.exe"),
        ];
        let found = find_entry_for_repo(&entries, "center2055/OnionHop", None).unwrap();
        assert_eq!(found.display_name, "OnionHop V3");
        assert_eq!(found.install_dir().unwrap(), std::path::PathBuf::from("C:/p"));
        assert!(find_entry_for_repo(&entries, "someone/Nothing", None).is_none());
    }

    #[test]
    fn prefers_the_entry_matching_the_recorded_version() {
        let entries = vec![
            entry("OnionHop V3", "3.8", "C:/old/unins000.exe"),
            entry("OnionHop V3", "3.9", "C:/new/unins000.exe"),
        ];
        let found = find_entry_for_repo(&entries, "center2055/OnionHop", Some("3.9")).unwrap();
        assert_eq!(found.uninstall_string, "C:/new/unins000.exe");
    }

    #[test]
    fn install_dir_falls_back_to_the_display_icon() {
        let e = UninstallEntry {
            display_name: "Icon App".to_string(),
            display_version: "1.0".to_string(),
            install_location: String::new(),
            uninstall_string: "MsiExec.exe /I{1234}".to_string(),
            display_icon: "C:\\Program Files\\Icon App\\IconApp.exe,0".to_string(),
        };
        // MSI uninstall strings carry no path, so the icon path is the answer.
        assert_eq!(
            e.icon_dir().unwrap(),
            std::path::PathBuf::from("C:\\Program Files\\Icon App")
        );
    }

    #[test]
    fn uninstaller_in_a_bin_subfolder_resolves_to_the_parent() {
        let e = UninstallEntry {
            display_name: "Bin App".to_string(),
            display_version: "1.0".to_string(),
            install_location: String::new(),
            uninstall_string: "\"C:\\Program Files\\Bin App\\bin\\uninstall.exe\"".to_string(),
            display_icon: String::new(),
        };
        assert_eq!(
            e.uninstaller_dir().unwrap(),
            std::path::PathBuf::from("C:\\Program Files\\Bin App")
        );
    }

    #[test]
    fn quoted_uninstaller_path_with_spaces_keeps_the_whole_path() {
        // Installers quote the path, and "Program Files" has a space in it.
        // Splitting on whitespace alone truncated the path to "C:".
        let e = UninstallEntry {
            display_name: "My App".to_string(),
            display_version: "1.0".to_string(),
            install_location: String::new(),
            uninstall_string: "\"C:\\Program Files\\My App\\uninstall.exe\"".to_string(),
            display_icon: String::new(),
        };
        assert_eq!(
            e.uninstaller_dir().unwrap(),
            std::path::PathBuf::from("C:\\Program Files\\My App")
        );
    }

    #[test]
    fn unquoted_uninstaller_path_with_spaces_stops_at_the_flag() {
        // Unquoted form: the path ends where the arguments begin.
        let e = UninstallEntry {
            display_name: "My App".to_string(),
            display_version: "1.0".to_string(),
            install_location: String::new(),
            uninstall_string: "C:\\Program Files\\My App\\uninstall.exe /currentuser".to_string(),
            display_icon: String::new(),
        };
        assert_eq!(
            e.uninstaller_dir().unwrap(),
            std::path::PathBuf::from("C:\\Program Files\\My App")
        );
    }
}
