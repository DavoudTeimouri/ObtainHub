use clap::{Parser, Subcommand, Args};
use clap_complete::Shell;

#[derive(Parser, Debug)]
#[command(
    name = "ohub",
    version,
    long_version = concat!(
        env!("CARGO_PKG_VERSION"),
        "\nA Windows app installer and manager, driven by GitHub releases.",
        "\n",
        "\nRepository:  ", env!("CARGO_PKG_REPOSITORY"),
        "\nLicense:     ", env!("CARGO_PKG_LICENSE"),
        "\nAuthor:      ", env!("CARGO_PKG_AUTHORS"),
        "\nPlatform:    Windows 10+ (x86_64)",
        "\nBuilt:       ", env!("VERGEN_BUILD_TIMESTAMP"),
        "\nRust:        ", env!("VERGEN_RUSTC_SEMVER"),
        "\n",
        "\nDocs:        https://github.com/DavoudTeimouri/ObtainHub#readme",
        "\nInstall:     ObtainHub-Setup.exe (or ObtainHub.msi for managed machines)",
        "\nEvery command has examples: ohub <command> --help",
    ),
    about = "ObtainHub - GitHub repository search and management CLI",
    long_about = "Search, install, and manage GitHub repositories from the command line.\n\nRepository: https://github.com/DavoudTeimouri/ObtainHub"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
    
    /// Enable verbose logging
    #[arg(short, long, global = true)]
    pub verbose: bool,

    /// Disable the coloured progress bar
    #[arg(long, global = true)]
    pub no_color: bool,
    
    /// Output format
    #[arg(short, long, global = true, value_enum, default_value = "table")]
    pub format: OutputFormat,
}

#[derive(Debug, Clone, Copy, clap::ValueEnum)]
pub enum OutputFormat {
    Table,
    Json,
    Yaml,
}


// Examples shown after each command's options. Kept in one place so the
// help text is easy to review and change without hunting through the
// argument structs.

const EX_SEARCH: &str = "\
Examples:
  ohub search firefox
  ohub search \"image viewer\" --min-stars 100 --language rust
  ohub search notepad --sort-stars --limit 5";

const EX_INSTALL: &str = "\
Examples:
  ohub install firefox
  ohub install owner/repo --tag v1.2.3
  ohub install owner/repo --file C:\\Downloads\\app.zip
  ohub install --url https://example.com/app.zip owner/repo";

const EX_CHECK: &str = "\
Examples:
  ohub check
  ohub check owner/repo --notes
  ohub check --outdated-only --dry-run";

const EX_LIST: &str = "\
Examples:
  ohub list
  ohub list --detail
  ohub list --status outdated";

const EX_UPDATE: &str = "\
Examples:
  ohub update
  ohub update owner/repo
  ohub update --dry-run";

const EX_UNINSTALL: &str = "\
Examples:
  ohub uninstall owner/repo
  ohub uninstall owner/repo --purge --yes";

const EX_REMOVE: &str = "\
Examples:
  ohub remove owner/repo
  ohub remove owner/repo --dry-run";

const EX_ADD: &str = "\
Examples:
  ohub add owner/repo
  ohub add owner/repo --name myapp
  ohub add C:\\Tools\\myapp --add-type folder";

const EX_SOURCE: &str = "\
Examples:
  ohub source list
  ohub source add mysource https://example.com/manifest.json
  ohub source verify mysource";

const EX_SELF_UNINSTALL: &str = "\
Examples:
  ohub self-uninstall --backup D:\\ohub-backup.zip
  ohub self-uninstall --yes";

const EX_SCHEDULE: &str = "\
Examples:
  ohub schedule enable
  ohub schedule status
  ohub schedule run";

const EX_GROUP: &str = "\
Examples:
  ohub group add work firefox notepad
  ohub group install work
  ohub group list";

const EX_SHIM: &str = "\
Examples:
  ohub shim add myapp
  ohub shim list
  ohub shim path";

const EX_STATE: &str = "\
Examples:
  ohub state export D:\\ohub-state.json
  ohub state import D:\\ohub-state.json --dry-run
  ohub state validate";

const EX_APPS: &str = "\
Examples:
  ohub apps backup -a myapp -a notepad -o D:\\apps.zip
  ohub apps restore -i D:\\apps.zip --dry-run";

const EX_CLEANUP: &str = "\
Examples:
  ohub cleanup all --dry-run
  ohub cleanup downloads --force";

const EX_TUI: &str = "\
Examples:
  ohub tui
  ohub tui --check-deps";

