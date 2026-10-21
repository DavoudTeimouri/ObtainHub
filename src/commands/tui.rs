use crate::core::{ConfigManager, StateManager};
use crate::cli::{AddArgs, AddType, Arch, InstallArgs, RemoveArgs, TuiArgs, UpdateArgs};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use minreq;
use ratatui;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState, Paragraph, Wrap},
    Terminal,
};
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use serde::{Deserialize, Serialize};
use std::io;
use tracing::info;

pub async fn execute(args: TuiArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Starting TUI");

    if args.check_deps {
        println!("TUI dependencies check: OK (ratatui, crossterm available)");
        return Ok(());
    }

    let mut terminal = setup_terminal()?;
    let result = run_app(&mut terminal, config, state).await;
    restore_terminal(&mut terminal)?;

    if let Err(err) = result {
        eprintln!("TUI error: {}", err);
    }

    Ok(())
}

fn setup_terminal() -> Result<Terminal<CrosstermBackend<io::Stdout>>> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let terminal = Terminal::new(backend)?;
    Ok(terminal)
}

fn restore_terminal(terminal: &mut Terminal<CrosstermBackend<io::Stdout>>) -> Result<()> {
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;
    Ok(())
}

/// Which panel the TUI is showing.
#[derive(PartialEq, Eq, Clone, Copy)]
enum Mode {
    /// Managed app list
    List,
    /// Typing a GitHub search query
    SearchInput,
    /// Search results, pick one to add or install
    SearchResults,
}

struct App {
    apps: Vec<AppInfo>,
    list_state: ListState,
    selected_index: Option<usize>,
    should_quit: bool,
    status_message: String,
    show_help: bool,
    filter_text: String,
    filtered_indices: Vec<usize>,
    show_details: bool,
    mode: Mode,
    search_input: String,
    search_results: Vec<String>,
    search_state: ListState,
    retry_config: RetryConfig,
}

#[derive(Clone)]
struct AppInfo {
    name: String,
    current_version: String,
    latest_version: String,
    status: String,
    repo: String,
    install_path: String,
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRelease {
    tag_name: String,
}

async fn fetch_latest_release(repo: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Option<String>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let token_clone = token.map(|s| s.to_string());

    let result = execute_with_retry(retry_config, || {
        let url = url.clone();
        let token = token_clone.clone();
        async move {
            let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
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

            let release: GitHubRelease = resp.json()?;
            Ok(Some(release.tag_name))
        }
    }, "fetch_latest_release").await?;

    Ok(result)
}

async fn run_app<B: ratatui::backend::Backend>(
    terminal: &mut Terminal<B>,
    config: &ConfigManager,
    state: &mut StateManager,
) -> Result<()> {
    let mut app = App {
        apps: Vec::new(),
        list_state: ListState::default(),
        selected_index: None,
        should_quit: false,
        status_message: "Loading...".to_string(),
        show_help: false,
        filter_text: String::new(),
        filtered_indices: Vec::new(),
        show_details: false,
        mode: Mode::List,
        search_input: String::new(),
        search_results: Vec::new(),
        search_state: ListState::default(),
        retry_config: RetryConfig::from_config(config),
    };

    // Load initial data
    let retry_config_clone = app.retry_config.clone();
    app.load_apps(config, state, &retry_config_clone).await;

    while !app.should_quit {
        terminal.draw(|f| ui(f, &mut app))?;

        if let Event::Key(key) = event::read()? {
            if key.kind == KeyEventKind::Press {
                handle_key_event(key.code, &mut app, config, state).await?;
            }
        }
    }

    Ok(())
}

impl App {
    async fn load_apps(&mut self, config: &ConfigManager, state: &StateManager, retry_config: &RetryConfig) {
        self.status_message = "Loading apps...".to_string();

        let apps = state.get_all_apps();
        let token = config.get().github_token.as_deref();

        let mut app_infos = Vec::new();

        for app in apps {
            let repo_id = app.repo.clone();
            let (_owner, repo) = if let Some(idx) = repo_id.find('/') {
                (&repo_id[..idx], &repo_id[idx+1..])
            } else {
                ("", "")
            };

            let current_version = app.version.clone();

            // Fetch latest version from GitHub
            let latest_version = if repo_id.contains('/') && !repo_id.starts_with("folder/") {
                match fetch_latest_release(&repo_id, token, retry_config).await {
                    Ok(Some(latest)) => latest,
                    _ => "?".to_string(),
                }
            } else {
                "?".to_string()
            };

            let status = if current_version.is_empty() || current_version == "unknown" {
                "Unmanaged".to_string()
            } else if latest_version == "?" {
                "Unknown".to_string()
            } else if latest_version == current_version {
                "Current".to_string()
            } else {
                "Update".to_string()
            };

            app_infos.push(AppInfo {
                name: repo.to_string(),
                current_version,
                latest_version,
                status,
                repo: repo_id,
                install_path: app.install_path.display().to_string(),
            });
        }

        self.apps = app_infos;
        self.apply_filter();
        self.list_state.select(Some(0));
        self.selected_index = Some(0);
        self.status_message = format!("Loaded {} apps", self.apps.len());
    }

