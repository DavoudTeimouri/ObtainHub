use crate::core::{ConfigManager, StateManager};
use anyhow::{Context, Result};
use minreq;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{debug, info};

/// Registry release information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistryRelease {
    #[serde(default = "default_tag_name")]
    pub tag_name: String,
    pub name: Option<String>,
    pub prerelease: bool,
    pub draft: bool,
    pub assets: Vec<RegistryAsset>,
    pub zipball_url: String,
    pub tarball_url: String,
}

fn default_tag_name() -> String {
    "unknown".to_string()
}

/// Registry asset
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistryAsset {
    pub name: String,
    pub browser_download_url: String,
    pub size: u64,
    pub content_type: Option<String>,
}

/// Registry type enumeration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum Registry {
    GitHub(GitHubRegistry),
    CratesIo(CratesIoRegistry),
    Generic(GenericHttpRegistry),
}

impl Registry {
    pub fn registry_type(&self) -> &'static str {
        match self {
            Registry::GitHub(_) => "github",
            Registry::CratesIo(_) => "crates-io",
            Registry::Generic(_) => "generic",
        }
    }
    
    pub async fn fetch_latest_release(
        &self,
        package_name: &str,
        token: Option<&str>,
    ) -> Result<RegistryRelease> {
        match self {
            Registry::GitHub(r) => r.fetch_latest_release(package_name, token).await,
            Registry::CratesIo(r) => r.fetch_latest_release(package_name, token).await,
            Registry::Generic(r) => r.fetch_latest_release(package_name, token).await,
        }
    }
    
    pub async fn fetch_release_by_tag(
        &self,
        package_name: &str,
        tag: &str,
        token: Option<&str>,
    ) -> Result<RegistryRelease> {
        match self {
            Registry::GitHub(r) => r.fetch_release_by_tag(package_name, tag, token).await,
            Registry::CratesIo(r) => r.fetch_release_by_tag(package_name, tag, token).await,
            Registry::Generic(r) => r.fetch_release_by_tag(package_name, tag, token).await,
        }
    }
    
    pub fn select_asset(&self, release: &RegistryRelease) -> Result<RegistryAsset> {
        match self {
            Registry::GitHub(r) => r.select_asset(release),
            Registry::CratesIo(r) => r.select_asset(release),
            Registry::Generic(r) => r.select_asset(release),
        }
    }
    
    pub async fn download_asset(
        &self,
        asset: &RegistryAsset,
        dest: &std::path::Path,
        token: Option<&str>,
        config: &ConfigManager,
    ) -> Result<()> {
        match self {
            Registry::GitHub(r) => r.download_asset(asset, dest, token, config).await,
            Registry::CratesIo(r) => r.download_asset(asset, dest, token, config).await,
            Registry::Generic(r) => r.download_asset(asset, dest, token, config).await,
        }
    }
}

/// GitHub registry implementation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitHubRegistry;

impl GitHubRegistry {
    pub fn new() -> Self {
        Self
    }
    
    fn get_repo_from_package(package_name: &str) -> String {
        package_name.to_string()
    }
}