const EX_CONFIG: &str = "\
Examples:
  ohub config show
  ohub config set parallel_downloads 8
  ohub config auth
  ohub config path";

const EX_BACKUP: &str = "\
Examples:
  ohub backup -o D:\\ohub-backup.zip
  ohub backup --include-repos -o D:\\ohub-full.zip";

const EX_RESTORE: &str = "\
Examples:
  ohub restore D:\\ohub-backup.zip --config --state
  ohub restore D:\\ohub-full.zip --repos
  ohub restore D:\\ohub-backup.zip --config --target-config D:\\tmp";

const EX_SELF_UPDATE: &str = "\
Examples:
  ohub self-update --check-only
  ohub self-update
  ohub self-update --prerelease";

const EX_ROLLBACK: &str = "\
Examples:
  ohub rollback owner/repo
  ohub rollback owner/repo --yes";

const EX_COMPLETION: &str = "\
Examples:
  ohub completion powershell
  ohub completion bash";

const EX_DOCTOR: &str = "\
Examples:
  ohub doctor
  ohub doctor --fix";

const EX_INFO: &str = "\
Examples:
  ohub info owner/repo";

const EX_RESET: &str = "\
Examples:
  ohub reset --backup D:\\ohub-state.zip
  ohub reset --keep-token";

#[derive(Subcommand, Debug)]
pub enum Commands {
    /// Search GitHub repositories
    Search(SearchArgs),
    
    /// Install a repository
    Install(InstallArgs),
    
    /// Check for updates to installed repositories
    Check(CheckArgs),
    
    /// List installed repositories
    List(ListArgs),
    
    /// Update installed repositories
    Update(UpdateArgs),
    
    /// Uninstall a repository
    Uninstall(UninstallArgs),

    /// Remove a repository from management (keep files)
    Remove(RemoveArgs),

    /// Add a repository to management without installing
    Add(AddArgs),

    /// Manage custom sources
    Source(SourceArgs),

    /// Completely remove ohub from the system
    SelfUninstall(SelfUninstallArgs),

    /// Manage scheduled background checks
    Schedule(ScheduleArgs),

    /// Manage app groups/profiles
    Group(GroupArgs),

    /// Manage portable shims for folder/zip apps
    Shim(ShimArgs),

    /// Export/import ohub state
    State(StateArgs),

    /// Backup/restore application folders
    Apps(AppsArgs),

    /// Clean up leftover files and tasks
    Cleanup(CleanupArgs),
    
    /// Launch Textual User Interface
    Tui(TuiArgs),
    
    /// Manage configuration
    Config(ConfigArgs),
    
    /// Backup installed repositories and config
    Backup(BackupArgs),
    
    /// Restore from backup
    Restore(RestoreArgs),
    
    /// Update ohub itself
        SelfUpdate(SelfUpdateArgs),

        /// Rollback a repository to its previous version
        Rollback(RollbackArgs),

        /// Generate shell completions
        Completion(CompletionArgs),
    
    /// Diagnose installation issues
    Doctor(DoctorArgs),

    /// Show detailed info about a repository
    Info(InfoArgs),

    /// Reset ohub state and configuration
    Reset(ResetArgs),
}

#[derive(Args, Debug)]
#[command(after_help = EX_SEARCH)]
pub struct SearchArgs {
    /// Search query
    #[arg(value_name = "QUERY")]
    pub query: String,

    /// Minimum stars filter
    #[arg(long, default_value = "0")]
    pub min_stars: u32,

    /// Only show actively maintained repos (updated within 1 year)
    #[arg(long)]
    pub active_only: bool,

    /// Sort by stars (default: best match)
    #[arg(long)]
    pub sort_stars: bool,

    /// Maximum results
    #[arg(long, default_value = "20")]
    pub limit: usize,

    /// Language filter
    #[arg(long)]
    pub language: Option<String>,

    /// Dry run - show query without executing
    #[arg(long)]
    pub dry_run: bool,

    /// Page number for pagination (1-indexed)
    #[arg(long, default_value = "1")]
    pub page: usize,

    /// Results per page (max 100)
    #[arg(long, default_value = "30")]
    pub per_page: usize,
}

#[derive(Args, Debug)]
#[command(after_help = EX_INSTALL)]
pub struct InstallArgs {
    /// Repository to install (owner/repo)
    #[arg(value_name = "REPO")]
    pub repo: String,

    /// Specific version/tag to install
    #[arg(long)]
    pub version: Option<String>,
    