    fn apply_filter(&mut self) {
        self.filtered_indices.clear();
        if self.filter_text.is_empty() {
            self.filtered_indices = (0..self.apps.len()).collect();
        } else {
            let ft = self.filter_text.to_lowercase();
            for (i, app) in self.apps.iter().enumerate() {
                if app.name.to_lowercase().contains(&ft)
                    || app.repo.to_lowercase().contains(&ft)
                    || app.status.to_lowercase().contains(&ft)
                {
                    self.filtered_indices.push(i);
                }
            }
        }
        // Clamp selection to valid range
        if self.filtered_indices.is_empty() {
            self.list_state.select(None);
            self.selected_index = None;
        } else if let Some(sel) = self.selected_index {
            if sel >= self.filtered_indices.len() {
                self.list_state.select(Some(0));
                self.selected_index = Some(0);
            } else {
                self.list_state.select(Some(sel));
            }
        } else {
            self.list_state.select(Some(0));
            self.selected_index = Some(0);
        }
    }

    fn selected_app(&self) -> Option<&AppInfo> {
        self.selected_index
            .and_then(|i| self.filtered_indices.get(i))
            .and_then(|&idx| self.apps.get(idx))
    }
}

/// Typing a GitHub search query.
async fn handle_search_input(
    key: KeyCode,
    app: &mut App,
    config: &ConfigManager,
) -> Result<()> {
    match key {
        KeyCode::Esc => {
            app.mode = Mode::List;
            app.search_input.clear();
            app.status_message = "Search cancelled".to_string();
        }
        KeyCode::Backspace => {
            app.search_input.pop();
        }
        KeyCode::Enter => {
            let query = app.search_input.trim().to_string();
            if query.is_empty() {
                app.status_message = "Type a search query first".to_string();
                return Ok(());
            }
            app.status_message = format!("Searching GitHub for '{query}'...");
            let token = config.get().github_token.as_deref();
            match crate::commands::install::search_github_repos(&query, token, config).await {
                Ok(results) if !results.is_empty() => {
                    app.search_results = results;
                    app.search_state.select(Some(0));
                    app.mode = Mode::SearchResults;
                    app.status_message =
                        format!("{} results - 'Enter' add, 'i' install, 'Esc' back", app.search_results.len());
                }
                Ok(_) => {
                    app.status_message = format!("No results for '{query}'");
                }
                Err(e) => {
                    app.status_message = format!("Search failed: {e}");
                }
            }
        }
        KeyCode::Char(c) => {
            app.search_input.push(c);
        }
        _ => {}
    }
    Ok(())
}

/// Picking a repository from the search results.
async fn handle_search_results(
    key: KeyCode,
    app: &mut App,
    config: &ConfigManager,
    state: &mut StateManager,
) -> Result<()> {
    let selected = app
        .search_state
        .selected()
        .and_then(|i| app.search_results.get(i))
        .cloned();

    match key {
        KeyCode::Esc => {
            app.mode = Mode::List;
            app.status_message = "Search closed".to_string();
        }
        KeyCode::Char('j') | KeyCode::Down => {
            if let Some(sel) = app.search_state.selected() {
                if sel < app.search_results.len().saturating_sub(1) {
                    app.search_state.select(Some(sel + 1));
                }
            }
        }
        KeyCode::Char('k') | KeyCode::Up => {
            if let Some(sel) = app.search_state.selected() {
                if sel > 0 {
                    app.search_state.select(Some(sel - 1));
                }
            }
        }
        KeyCode::Enter | KeyCode::Char('a') => {
            let Some(repo) = selected else { return Ok(()) };
            app.status_message = format!("Adding {repo}...");
            let args = AddArgs {
                repo: repo.clone(),
                name: None,
                path: None,
                add_type: AddType::Github,
                location: None,
                as_source: false,
                recursive: false,
                repo_arg: None,
                yes: true,
            };
            match crate::commands::add::execute(args, config, state, &app.retry_config).await {
                Ok(()) => {
                    app.status_message = format!("Added {repo}");
                    app.mode = Mode::List;
                    let retry_config_clone = app.retry_config.clone();
                    app.load_apps(config, state, &retry_config_clone).await;
                }
                Err(e) => app.status_message = format!("Add failed: {e}"),
            }
        }
        KeyCode::Char('i') => {
            let Some(repo) = selected else { return Ok(()) };
            app.status_message = format!("Installing {repo}...");
            let args = InstallArgs {
                repo: repo.clone(),
                version: None,
                tag: None,
                prerelease: false,
                force: false,
                download_only: false,
                skip_deps: false,
                arch: Arch::Auto,
                yes: true,
                reset: false,
                interactive: false,
                dry_run: false,
                file: None,
                url: None,
                dependencies: Vec::new(),
            };
            match crate::commands::install::execute(args, config, state, &app.retry_config).await {
                Ok(()) => {
                    app.status_message = format!("Installed {repo}");
                    app.mode = Mode::List;
                    let retry_config_clone = app.retry_config.clone();
                    app.load_apps(config, state, &retry_config_clone).await;
                }
                Err(e) => app.status_message = format!("Install failed: {e}"),
            }
        }
        _ => {}
    }
    Ok(())
}

async fn handle_key_event(
    key: KeyCode,
    app: &mut App,
    config: &ConfigManager,
    state: &mut StateManager,
) -> Result<()> {
    // Search panels take over all keys while active.
    match app.mode {
        Mode::SearchInput => return handle_search_input(key, app, config).await,
        Mode::SearchResults => return handle_search_results(key, app, config, state).await,
        Mode::List => {}
    }

    match key {
        KeyCode::Char('q') | KeyCode::Esc => {
            if app.show_help {
                app.show_help = false;
            } else if app.show_details {
                app.show_details = false;
            } else if !app.filter_text.is_empty() {
                app.filter_text.clear();
                app.apply_filter();
            } else {
                app.should_quit = true;
            }
        }
        KeyCode::Char('?') | KeyCode::Char('h') | KeyCode::F(1) => {
            app.show_help = !app.show_help;
        }
        KeyCode::Char('j') | KeyCode::Down => {
            if let Some(selected) = app.list_state.selected() {
                if selected < app.filtered_indices.len().saturating_sub(1) {
                    app.list_state.select(Some(selected + 1));
                    app.selected_index = Some(selected + 1);
                }
            }
        }
        KeyCode::Char('k') | KeyCode::Up => {
            if let Some(selected) = app.list_state.selected() {
                if selected > 0 {
                    app.list_state.select(Some(selected - 1));
                    app.selected_index = Some(selected - 1);
                }
            }
        }
        KeyCode::Char('a') => {
            app.mode = Mode::SearchInput;
            app.search_input.clear();
            app.status_message = "Type a search query, Enter to search, Esc to cancel".to_string();
        }
        KeyCode::Char('r') => {
            app.status_message = "Refreshing...".to_string();
            let retry_config_clone = app.retry_config.clone();
            app.load_apps(config, state, &retry_config_clone).await;
            app.status_message = format!("Refreshed {} apps", app.apps.len());
        }
        KeyCode::Char('u') => {
            let selected = app.selected_app().cloned();
            if let Some(app_info) = selected {
                if app_info.status == "Update" || app_info.status == "Outdated" {
                    let repo_name = app_info.repo.clone();
                    let app_name = app_info.name.clone();
                    app.status_message = format!("Updating {app_name}...");
                    let update_args = UpdateArgs {
                        repo: Some(repo_name),
                        prerelease: false,
                        dry_run: false,
                        force: false,
                        skip_deps: false,
                        arch: crate::cli::Arch::Auto,
                        yes: false,
                        reset: false,
                        interactive: false,
                        notes: false,
                        // The TUI owns the screen - update output would corrupt it.
                        quiet: true,
                        log: None,
                    };
                    match crate::commands::update::execute(
                        update_args,
                        config,
                        state,
                        &app.retry_config,
                    )
                    .await
                    {
                        Ok(_) => {
                            app.status_message = format!("Updated {app_name}");
                            let retry_config_clone = app.retry_config.clone();
                            app.load_apps(config, state, &retry_config_clone).await;
                        }
                        Err(e) => {
                            app.status_message = format!("Update failed: {e}");
                        }
                    }
                } else {
                    app.status_message = format!("{} is already current", app_info.name);
                }
            }
        }
        KeyCode::Char('x') => {
            let selected = app.selected_app().cloned();
            if let Some(app_info) = selected {
                let repo_name = app_info.repo.clone();
                let app_name = app_info.name.clone();
                app.status_message = format!("Removing {app_name}...");
                match crate::commands::remove::execute(
                    RemoveArgs {
                        repo: repo_name,
                        yes: true,
                        dry_run: false,
                    },
                    config,
                    state,
                )
                .await
                {
                    Ok(_) => {
                        app.status_message = format!("Removed {app_name}");
                        let retry_config_clone = app.retry_config.clone();
                        app.load_apps(config, state, &retry_config_clone).await;
                    }
                    Err(e) => {
                        app.status_message = format!("Remove failed: {e}");
                    }
                }
            }
        }
        KeyCode::Char('/') => {
            app.filter_text = String::new();
            app.status_message = "Filter: ".to_string();
        }
        KeyCode::Char('c') => {
            app.filter_text.clear();
            app.apply_filter();
            app.status_message = "Filter cleared".to_string();
        }
        KeyCode::Enter => {
            app.show_details = !app.show_details;
        }
        KeyCode::Backspace => {
            if !app.filter_text.is_empty() {
                app.filter_text.pop();
                app.apply_filter();
            }
        }
        // Only handle char input when filtering. '/' and 'c' are handled by
        // their own arms above.
        KeyCode::Char(c) if !app.filter_text.is_empty() => {
            app.filter_text.push(c);
            app.apply_filter();
        }
        _ => {}
    }
    Ok(())
}

fn ui(f: &mut ratatui::Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(1)
        .constraints([
            Constraint::Length(3),
            Constraint::Length(3),
            Constraint::Min(0),
            Constraint::Length(3),
        ])
        .split(f.size());

    // Header
    let header_text = match app.mode {
        Mode::SearchInput => format!(
            "ObtainHub TUI - Search: '{}' | Enter to search, Esc to cancel",
            app.search_input
        ),
        Mode::SearchResults => "ObtainHub TUI - Pick a repo: 'Enter' add to management, 'i' install, 'Esc' back".to_string(),
        Mode::List => {
            if !app.filter_text.is_empty() {
                format!(
                    "ObtainHub TUI - Filter: '{}' | 'u' update, 'x' remove, 'a' search, '/' filter, 'c' clear, 'Enter' details, 'r' refresh, '?' help, 'q' quit",
                    app.filter_text
                )
            } else {
                "ObtainHub TUI - 'u' update, 'x' remove, 'a' search, '/' filter, 'c' clear, 'Enter' details, 'r' refresh, 'j/k' nav, '?' help, 'q' quit".to_string()
            }
        }
    };
    let header = Paragraph::new(header_text)
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .block(Block::default().borders(Borders::ALL).title("ObtainHub"));
    f.render_widget(header, chunks[0]);

    // Filter input bar
    if !app.filter_text.is_empty() && app.mode == Mode::List {
        let filter_bar = Paragraph::new(format!("Filter: {}", app.filter_text))
            .style(Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD))
            .block(Block::default().borders(Borders::ALL).title("Filter"));
        f.render_widget(filter_bar, chunks[1]);
    }