impl GitHubRegistry {
    pub async fn fetch_latest_release(
        &self,
        package_name: &str,
        token: Option<&str>,
    ) -> Result<RegistryRelease> {
        let repo = Self::get_repo_from_package(package_name);
        let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
        let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {}", token));
        }
        let resp: RegistryRelease = req.send()?.json()?;
        Ok(resp)
    }
    
    pub async fn fetch_release_by_tag(
        &self,
        package_name: &str,
        tag: &str,
        token: Option<&str>,
    ) -> Result<RegistryRelease> {
        let repo = Self::get_repo_from_package(package_name);
        let url = format!("https://api.github.com/repos/{}/releases/tags/{}", repo, tag);
        let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {}", token));
        }
        let resp: RegistryRelease = req.send()?.json()?;
        Ok(resp)
    }
    
    pub fn select_asset(&self, release: &RegistryRelease) -> Result<RegistryAsset> {
        let target_os = std::env::consts::OS;
        let target_arch = std::env::consts::ARCH;
        
        for asset in &release.assets {
            let name = asset.name.to_lowercase();
            if (target_os == "windows" && (name.ends_with(".zip") || name.ends_with(".exe"))) ||
               (target_os == "linux" && (name.ends_with(".tar.gz") || name.ends_with(".tar.xz") || name.ends_with(".AppImage"))) ||
               (target_os == "macos" && (name.ends_with(".tar.gz") || name.ends_with(".dmg") || name.ends_with(".zip"))) {
                if name.contains(target_arch) || name.contains("x86_64") || name.contains("amd64") || name.contains("aarch64") || name.contains("arm64") {
                    return Ok(asset.clone());
                }
            }
        }
        
        for asset in &release.assets {
            let name = asset.name.to_lowercase();
            if name.ends_with(".zip") || name.ends_with(".tar.gz") || name.ends_with(".tar.xz") || name.ends_with(".tgz") {
                return Ok(asset.clone());
            }
        }
        
        let zipball_asset = RegistryAsset {
            name: format!("{}.zip", release.tag_name),
            browser_download_url: release.zipball_url.clone(),
            size: 0,
            content_type: Some("application/zip".to_string()),
        };
        Ok(zipball_asset)
    }
    
    pub async fn download_asset(
        &self,
        asset: &RegistryAsset,
        dest: &std::path::Path,
        token: Option<&str>,
        config: &ConfigManager,
    ) -> Result<()> {
        let mut req = minreq::get(&asset.browser_download_url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {}", token));
        }
        
        let response = req
            .with_timeout(config.get().timeout_seconds as u64)
            .send()
            .context("Failed to send request")?;
        
        let total_size = response
            .headers
            .get("content-length")
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(0);
        
        let pb = indicatif::ProgressBar::new(total_size);
        pb.set_style(
            indicatif::ProgressStyle::default_bar()
                .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
                .unwrap()
                .progress_chars("#>-"),
        );
        pb.set_message(asset.name.clone());
        
        let bytes = response.as_bytes();
        
        for chunk in bytes.chunks(8192) {
            pb.inc(chunk.len() as u64);
        }
        
        pb.finish_with_message(format!("Downloaded {}", asset.name));
        std::fs::write(dest, bytes).context("Failed to write download")?;
        Ok(())
    }
}

/// Crates.io registry implementation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CratesIoRegistry;

impl CratesIoRegistry {
    pub fn new() -> Self {
        Self
    }
}

impl CratesIoRegistry {
    pub async fn fetch_latest_release(
        &self,
        package_name: &str,
        _token: Option<&str>,
    ) -> Result<RegistryRelease> {
        let url = format!("https://crates.io/api/v1/crates/{}", package_name);
        let resp = minreq::get(&url)
            .with_header("User-Agent", "ObtainHub/3.0.0")
            .send()?;
        
        #[derive(Deserialize)]
        struct CrateResponse {
            crate_info: CrateInfo,
            versions: Vec<CrateVersion>,
        }
        
        #[derive(Deserialize)]
        struct CrateInfo {
            name: String,
            max_version: String,
        }
        
        #[derive(Deserialize)]
        struct CrateVersion {
            num: String,
            downloads: Vec<CrateDownload>,
        }
        
        #[derive(Deserialize)]
        struct CrateDownload {
            url: String,
        }
        
        let resp: CrateResponse = resp.json()?;
        
        let latest_version = &resp.versions.iter()
            .find(|v| v.num == resp.crate_info.max_version)
            .context("Version not found")?;
        
        let download_url = latest_version.downloads.first()
            .map(|d| d.url.clone())
            .unwrap_or_else(|| format!("https://crates.io/api/v1/crates/{}/{}/download", package_name, resp.crate_info.max_version));
        
        let asset = RegistryAsset {
            name: format!("{}-{}.crate", package_name, resp.crate_info.max_version),
            browser_download_url: download_url,
            size: 0,
            content_type: Some("application/octet-stream".to_string()),
        };
        
        Ok(RegistryRelease {
            tag_name: format!("v{}", resp.crate_info.max_version),
            name: Some(package_name.to_string()),
            prerelease: false,
            draft: false,
            assets: vec![asset],
            zipball_url: String::new(),
            tarball_url: String::new(),
        })
    }
    
    pub async fn fetch_release_by_tag(
        &self,
        package_name: &str,
        tag: &str,
        _token: Option<&str>,
    ) -> Result<RegistryRelease> {
        let version = tag.trim_start_matches('v');
        let url = format!("https://crates.io/api/v1/crates/{}/{}", package_name, version);
        let resp = minreq::get(&url)
            .with_header("User-Agent", "ObtainHub/3.0.0")
            .send()?;
        
        #[derive(Deserialize)]
        struct VersionResponse {
            version: CrateVersionDetail,
        }
        
        #[derive(Deserialize)]
        struct CrateVersionDetail {
            num: String,
            downloads: Vec<CrateDownload>,
        }
        
        #[derive(Deserialize)]
        struct CrateDownload {
            url: String,
        }
        
        let resp: VersionResponse = resp.json()?;
        
        let download_url = resp.version.downloads.first()
            .map(|d| d.url.clone())
            .unwrap_or_else(|| format!("https://crates.io/api/v1/crates/{}/{}/download", package_name, version));
        
        let asset = RegistryAsset {
            name: format!("{}-{}.crate", package_name, version),
            browser_download_url: download_url,
            size: 0,
            content_type: Some("application/octet-stream".to_string()),
        };
        
        Ok(RegistryRelease {
            tag_name: format!("v{}", version),
            name: Some(package_name.to_string()),
            prerelease: false,
            draft: false,
            assets: vec![asset],
            zipball_url: String::new(),
            tarball_url: String::new(),
        })
    }
    
