pub mod config;
pub mod state;
pub mod logger;
pub mod assets;
pub mod registries;
pub mod winreg;
pub mod elevate;

pub use config::ConfigManager;
pub use state::StateManager;
pub use winreg::{scan_uninstall_entries, detect_install_change};
pub use elevate::{run_installer, run_uninstaller};