    // Search panels take over the main area
    if app.mode == Mode::SearchInput {
        let input = Paragraph::new(format!("> {}", app.search_input))
            .style(Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD))
            .block(
                Block::default()
                    .borders(Borders::ALL)
                    .title("Search GitHub - Enter to search, Esc to cancel"),
            );
        f.render_widget(input, chunks[2]);
    } else if app.mode == Mode::SearchResults {
        let items: Vec<ListItem> = app
            .search_results
            .iter()
            .map(|r| ListItem::new(Line::from(Span::raw(r))))
            .collect();
        let list = List::new(items)
            .block(
                Block::default().borders(Borders::ALL).title(
                    "Search Results - Enter/a add, 'i' install, Esc back",
                ),
            )
            .highlight_style(Style::default().bg(Color::DarkGray).add_modifier(Modifier::BOLD))
            .highlight_symbol("► ");
        f.render_stateful_widget(list, chunks[2], &mut app.search_state);
    } else if app.show_details {
        if let Some(app_info) = app.selected_app() {
            let details = vec![
                Line::from(vec![Span::styled("Name: ", Style::default().add_modifier(Modifier::BOLD)), Span::raw(&app_info.name)]),
                Line::from(vec![Span::styled("Repository: ", Style::default().add_modifier(Modifier::BOLD)), Span::raw(&app_info.repo)]),
                Line::from(vec![Span::styled("Current version: ", Style::default().add_modifier(Modifier::BOLD)), Span::raw(&app_info.current_version)]),
                Line::from(vec![Span::styled("Latest version: ", Style::default().add_modifier(Modifier::BOLD)), Span::raw(&app_info.latest_version)]),
                Line::from(vec![Span::styled("Status: ", Style::default().add_modifier(Modifier::BOLD)), Span::styled(&app_info.status, match app_info.status.as_str() {
                    "Current" => Style::default().fg(Color::Green),
                    "Update" | "Outdated" => Style::default().fg(Color::Red),
                    _ => Style::default().fg(Color::Yellow),
                })]),
                Line::from(vec![Span::styled("Install path: ", Style::default().add_modifier(Modifier::BOLD)), Span::raw(&app_info.install_path)]),
                Line::from(""),
                Line::from(vec![Span::styled("Press 'u' to update, 'x' to remove, 'Enter' to close", Style::default().fg(Color::Gray))]),
            ];
            let details_block = Paragraph::new(details)
                .style(Style::default().fg(Color::White))
                .block(Block::default().borders(Borders::ALL).title("App Details - Press 'Enter' to close"))
                .wrap(Wrap { trim: true });
            f.render_widget(details_block, chunks[2]);
        }
    } else if app.show_help {
        let help_text = vec![
            Line::from(vec![
                Span::styled("Key Bindings", Style::default().add_modifier(Modifier::BOLD).fg(Color::Cyan)),
            ]),
            Line::from(""),
            Line::from(vec![
                Span::styled("  q / Esc", Style::default().fg(Color::Yellow)),
                Span::raw("  - Quit (closes help if open)"),
            ]),
            Line::from(vec![
                Span::styled("  ? / h / F1", Style::default().fg(Color::Yellow)),
                Span::raw("  - Toggle this help screen"),
            ]),
            Line::from(vec![
                Span::styled("  j / ↓", Style::default().fg(Color::Yellow)),
                Span::raw("  - Move selection down"),
            ]),
            Line::from(vec![
                Span::styled("  k / ↑", Style::default().fg(Color::Yellow)),
                Span::raw("  - Move selection up"),
            ]),
            Line::from(vec![
                Span::styled("  r", Style::default().fg(Color::Yellow)),
                Span::raw("  - Refresh app list"),
            ]),
            Line::from(vec![
                Span::styled("  u", Style::default().fg(Color::Yellow)),
                Span::raw("  - Update selected app (if update available)"),
            ]),
            Line::from(vec![
                Span::styled("  x", Style::default().fg(Color::Yellow)),
                Span::raw("  - Remove selected app from management"),
            ]),
            Line::from(vec![
                Span::styled("  a", Style::default().fg(Color::Yellow)),
                Span::raw("  - Search GitHub, then add or install a repository"),
            ]),
            Line::from(vec![
                Span::styled("  /", Style::default().fg(Color::Yellow)),
                Span::raw("  - Filter apps by name/repo/status"),
            ]),
            Line::from(vec![
                Span::styled("  c", Style::default().fg(Color::Yellow)),
                Span::raw("  - Clear filter"),
            ]),
            Line::from(vec![
                Span::styled("  Enter", Style::default().fg(Color::Yellow)),
                Span::raw("  - Show app details"),
            ]),
            Line::from(""),
            Line::from(vec![
                Span::styled("Status Colors:", Style::default().add_modifier(Modifier::BOLD).fg(Color::Cyan)),
            ]),
            Line::from(vec![
                Span::styled("  Green", Style::default().fg(Color::Green)),
                Span::raw("  - Current / up to date"),
            ]),
            Line::from(vec![
                Span::styled("  Red", Style::default().fg(Color::Red)),
                Span::raw("  - Update available / outdated"),
            ]),
            Line::from(vec![
                Span::styled("  Yellow", Style::default().fg(Color::Yellow)),
                Span::raw("  - Unknown / unmanaged"),
            ]),
            Line::from(""),
            Line::from(vec![
                Span::styled("Commands (run in terminal):", Style::default().add_modifier(Modifier::BOLD).fg(Color::Cyan)),
            ]),
            Line::from("  ohub search <query> [--min-stars N] [--sort-stars] [--language LANG]"),
            Line::from("  ohub install <owner/repo> [--version TAG] [--dry-run] [--file PATH] [--url URL]"),
            Line::from("  ohub check [--all] [--outdated-only]"),
            Line::from("  ohub update [<owner/repo>] [--dry-run] [--force]"),
            Line::from("  ohub list [--format table|json|yaml]"),
            Line::from("  ohub uninstall <owner/repo> [--purge] [--yes]"),
            Line::from("  ohub group create <name> / add <group> <repo>"),
            Line::from("  ohub config list / get <key> / set <key> <value>"),
            Line::from("  ohub self-update [--check-only] [--force]"),
            Line::from("  ohub completion <shell>  # bash|zsh|fish|powershell|elvish"),
            Line::from("  ohub doctor"),
            Line::from("  ohub tui"),
        ];

        let help = Paragraph::new(help_text)
            .style(Style::default().fg(Color::White))
            .block(Block::default().borders(Borders::ALL).title("Help - Press '?' to close"))
            .wrap(Wrap { trim: true });
        f.render_widget(help, if !app.filter_text.is_empty() { chunks[2] } else { chunks[1] });
    } else {
        // App list (filtered)
        let visible_indices: Vec<usize> = app.filtered_indices.to_vec();
        let items: Vec<ListItem> = visible_indices
            .iter()
            .map(|&idx| {
                let a = &app.apps[idx];
                let status_style = match a.status.as_str() {
                    "Current" => Style::default().fg(Color::Green),
                    "Update" | "Outdated" => Style::default().fg(Color::Red),
                    _ => Style::default().fg(Color::Yellow),
                };

                ListItem::new(Line::from(vec![
                    Span::styled(&a.name, Style::default().add_modifier(Modifier::BOLD)),
                    Span::raw("  "),
                    Span::raw(format!("v{} ", a.current_version)),
                    if a.latest_version != "?" && a.latest_version != a.current_version {
                        Span::styled(format!("→ v{} ", a.latest_version), Style::default().fg(Color::Cyan))
                    } else {
                        Span::raw("     ")
                    },
                    Span::styled(&a.status, status_style),
                    Span::raw("  "),
                    Span::styled(&a.repo, Style::default().fg(Color::DarkGray)),
                ]))
            })
            .collect();

        let list = List::new(items)
            .block(Block::default().borders(Borders::ALL).title(format!("Managed Apps ({})", visible_indices.len())))
            .highlight_style(Style::default().bg(Color::DarkGray).add_modifier(Modifier::BOLD))
            .highlight_symbol("► ");

        f.render_stateful_widget(list, if !app.filter_text.is_empty() { chunks[2] } else { chunks[1] }, &mut app.list_state);
    }

    // Footer / status
    let footer = Paragraph::new(app.status_message.as_str())
        .style(Style::default().fg(Color::Gray))
        .block(Block::default().borders(Borders::ALL).title("Status"))
        .wrap(Wrap { trim: true });
    f.render_widget(footer, chunks[3]);
}