    /// Specific release tag to install
    #[arg(long)]
    pub tag: Option<String>,
    
    /// Allow prerelease versions
    #[arg(long)]
    pub prerelease: bool,
    
    /// Force reinstall if already installed
    #[arg(long)]
    pub force: bool,
    
    /// Only download, don't install
    #[arg(long)]
    pub download_only: bool,
    
    /// Skip dependency checks
    #[arg(long)]
    pub skip_deps: bool,

    /// HTTP request timeout in seconds (10-300)
    #[arg(long, value_parser = clap::value_parser!(u64).range(10..=300))]
    pub timeout: Option<u64>,

    /// Architecture to select
    #[arg(long, value_enum, default_value = "auto")]
    pub arch: Arch,
    
    /// Auto-confirm prompts
    #[arg(short, long)]
    pub yes: bool,
    
    /// Forget saved asset/repo choice for this app so prompts re-appear
    #[arg(long)]
    pub reset: bool,
    
    /// Launch the installer visibly and let you drive it
    #[arg(long)]
    pub interactive: bool,
    
    /// Dry run - show what would be installed
    #[arg(long)]
    pub dry_run: bool,

    /// Install from local file (zip, tar.gz, tar.xz)
    #[arg(long)]
    pub file: Option<String>,

    /// Install from direct URL
    #[arg(long)]
    pub url: Option<String>,

    /// Declare dependencies (owner/repo format, comma-separated or repeat flag)
    #[arg(long, value_delimiter = ',')]
    pub dependencies: Vec<String>,
}

#[derive(Clone, Debug, clap::ValueEnum)]
pub enum Arch {
    Auto,
    X64,
    Arm64,
    X86,
}

#[derive(Copy, Clone, PartialEq, Eq, clap::ValueEnum, Debug)]
pub enum TokenSource {
    Auto,
    Keyring,
    Env,
    File,
    PlaintextKeyring,
}

#[derive(Args, Debug)]
#[command(after_help = EX_CHECK)]
pub struct CheckArgs {
    /// Check specific repository (default: all)
    #[arg(value_name = "REPO")]
    pub repo: Option<String>,

    /// Only show outdated
    #[arg(long)]
    pub outdated_only: bool,
    
    /// Include prerelease versions
    #[arg(long)]
    pub prerelease: bool,
    
    /// Auto-confirm prompts
    #[arg(short, long)]
    pub yes: bool,
    
    /// Re-check all unmanaged applications, ignoring previous choices
    #[arg(long)]
    pub all: bool,
    
    /// For unmanaged apps with no exact repo, offer candidate repositories by name to link
    #[arg(long)]
    pub candidates: bool,
    
    /// Forget saved asset/repo choices so prompts re-appear
    #[arg(long)]
    pub reset: bool,
    
    /// Architecture to select
    #[arg(long, value_enum, default_value = "auto")]
    pub arch: Arch,
    
    /// HTTP request timeout in seconds (10-300)
    #[arg(long, value_parser = clap::value_parser!(u64).range(10..=300))]
    pub timeout: Option<u64>,
    
    /// Show release notes for available updates
    #[arg(long)]
    pub notes: bool,
    
    /// Force check even if recent
        #[arg(long)]
        pub force: bool,

        /// Quiet mode - suppress non-error output
        #[arg(short, long)]
        pub quiet: bool,

        /// Dry run - show what would be done without making changes
        #[arg(long)]
        pub dry_run: bool,

        /// Append a run report to this file (scheduled runs leave a record behind)
        #[arg(long, value_name = "PATH")]
        pub log: Option<String>,
}

#[derive(Args, Debug)]
#[command(after_help = EX_LIST)]
pub struct ListArgs {
    /// Show detailed info
    #[arg(long)]
    pub detail: bool,
    
    /// Filter by status
    #[arg(long, value_enum)]
    pub status: Option<InstallStatus>,
}

#[derive(Debug, Clone, Copy, clap::ValueEnum)]
pub enum InstallStatus {
    Installed,
    Outdated,
    Error,
}

#[derive(Args, Debug)]
#[command(after_help = EX_UPDATE)]
pub struct UpdateArgs {
    /// Specific repository to update (default: all)
    #[arg(value_name = "REPO")]
    pub repo: Option<String>,

    /// Allow prerelease versions
    #[arg(long)]
    pub prerelease: bool,

    /// Dry run - show what would be updated
    #[arg(long)]
    pub dry_run: bool,

    /// Force update even if current
    #[arg(long)]
    pub force: bool,

