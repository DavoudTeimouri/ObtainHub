pub mod config;
pub mod state;
pub mod logger;
pub mod assets;
pub mod registries;
pub mod winreg;
pub mod elevate;
pub mod credentials;
pub mod cache;

pub use config::ConfigManager;
pub use state::{normalize_version, StateManager};
pub use winreg::{scan_uninstall_entries, detect_install_change, find_entry_for_repo};
pub use elevate::{run_installer, run_uninstaller};
