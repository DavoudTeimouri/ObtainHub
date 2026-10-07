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
}

fn default_src_type() -> String { "github".to_string() }

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
    pub manifest_sources: Vec<ManifestSource>,
    
    #[serde(default)]
    pub schedule: ScheduleConfig,
    
    #[serde(default)]
    pub groups: HashMap<String, Vec<String>>,
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
            manifest_sources: Vec::new(),
            schedule: ScheduleConfig {
                enabled: false,
                interval_hours: 24,
                notify_on_update: true,
                run_on_startup: false,
                last_run: None,
            },
            groups: HashMap::new(),
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
        
        let config = if config_path.exists() {
            let content = std::fs::read_to_string(&config_path)?;
            toml::from_str(&content)?
        } else {
            Config::default()
        };
        
        Ok(Self { config, config_path })
    }
    
    pub fn get(&self) -> &Config {
        &self.config
    }
    
    pub fn get_mut(&mut self) -> &mut Config {
        &mut self.config
    }
    
    pub fn save(&self) -> Result<()> {
        let content = toml::to_string_pretty(&self.config)?;
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