    /// Skip dependency checks
    #[arg(long)]
    pub skip_deps: bool,

    /// HTTP request timeout in seconds (10-300)
    #[arg(long, value_parser = clap::value_parser!(u64).range(10..=300))]
    pub timeout: Option<u64>,

    /// Architecture to select
    #[arg(long, value_enum, default_value = "auto")]
    pub arch: Arch,
    
    /// Auto-confirm prompts
    #[arg(short, long)]
    pub yes: bool,

    /// Forget saved asset/repo choices so prompts re-appear
    #[arg(long)]
    pub reset: bool,

    /// Launch installers visibly and let you drive them
    #[arg(long)]
    pub interactive: bool,

    /// Show release notes for available updates
    #[arg(long)]
    pub notes: bool,

    /// Suppress progress output; print only the summary (for scheduled runs)
    #[arg(long, short)]
    pub quiet: bool,

    /// Append a run report to this file
    #[arg(long, value_name = "PATH")]
    pub log: Option<String>,
}

#[derive(Args, Debug)]
#[command(after_help = EX_ROLLBACK)]
pub struct RollbackArgs {
    /// Repository to rollback (owner/repo)
    #[arg(value_name = "REPO")]
    pub repo: String,

    /// Skip confirmation
    #[arg(long)]
    pub yes: bool,

    /// Suppress progress output; print only the result
    #[arg(long, short)]
    pub quiet: bool,

    /// Architecture to select
    #[arg(long, value_enum, default_value = "auto")]
    pub arch: Arch,
}

#[derive(Args, Debug)]
#[command(after_help = EX_UNINSTALL)]
pub struct UninstallArgs {
    /// Repository to uninstall (owner/repo)
    #[arg(value_name = "REPO")]
    pub repo: String,

    /// Remove config and data too
    #[arg(long)]
    pub purge: bool,

    /// Skip confirmation
    #[arg(long)]
    pub yes: bool,

    /// Force uninstall even if it's a dependency of other repos
    #[arg(long)]
    pub force: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_REMOVE)]
pub struct RemoveArgs {
    /// Repository to remove from management (owner/repo)
    #[arg(value_name = "REPO")]
    pub repo: String,
    
    /// Skip confirmation
    #[arg(long)]
    pub yes: bool,
    
    /// Dry run - show what would be removed
    #[arg(long)]
    pub dry_run: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_ADD)]
pub struct AddArgs {
    /// Repository to add (owner/repo)
    #[arg(value_name = "REPO")]
    pub repo: String,
    
    /// Custom name for the repository
    #[arg(long)]
    pub name: Option<String>,
    
    /// Install path (default: auto)
    #[arg(long)]
    pub path: Option<String>,
    
    /// Add mode: github repo, zip archive repo, or local folder
    #[arg(long, value_enum, default_value = "github")]
    pub add_type: AddType,
    
    /// Destination folder for extracted zip apps (default: install dir/portable/<name>)
    #[arg(long)]
    pub location: Option<String>,
    
    /// Also register the repo as a manifest source
    #[arg(long)]
    pub as_source: bool,
    
    /// (folder mode) scan the folder recursively for applications
    #[arg(long)]
    pub recursive: bool,
    
    /// (folder mode) link the folder app to a GitHub repo (owner/repo) for updates
    #[arg(long)]
    pub repo_arg: Option<String>,
    
    /// Skip confirmation
    #[arg(long)]
    pub yes: bool,
}

#[derive(Clone, Debug, clap::ValueEnum)]
pub enum AddType {
    Github,
    Zip,
    Folder,
}

#[derive(Args, Debug)]
#[command(after_help = EX_SOURCE)]
pub struct SourceArgs {
    #[command(subcommand)]
    pub action: SourceAction,
}

#[derive(Subcommand, Debug)]
// ponytail: `Add` carries more fields than the other variants, so the enum is
// 232 bytes. Boxing it would cost an allocation on every `ohub source add`;
// splitting the variants into separate subcommands is the upgrade path.
#[allow(clippy::large_enum_variant)]
pub enum SourceAction {
    /// List configured sources
    List,
    /// Add a custom source
    Add {
        name: String,
        url: String,
        #[arg(long, default_value = "github")]
        src_type: String,
        #[arg(long, default_value = "github")]
        registry_type: String,
        #[arg(long)]
        package_name: Option<String>,
        #[arg(long)]
        pre_install: Option<String>,
        #[arg(long)]
        post_install: Option<String>,
        #[arg(long)]
        pre_uninstall: Option<String>,
        #[arg(long)]
        post_uninstall: Option<String>,
        #[arg(long)]
        priority: Option<i32>,
        #[arg(long)]
        enabled: bool,
        #[arg(long)]
        auto_sync: bool,
    },
    /// Remove a source
    Remove { name: String },
    /// Verify a source
    Verify { name: String },
    /// Update a source
    Update { name: String },
    /// Enable a source
    Enable { name: String },
    /// Disable a source
    Disable { name: String },
}

