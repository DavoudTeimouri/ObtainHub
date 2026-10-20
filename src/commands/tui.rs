use crate::core::{ConfigManager, StateManager};
use crate::cli::{RemoveArgs, TuiArgs, UpdateArgs};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use minreq;
use ratatui;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph, Wrap},
    Terminal,
    Frame,
};
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use serde::{Deserialize, Serialize};
use std::io;
use std::time::Duration;
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
    retry_config: RetryConfig,
}

#[derive(Clone)]
struct AppInfo {
    id: String,
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
                req = req.with_header("Authorization", &format!("Bearer {}", token));
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
        retry_config: RetryConfig::from_config(config),
    };

    // Load initial data
    let retry_config_clone = app.retry_config.clone();
    app.load_apps(config, state, &retry_config_clone).await;

    while !app.should_quit {
        terminal.draw(|f| ui::<B>(f, &mut app))?;

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
            let (owner, repo) = if let Some(idx) = repo_id.find('/') {
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
                id: repo_id.clone(),
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

async fn handle_key_event(
    key: KeyCode,
    app: &mut App,
    config: &ConfigManager,
    state: &mut StateManager,
) -> Result<()> {
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
        KeyCode::Char(c) => {
            // Only handle char input when filtering (filter_text started with /)
            // or if we're in filter mode
            if !app.filter_text.is_empty() || c == '/' {
                if c != '/' {
                    app.filter_text.push(c);
                    app.apply_filter();
                }
            }
        }
        _ => {}
    }
    Ok(())
}

fn ui<B: ratatui::backend::Backend>(f: &mut ratatui::Frame, app: &mut App) {
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
    let header_text = if !app.filter_text.is_empty() {
        format!(
            "ObtainHub TUI - Filter: '{}' | 'u' update, 'x' remove, '/' filter, 'c' clear, 'Enter' details, 'r' refresh, '?' help, 'q' quit",
            app.filter_text
        )
    } else {
        "ObtainHub TUI - 'u' update, 'x' remove, '/' filter, 'c' clear, 'Enter' details, 'r' refresh, 'j/k' nav, '?' help, 'q' quit".to_string()
    };
    let header = Paragraph::new(header_text)
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .block(Block::default().borders(Borders::ALL).title("ObtainHub"));
    f.render_widget(header, chunks[0]);

    // Filter input bar
    if !app.filter_text.is_empty() {
        let filter_bar = Paragraph::new(format!("Filter: {}", app.filter_text))
            .style(Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD))
            .block(Block::default().borders(Borders::ALL).title("Filter"));
        f.render_widget(filter_bar, chunks[1]);
    }

    // Details modal or App list or Help
    if app.show_details {
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
        let visible_indices: Vec<usize> = app.filtered_indices.iter().copied().collect();
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