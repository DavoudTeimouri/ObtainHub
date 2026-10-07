use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use dirs;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct State {
    pub installed: HashMap<String, InstalledRepo>,
    pub last_update_check: Option<chrono::DateTime<chrono::Utc>>,
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstalledRepo {
    pub repo: String,
    pub version: String,
    pub install_path: PathBuf,
    pub installed_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: Option<chrono::DateTime<chrono::Utc>>,
    pub checksum: Option<String>,
    pub metadata: serde_json::Value,
}

pub struct StateManager {
    state: State,
    state_path: PathBuf,
}

impl StateManager {
    pub fn new() -> Result<Self> {
        let state_dir = dirs::data_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("ObtainHub");
        
        std::fs::create_dir_all(&state_dir)?;
        
        let state_path = state_dir.join("state.json");
        
        let state = if state_path.exists() {
            let content = std::fs::read_to_string(&state_path)?;
            serde_json::from_str(&content)?
        } else {
            State::default()
        };
        
        Ok(Self { state, state_path })
    }
    
    pub fn get(&self) -> &State {
        &self.state
    }
    
    pub fn get_mut(&mut self) -> &mut State {
        &mut self.state
    }
    
    pub fn save(&self) -> Result<()> {
        let content = serde_json::to_string_pretty(&self.state)?;
        // Atomic write
        let tmp_path = self.state_path.with_extension("tmp");
        std::fs::write(&tmp_path, content)?;
        std::fs::rename(tmp_path, &self.state_path)?;
        Ok(())
    }
    
    pub fn add_installed(&mut self, repo: InstalledRepo) {
        self.state.installed.insert(repo.repo.clone(), repo);
    }
    
    pub fn remove_installed(&mut self, repo: &str) -> Option<InstalledRepo> {
        self.state.installed.remove(repo)
    }
    
    pub fn get_installed(&self, repo: &str) -> Option<&InstalledRepo> {
        self.state.installed.get(repo)
    }
    
    pub fn list_installed(&self) -> Vec<&InstalledRepo> {
        self.state.installed.values().collect()
    }
    
    pub fn path(&self) -> &PathBuf {
        &self.state_path
    }
    
    pub fn get_all_apps(&self) -> Vec<&InstalledRepo> {
        self.state.installed.values().collect()
    }

    pub fn clear(&mut self) -> Result<()> {
        self.state.installed.clear();
        self.state.last_update_check = None;
        self.state.metadata.clear();
        self.save()
    }

    pub fn repair(&mut self) -> Result<()> {
        // Ensure state directory exists
        if let Some(parent) = self.state_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        // Save to repair any corruption
        self.save()
    }
}