#[derive(Args, Debug)]
#[command(after_help = EX_SELF_UNINSTALL)]
pub struct SelfUninstallArgs {
    /// Create backup zip before uninstalling
    #[arg(long)]
    pub backup: Option<String>,
    
    /// Include download folder in backup
    #[arg(long)]
    pub include_downloads: bool,
    
    /// Skip confirmation prompt
    #[arg(short, long)]
    pub yes: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_SCHEDULE)]
pub struct ScheduleArgs {
    #[command(subcommand)]
    pub action: ScheduleAction,
}

#[derive(Subcommand, Debug)]
pub enum ScheduleAction {
    /// Enable scheduled checks
    Enable,
    /// Disable scheduled checks
    Disable,
    /// Show schedule status
    Status,
    /// Run scheduled check now
    Run {
        #[arg(long)]
        prerelease: bool,
    },
}

#[derive(Args, Debug)]
#[command(after_help = EX_GROUP)]
pub struct GroupArgs {
    #[command(subcommand)]
    pub action: GroupAction,
}

#[derive(Subcommand, Debug)]
pub enum GroupAction {
    /// List all groups
    List,
    /// Create a group with apps
    Add { name: String, apps: Vec<String> },
    /// Remove apps from a group
    Remove { name: String, apps: Vec<String> },
    /// Delete a group entirely
    Delete { name: String },
    /// Install all apps in a group
    Install { name: String, #[arg(long)] prerelease: bool },
    /// Update all apps in a group
    Update { name: String, #[arg(long)] prerelease: bool },
    /// Check all apps in a group for updates
    Check { name: String, #[arg(long)] prerelease: bool },
    /// Uninstall all apps in a group
    Uninstall { name: String, #[arg(long)] force: bool },
}

#[derive(Args, Debug)]
#[command(after_help = EX_SHIM)]
pub struct ShimArgs {
    #[command(subcommand)]
    pub action: ShimAction,
}

#[derive(Subcommand, Debug)]
pub enum ShimAction {
    /// List all created shims
    List,
    /// Create a shim for a managed app
    Add { 
        app: String,
        #[arg(long)]
        name: Option<String>,
    },
    /// Remove a shim
    Remove { 
        app: String,
    },
    /// Show shim directory path
    Path,
}

#[derive(Args, Debug)]
#[command(after_help = EX_STATE)]
pub struct StateArgs {
    #[command(subcommand)]
    pub action: StateAction,
}

#[derive(Subcommand, Debug)]
pub enum StateAction {
    /// Export state to JSON file or stdout
    Export { file: Option<String> },
    /// Import state from JSON file
    Import { file: String, #[arg(long)] dry_run: bool },
    /// Validate state integrity
    Validate,
    /// Clean orphaned state entries
    Clean,
}

#[derive(Args, Debug)]
#[command(after_help = EX_APPS)]
pub struct AppsArgs {
    #[command(subcommand)]
    pub action: AppsAction,
}

#[derive(Subcommand, Debug)]
pub enum AppsAction {
    /// Backup application folder(s) to zip
    Backup {
        #[arg(short, long, num_args = 0..)]
        app: Vec<String>,
        
        #[arg(short, long)]
        output: String,
        
        #[arg(long)]
        include_downloads: bool,
    },
    /// Restore application folder(s) from zip
    Restore {
        #[arg(short, long, num_args = 0..)]
        app: Vec<String>,
        
        #[arg(short, long)]
        input: String,
        
        #[arg(long)]
        target_dir: Option<String>,
        
        #[arg(long)]
        dry_run: bool,
    },
}

#[derive(Args, Debug)]
#[command(after_help = EX_CLEANUP)]
pub struct CleanupArgs {
    #[command(subcommand)]
    pub action: CleanupAction,
}

#[derive(Subcommand, Debug)]
pub enum CleanupAction {
    /// Run all cleanup operations
    All {
        /// Dry run
        #[arg(long)]
        dry_run: bool,
        /// Force cleanup
        #[arg(long)]
        force: bool,
    },
    /// Clean up leftover scheduled tasks
    Tasks {
        /// Dry run
        #[arg(long)]
        dry_run: bool,
        /// Force cleanup
        #[arg(long)]
        force: bool,
    },
    /// Clean up incomplete downloads
    Downloads {
        /// Dry run
        #[arg(long)]
        dry_run: bool,
        /// Force cleanup
        #[arg(long)]
        force: bool,
    },
    /// Clean up old manifest cache entries
    Cache {
        /// Dry run
        #[arg(long)]
        dry_run: bool,
        /// Force cleanup
        #[arg(long)]
        force: bool,
    },
}

#[derive(Args, Debug)]
#[command(after_help = EX_TUI)]
pub struct TuiArgs {
    /// Check dependencies and exit
    #[arg(long)]
    pub check_deps: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_CONFIG)]
pub struct ConfigArgs {
    #[command(subcommand)]
    pub action: ConfigAction,
}

#[derive(Subcommand, Debug)]
pub enum ConfigAction {
    /// Show current configuration
    Show,
    /// Set a configuration value
    Set { key: String, value: String },
    /// Get a configuration value
    Get { key: String },
    /// Reset to defaults
    Reset,
    /// Edit in $EDITOR
    Edit,
    /// Show config and state file paths
    Path,
    /// Move config and state files to a directory
    Move { path: String },
    /// Repair corrupted config/state files
    Repair,
    /// Backup config and state to zip file
    Backup { file: String },
    /// Restore config and state from zip file
    Restore { file: String, #[arg(long)] force: bool },
    /// Show GitHub token source and protection status
    Auth {
        #[arg(long, value_enum, default_value = "auto")]
        token_source: TokenSource,
    },
}

#[derive(Args, Debug)]
#[command(after_help = EX_BACKUP)]
pub struct BackupArgs {
    /// Output file path
    #[arg(short, long)]
    pub output: Option<String>,
    
    /// Include installed repositories
    #[arg(long)]
    pub include_repos: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_RESTORE)]
pub struct RestoreArgs {
    /// Backup file to restore from
    #[arg(value_name = "FILE")]
    pub file: String,
    
    /// Restore configuration
    #[arg(long)]
    pub config: bool,
    
    /// Restore installed repository state
    #[arg(long)]
    pub state: bool,
    
    /// Restore repository archives
    #[arg(long)]
    pub repos: bool,

    /// Write the restored config.toml into this directory instead of the
    /// live config directory
    #[arg(long)]
    pub target_config: Option<String>,

    /// Write the restored state.json into this directory instead of the live
    /// state directory
    #[arg(long)]
    pub target_state: Option<String>,

    /// Force restore (overwrite existing)
    #[arg(long)]
    pub force: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_SELF_UPDATE)]
pub struct SelfUpdateArgs {
    /// Check only, don't install
    #[arg(long)]
    pub check_only: bool,
    
    /// Install pre-release versions
    #[arg(long)]
    pub prerelease: bool,
    
    /// Force update even if same version
    #[arg(long)]
    pub force: bool,
    
    /// Output as JSON
    #[arg(long)]
    pub json: bool,
    
    /// Suppress non-error output
    #[arg(long, short)]
    pub quiet: bool,
    
    /// Skip signature verification (not recommended for security)
    #[arg(long)]
    pub skip_signature: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_COMPLETION)]
pub struct CompletionArgs {
    /// Shell to generate completions for
    #[arg(value_enum)]
    pub shell: Shell,
}

#[derive(Args, Debug)]
#[command(after_help = EX_DOCTOR)]
pub struct DoctorArgs {
    /// Fix issues automatically
    #[arg(long)]
    pub fix: bool,

    /// Exit with a non-zero status when issues are found
    #[arg(long)]
    pub strict: bool,
}

#[derive(Args, Debug)]
#[command(after_help = EX_INFO)]
pub struct InfoArgs {
    /// Repository name (owner/repo)
    #[arg(value_name = "REPO")]
    pub repo: String,
}

#[derive(Args, Debug)]
#[command(after_help = EX_RESET)]
pub struct ResetArgs {
    /// Directory to backup state and config files
    #[arg(long)]
    pub backup: Option<String>,
    
    /// Keep the GitHub token in the config after reset
    #[arg(long)]
    pub keep_token: bool,
    
    /// Move the GitHub token to the specified file (removed from config)
    #[arg(long)]
    pub move_token: Option<String>,
}