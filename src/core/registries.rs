use crate::core::ConfigManager;
use crate::cli::Arch;
use anyhow::{Context, Result};
use minreq;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

/// The HTTP timeout for this run, in seconds.
///
/// `ohub <command> --timeout N` sets it; every request reads it from here, so
/// the flag reaches all of them without threading a parameter through every
/// signature. Set once from the config at start-up, overridden by the flag.
static REQUEST_TIMEOUT: AtomicU64 = AtomicU64::new(30);

/// Set the request timeout for this run. The last call wins.
pub fn set_request_timeout(seconds: u64) {
    REQUEST_TIMEOUT.store(seconds, Ordering::Relaxed);
}

/// The request timeout for this run.
pub fn request_timeout() -> Duration {
    Duration::from_secs(REQUEST_TIMEOUT.load(Ordering::Relaxed))
}

/// A GitHub API GET with this run's timeout already applied.
pub fn github_get(url: &str) -> minreq::Request {
    minreq::get(url)
        .with_timeout(request_timeout().as_secs())
        .with_header("User-Agent", "ObtainHub/3.0.0")
}

/// The asset-name tokens that identify an architecture.
///
/// `Auto` follows the machine the binary runs on. The list is deliberately
/// generous - release assets are named by many different projects.
pub fn arch_tokens(arch: &Arch) -> &'static [&'static str] {
    match arch {
        Arch::Auto => match std::env::consts::ARCH {
            "aarch64" => &["aarch64", "arm64"],
            "x86" => &["i686", "i386", "32-bit", "32bit"],
            _ => &["x86_64", "x64", "amd64", "64-bit", "64bit", "win64", "win-x64"],
        },
        Arch::X64 => &["x86_64", "x64", "amd64", "64-bit", "64bit", "win64", "win-x64"],
        Arch::Arm64 => &["aarch64", "arm64"],
        Arch::X86 => &["i686", "i386", "32-bit", "32bit", "x86"],
    }
}

