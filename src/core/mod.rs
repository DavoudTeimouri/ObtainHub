pub mod config;
pub mod state;
pub mod logger;
pub mod assets;
pub mod registries;
pub mod winreg;
pub mod elevate;

pub use config::ConfigManager;
pub use state::StateManager;
pub use logger::init as init_logger;
pub use winreg::{scan_uninstall_entries, detect_install_change, UninstallEntry};
pub use elevate::{run_elevated, run_installer, run_uninstaller};
pub use assets::{
    download_with_progress, verify_checksum, calculate_sha256_bytes, extract_archive,
    download_verify_extract,
};
pub use registries::{
    Registry, RegistryRelease, RegistryAsset,
    GitHubRegistry, CratesIoRegistry, GenericHttpRegistry, create_registry,
};