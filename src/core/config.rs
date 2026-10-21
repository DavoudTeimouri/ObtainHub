use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use dirs;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestSource {
    pub name: String,
    pub url: String,
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub headers: HashMap<String, String>,
    #[serde(default = "default_src_type")]
    pub src_type: String,
    #[serde(default)]
    pub hooks: HashMap<String, String>,
    #[serde(default)]
    pub priority: Option<i32>,
    #[serde(default)]
    pub auto_sync: bool,
    /// Registry type: github, github-packages, crates-io, npm, pypi, generic
    #[serde(default = "default_registry_type")]
    pub registry_type: String,
    /// Package name in the registry (if different from repo name)
    #[serde(default)]
    pub package_name: Option<String>,
}

fn default_src_type() -> String { "github".to_string() }

fn default_registry_type() -> String { "github".to_string() }

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ScheduleConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_schedule_interval")]
    pub interval_hours: u64,
    #[serde(default = "default_true")]
    pub notify_on_update: bool,
    #[serde(default)]
    pub run_on_startup: bool,
    #[serde(default)]
    pub last_run: Option<chrono::DateTime<chrono::Utc>>,
}

fn default_schedule_interval() -> u64 { 24 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_github_token")]
    pub github_token: Option<String>,
    
    #[serde(default = "default_install_dir")]
    pub install_dir: PathBuf,
    
    #[serde(default = "default_download_dir")]
    pub download_dir: PathBuf,
    
    #[serde(default = "default_shim_dir")]
    pub shim_dir: PathBuf,
    
    #[serde(default = "default_parallel_downloads")]
        pub parallel_downloads: usize,
    
        #[serde(default = "default_timeout")]
        pub timeout_seconds: u64,
    
        #[serde(default = "default_check_interval")]
        pub update_check_interval_hours: u64,
    
        #[serde(default = "default_true")]
        pub auto_cleanup: bool,
    
        #[serde(default)]
        pub proxy: Option<String>,
    
        #[serde(default = "default_true")]
        pub verify_checksums: bool,
    
        #[serde(default)]
        pub download_bandwidth_limit: Option<u64>,
    
        #[serde(default)]
        pub manifest_sources: Vec<ManifestSource>,
    
        #[serde(default)]
        pub schedule: ScheduleConfig,
    
        #[serde(default)]
        pub groups: HashMap<String, Vec<String>>,
    
        // HTTP retry configuration
        #[serde(default = "default_http_retries")]
        pub http_retries: u32,
    
        #[serde(default = "default_http_retry_delay")]
        pub http_retry_delay_ms: u64,
    
        #[serde(default = "default_http_retry_backoff")]
        pub http_retry_backoff: f64,
}

fn default_download_dir() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub")
        .join("downloads")
}

fn default_shim_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("bin")
        .join("obtainhub")
}

fn default_github_token() -> Option<String> { None }
fn default_install_dir() -> PathBuf { 
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub")
        .join("repos")
}
fn default_parallel_downloads() -> usize { 4 }
fn default_timeout() -> u64 { 30 }
fn default_check_interval() -> u64 { 24 }
fn default_true() -> bool { true }

// HTTP retry defaults
fn default_http_retries() -> u32 { 3 }
fn default_http_retry_delay() -> u64 { 1000 } // 1 second
fn default_http_retry_backoff() -> f64 { 2.0 } // exponential backoff factor

impl Default for Config {
    fn default() -> Self {
        Self {
            github_token: None,
            install_dir: default_install_dir(),
            download_dir: default_download_dir(),
            shim_dir: default_shim_dir(),
            parallel_downloads: 4,
            timeout_seconds: 30,
            update_check_interval_hours: 24,
            auto_cleanup: true,
            proxy: None,
            verify_checksums: true,
            download_bandwidth_limit: None,
            manifest_sources: Vec::new(),
            schedule: ScheduleConfig {
                enabled: false,
                interval_hours: 24,
                notify_on_update: true,
                run_on_startup: false,
                last_run: None,
            },
            groups: HashMap::new(),
            http_retries: 3,
            http_retry_delay_ms: 1000,
            http_retry_backoff: 2.0,
        }
    }
}

pub struct ConfigManager {
    pub config: Config,
    config_path: PathBuf,
}

impl ConfigManager {
    pub fn new() -> Result<Self> {
        let config_dir = dirs::config_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("ObtainHub");
        
        std::fs::create_dir_all(&config_dir)?;
        
        let config_path = config_dir.join("config.toml");
        
        let mut config: Config = if config_path.exists() {
            let content = std::fs::read_to_string(&config_path)?;
            toml::from_str(&content)?
        } else {
            Config::default()
        };
        Self::sanitize(&mut config);

        let mut manager = Self { config, config_path };
        // A token left in the config file by an older version moves into the
        // credential store, so the plain text copy disappears on first run.
        if manager.migrate_token_to_credential_store()? {
            eprintln!(
                "Moved the GitHub token from {} into the OS credential store.",
                manager.config_path.display()
            );
        }
        Ok(manager)
    }

    /// The GitHub token: the OS credential store first, the config file second.
    ///
    /// The credential store is the token's home. The config file is only a
    /// fallback for a machine with no credential store.
    pub fn github_token(&self) -> Option<String> {
        crate::core::credentials::load_token().or_else(|| self.config.github_token.clone())
    }