/// Whether an asset name belongs to the requested architecture.
pub fn matches_arch(asset_name: &str, arch: &Arch) -> bool {
    let name = asset_name.to_lowercase();
    if matches!(arch, Arch::X86) {
        // "x86" is a substring of "x86_64" - a 64-bit name is not a 32-bit one.
        if name.contains("x86_64")
            || name.contains("x64")
            || name.contains("amd64")
            || name.contains("64-bit")
            || name.contains("64bit")
        {
            return false;
        }
    }
    arch_tokens(arch).iter().any(|t| name.contains(t))
}

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
    /// The published sha256 of the asset, when the registry has one.
    /// crates.io publishes it; GitHub keeps it in the release digest instead.
    #[serde(default)]
    pub checksum: Option<String>,
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
    
    pub fn select_asset(&self, release: &RegistryRelease, arch: &Arch) -> Result<RegistryAsset> {
        match self {
            Registry::GitHub(r) => r.select_asset(release, arch),
            Registry::CratesIo(r) => r.select_asset(release, arch),
            Registry::Generic(r) => r.select_asset(release, arch),
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
        let mut req = github_get(&url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
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
        let mut req = github_get(&url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }
        let resp: RegistryRelease = req.send()?.json()?;
        Ok(resp)
    }
    
    pub fn select_asset(&self, release: &RegistryRelease, arch: &Arch) -> Result<RegistryAsset> {
        let target_os = std::env::consts::OS;

        for asset in &release.assets {
            let name = asset.name.to_lowercase();
            let os_match = (target_os == "windows" && (name.ends_with(".zip") || name.ends_with(".exe")))
                || (target_os == "linux" && (name.ends_with(".tar.gz") || name.ends_with(".tar.xz") || name.ends_with(".AppImage")))
                || (target_os == "macos" && (name.ends_with(".tar.gz") || name.ends_with(".dmg") || name.ends_with(".zip")));
            if os_match && matches_arch(&name, arch) {
                return Ok(asset.clone());
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
        // With a bandwidth limit the file is fetched in chunks, one chunk per
        // second, so the transfer really is paced. `minreq` buffers the whole
        // body, so a single request cannot be slowed down.
        if let Some(limit_kbps) = config.get().download_bandwidth_limit {
            if limit_kbps > 0 && asset.size > 0 {
                return download_paced(asset, dest, token, limit_kbps).await;
            }
        }

        let mut req = github_get(&asset.browser_download_url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }

        let response = req
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
        let resp = github_get(&url)
            .send()?;
        
        #[derive(Deserialize)]
        struct CrateResponse {
            crate_info: CrateInfo,
            versions: Vec<CrateVersion>,
        }
        
        #[derive(Deserialize)]
        struct CrateInfo {
            #[allow(dead_code)]
            name: String,
            max_version: String,
        }
        
        #[derive(Deserialize)]
        struct CrateVersion {
            num: String,
            downloads: Vec<CrateDownload>,
            /// The sha256 of the .crate file, published by crates.io.
            #[serde(default)]
            checksum: Option<String>,
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
            checksum: latest_version.checksum.clone(),
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
        let resp = github_get(&url)
            .send()?;
        
        #[derive(Deserialize)]
        struct VersionResponse {
            version: CrateVersionDetail,
        }
        
        #[derive(Deserialize)]
        struct CrateVersionDetail {
            #[allow(dead_code)]
            num: String,
            downloads: Vec<CrateDownload>,
            /// The sha256 of the .crate file, published by crates.io.
            #[serde(default)]
            checksum: Option<String>,
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
            checksum: resp.version.checksum.clone(),
        })
    }
    
    pub fn select_asset(&self, release: &RegistryRelease, _arch: &Arch) -> Result<RegistryAsset> {
        release.assets.first().cloned()
            .ok_or_else(|| anyhow::anyhow!("No assets available"))
    }
    
    pub async fn download_asset(
        &self,
        asset: &RegistryAsset,
        dest: &std::path::Path,
        _token: Option<&str>,
        _config: &ConfigManager,
    ) -> Result<()> {
        let req = github_get(&asset.browser_download_url);
        
        let response = req
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
        let mut req = github_get(&url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
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
        let mut req = github_get(&url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }
        let resp: RegistryRelease = req.send()?.json()?;
        Ok(resp)
    }
    
    pub fn select_asset(&self, release: &RegistryRelease, _arch: &Arch) -> Result<RegistryAsset> {
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
        // With a bandwidth limit the file is fetched in chunks, one chunk per
        // second, so the transfer really is paced. `minreq` buffers the whole
        // body, so a single request cannot be slowed down.
        if let Some(limit_kbps) = config.get().download_bandwidth_limit {
            if limit_kbps > 0 && asset.size > 0 {
                return download_paced(asset, dest, token, limit_kbps).await;
            }
        }

        let mut req = github_get(&asset.browser_download_url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }

        let response = req
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

/// Download an asset at a limited rate.
///
/// The chunk is as many bytes as the limit allows in one second and the next
/// chunk starts a second later, so the average rate is the configured one. The
/// server has to support Range requests; without them the download cannot be
/// paced and the caller is told so.
async fn download_paced(
    asset: &RegistryAsset,
    dest: &std::path::Path,
    token: Option<&str>,
    limit_kbps: u64,
) -> Result<()> {
    let chunk_size = limit_kbps.saturating_mul(1024).max(1);
    let mut bytes: Vec<u8> = Vec::with_capacity(asset.size as usize);
    let mut start: u64 = 0;
    while start < asset.size {
        let end = (start + chunk_size - 1).min(asset.size - 1);
        let mut req = github_get(&asset.browser_download_url);
        req = req.with_header("Range", format!("bytes={start}-{end}"));
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }
        let response = req.send().context("Failed to send request")?;
        if response.status_code != 206 {
            anyhow::bail!(
                "The server does not support range requests, so the download cannot be rate limited"
            );
        }
        bytes.extend_from_slice(response.as_bytes());
        start = end + 1;
        if start < asset.size {
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        }
    }
    std::fs::write(dest, &bytes).context("Failed to write download")?;
    Ok(())
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

/// The release notes (body) of a repo's latest GitHub release.
///
/// Shared by the TUI and by the `check --notes` / `update --notes` flags. The
/// TUI used to own a private copy, which left the CLI flags with nothing to
/// call - they were accepted and did nothing.
pub async fn fetch_release_notes(
    repo: &str,
    token: Option<&str>,
    retry_config: &crate::utils::retry::RetryConfig,
) -> Result<Option<String>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let token_clone = token.map(|s| s.to_string());

    let result = crate::utils::retry::execute_with_retry(
        retry_config,
        || {
            let url = url.clone();
            let token = token_clone.clone();
            async move {
                let mut req = github_get(&url);
                if let Some(token) = token {
                    req = req.with_header("Authorization", format!("Bearer {}", token));
                }
                let resp = req.send()?;

                if resp.status_code == 404 {
                    return Ok(None);
                }
                if resp.status_code == 403 {
                    return Err(anyhow::anyhow!(
                        "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
                    ));
                }
                if !(resp.status_code >= 200 && resp.status_code < 300) {
                    return Err(anyhow::anyhow!("GitHub API error: {}", resp.status_code));
                }

                let body = resp.as_bytes().to_vec();
                if body.is_empty() {
                    return Ok(None);
                }
                let json: serde_json::Value = serde_json::from_slice(&body)?;
                Ok(json["body"].as_str().map(|s| s.to_string()))
            }
        },
        "fetch_release_notes",
    )
    .await?;

    Ok(result)
}

/// The release notes of a repo's latest release, as a printable block.
///
/// One place for the format, so `check --notes` and `update --notes` print
/// the same thing.
pub async fn release_notes_block(
    repo: &str,
    token: Option<&str>,
    retry_config: &crate::utils::retry::RetryConfig,
) -> String {
    format_release_notes(repo, fetch_release_notes(repo, token, retry_config).await)
}

/// Format a release-notes result for display.
pub fn format_release_notes(repo: &str, notes: Result<Option<String>>) -> String {
    match notes {
        Ok(Some(notes)) => format!("--- {repo} release notes ---\n{notes}\n"),
        Ok(None) => format!("{repo}: no release notes\n"),
        Err(e) => format!("{repo}: could not fetch the release notes: {e}\n"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn release_notes_cover_present_absent_and_failed() {
        assert_eq!(
            format_release_notes("a/b", Ok(Some("what changed".to_string()))),
            "--- a/b release notes ---\nwhat changed\n"
        );
        assert_eq!(
            format_release_notes("a/b", Ok(None)),
            "a/b: no release notes\n"
        );
        assert_eq!(
            format_release_notes("a/b", Err(anyhow::anyhow!("rate limited"))),
            "a/b: could not fetch the release notes: rate limited\n"
        );
    }

    #[test]
    fn arch_matching_separates_32_and_64_bit_names() {
        // "x86" is a substring of "x86_64", so a 64-bit name must not match x86.
        assert!(matches_arch("app-x86_64.zip", &Arch::X64));
        assert!(!matches_arch("app-x86_64.zip", &Arch::X86));
        assert!(matches_arch("app-x64.zip", &Arch::X64));
        assert!(!matches_arch("app-x64.zip", &Arch::X86));
        assert!(matches_arch("app-i686.zip", &Arch::X86));
        assert!(!matches_arch("app-i686.zip", &Arch::X64));
        assert!(matches_arch("app-arm64.zip", &Arch::Arm64));
        assert!(!matches_arch("app-arm64.zip", &Arch::X64));
        assert!(matches_arch("app-win64.zip", &Arch::X64));
    }
}