    pub fn select_asset(&self, release: &RegistryRelease) -> Result<RegistryAsset> {
        release.assets.first().cloned()
            .ok_or_else(|| anyhow::anyhow!("No assets available"))
    }
    
    pub async fn download_asset(
        &self,
        asset: &RegistryAsset,
        dest: &std::path::Path,
        _token: Option<&str>,
        config: &ConfigManager,
    ) -> Result<()> {
        let mut req = minreq::get(&asset.browser_download_url).with_header("User-Agent", "ObtainHub/3.0.0");
        
        let response = req
            .with_timeout(config.get().timeout_seconds as u64)
            .send()
            .context("Failed to send request")?;
        
        let total_size = response
            .headers
            .get("content-length")
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(0);
        
        let pb = indicatif::ProgressBar::new(total_size);
        pb.set_style(
            indicatif::ProgressStyle::default_bar()
                .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
                .unwrap()
                .progress_chars("#>-"),
        );
        pb.set_message(asset.name.clone());
        
        let bytes = response.as_bytes();
        
        for chunk in bytes.chunks(8192) {
            pb.inc(chunk.len() as u64);
        }
        
        pb.finish_with_message(format!("Downloaded {}", asset.name));
        std::fs::write(dest, bytes).context("Failed to write download")?;
        Ok(())
    }
}

/// Generic HTTP registry for custom sources
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenericHttpRegistry {
    base_url: String,
}

impl GenericHttpRegistry {
    pub fn new(base_url: String) -> Self {
        Self { base_url }
    }
}

impl GenericHttpRegistry {
    pub async fn fetch_latest_release(
        &self,
        package_name: &str,
        token: Option<&str>,
    ) -> Result<RegistryRelease> {
        let url = format!("{}/packages/{}/latest", self.base_url, package_name);
        let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {}", token));
        }
        let resp: RegistryRelease = req.send()?.json()?;
        Ok(resp)
    }
    
    pub async fn fetch_release_by_tag(
        &self,
        package_name: &str,
        tag: &str,
        token: Option<&str>,
    ) -> Result<RegistryRelease> {
        let url = format!("{}/packages/{}/versions/{}", self.base_url, package_name, tag);
        let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {}", token));
        }
        let resp: RegistryRelease = req.send()?.json()?;
        Ok(resp)
    }
    
    pub fn select_asset(&self, release: &RegistryRelease) -> Result<RegistryAsset> {
        release.assets.first().cloned()
            .ok_or_else(|| anyhow::anyhow!("No assets available"))
    }
    
    pub async fn download_asset(
        &self,
        asset: &RegistryAsset,
        dest: &std::path::Path,
        token: Option<&str>,
        config: &ConfigManager,
    ) -> Result<()> {
        let mut req = minreq::get(&asset.browser_download_url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {}", token));
        }
        
        let response = req
            .with_timeout(config.get().timeout_seconds as u64)
            .send()
            .context("Failed to send request")?;
        
        let total_size = response
            .headers
            .get("content-length")
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(0);
        
        let pb = indicatif::ProgressBar::new(total_size);
        pb.set_style(
            indicatif::ProgressStyle::default_bar()
                .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
                .unwrap()
                .progress_chars("#>-"),
        );
        pb.set_message(asset.name.clone());
        
        let bytes = response.as_bytes();
        
        for chunk in bytes.chunks(8192) {
            pb.inc(chunk.len() as u64);
        }
        
        pb.finish_with_message(format!("Downloaded {}", asset.name));
        std::fs::write(dest, bytes).context("Failed to write download")?;
        Ok(())
    }
}

/// Factory for creating registry instances
pub fn create_registry(source: &crate::core::config::ManifestSource) -> Registry {
    match source.registry_type.as_str() {
        "github" => Registry::GitHub(GitHubRegistry::new()),
        "github-packages" => Registry::GitHub(GitHubRegistry::new()),
        "crates-io" => Registry::CratesIo(CratesIoRegistry::new()),
        "generic" => Registry::Generic(GenericHttpRegistry::new(source.url.clone())),
        _ => Registry::Generic(GenericHttpRegistry::new(source.url.clone())),
    }
}