    /// Where the GitHub token lives: "credential store", "config file" or
    /// "not set".
    pub fn token_source(&self) -> &'static str {
        if crate::core::credentials::load_token().is_some() {
            "credential store"
        } else if self.config.github_token.is_some() {
            "config file"
        } else {
            "not set"
        }
    }

    /// Move a plaintext token from the config file into the OS credential
    /// store.
    ///
    /// Does nothing when there is no token, or when this machine has no
    /// credential store. Returns `true` when the config file was changed.
    pub fn migrate_token_to_credential_store(&mut self) -> Result<bool> {
        let Some(token) = self.config.github_token.clone() else {
            return Ok(false);
        };
        if crate::core::credentials::load_token().is_none()
            && !crate::core::credentials::store_token(&token)?
        {
            // No credential store on this machine - the token stays where it is.
            return Ok(false);
        }
        self.config.github_token = None;
        self.save()?;
        Ok(true)
    }

    /// Clamp out-of-range values that would otherwise cause hangs or div-by-zero
    /// downstream. Config is user-editable, so treat bad values as defaults, not errors.
    fn sanitize(config: &mut Config) {
        if config.parallel_downloads == 0 {
            config.parallel_downloads = 4;
        }
        if config.parallel_downloads > 32 {
            config.parallel_downloads = 32;
        }
        if config.timeout_seconds == 0 {
            config.timeout_seconds = 30;
        }
        if config.timeout_seconds > 3600 {
            config.timeout_seconds = 3600;
        }
        if config.update_check_interval_hours == 0 {
            config.update_check_interval_hours = 24;
        }
        if config.update_check_interval_hours > 8760 {
            config.update_check_interval_hours = 8760;
        }
        if config.schedule.interval_hours == 0 {
            config.schedule.interval_hours = 24;
        }
        if config.schedule.interval_hours > 8760 {
            config.schedule.interval_hours = 8760;
        }
        // Ensure paths are absolute
        if !config.install_dir.is_absolute() {
            config.install_dir = std::env::current_dir().unwrap_or_default().join(config.install_dir.clone());
        }
        if !config.download_dir.is_absolute() {
            config.download_dir = std::env::current_dir().unwrap_or_default().join(config.download_dir.clone());
        }
        if !config.shim_dir.is_absolute() {
            config.shim_dir = std::env::current_dir().unwrap_or_default().join(config.shim_dir.clone());
        }
    }
    
    pub fn get(&self) -> &Config {
        &self.config
    }
    
    pub fn get_mut(&mut self) -> &mut Config {
        &mut self.config
    }
    
    pub fn save(&self) -> Result<()> {
        let mut config = self.config.clone();
        Self::sanitize(&mut config);
        let content = toml::to_string_pretty(&config)?;
        std::fs::write(&self.config_path, content)?;
        Ok(())
    }
    
    pub fn path(&self) -> &Path {
        &self.config_path
    }
    
    pub fn reset(&mut self) -> Result<()> {
        self.config = Config::default();
        self.save()
    }

    pub fn repair(&mut self) -> Result<()> {
        // Ensure config directory exists
        if let Some(parent) = self.config_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        // Save to repair any corruption
        self.save()
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_clamps_zero_values() {
        let mut c = Config {
            parallel_downloads: 0,
            timeout_seconds: 0,
            update_check_interval_hours: 0,
            schedule: ScheduleConfig { interval_hours: 0, ..Default::default() },
            ..Default::default()
        };

        ConfigManager::sanitize(&mut c);

        assert_eq!(c.parallel_downloads, 4);
        assert_eq!(c.timeout_seconds, 30);
        assert_eq!(c.update_check_interval_hours, 24);
        assert_eq!(c.schedule.interval_hours, 24);
    }

    #[test]
    fn sanitize_leaves_valid_values_alone() {
        let mut c = Config {
            parallel_downloads: 8,
            timeout_seconds: 90,
            ..Default::default()
        };

        ConfigManager::sanitize(&mut c);

        assert_eq!(c.parallel_downloads, 8);
        assert_eq!(c.timeout_seconds, 90);
    }

    #[test]
    fn sanitize_clamps_max_values() {
        let mut c = Config {
            parallel_downloads: 100,
            timeout_seconds: 10000,
            update_check_interval_hours: 20000,
            schedule: ScheduleConfig { interval_hours: 20000, ..Default::default() },
            ..Default::default()
        };

        ConfigManager::sanitize(&mut c);

        assert_eq!(c.parallel_downloads, 32);
        assert_eq!(c.timeout_seconds, 3600);
        assert_eq!(c.update_check_interval_hours, 8760);
        assert_eq!(c.schedule.interval_hours, 8760);
    }

    #[test]
    fn sanitize_makes_paths_absolute() {
        let mut c = Config {
            install_dir: PathBuf::from("relative/install"),
            download_dir: PathBuf::from("relative/download"),
            shim_dir: PathBuf::from("relative/shim"),
            ..Default::default()
        };

        ConfigManager::sanitize(&mut c);

        assert!(c.install_dir.is_absolute());
        assert!(c.download_dir.is_absolute());
        assert!(c.shim_dir.is_absolute());
    }
}
