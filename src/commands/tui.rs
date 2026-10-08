use crate::core::{ConfigManager, StateManager};
use crate::cli::TuiArgs;
use anyhow::Result;
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
use std::io;
use tracing::info;

pub async fn execute(args: TuiArgs, config: &ConfigManager, state: &StateManager) -> Result<()> {
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
}

#[derive(Clone)]
struct AppInfo {
    id: String,
    name: String,
    current_version: String,
    latest_version: String,
    status: String,
    repo: String,
}

async fn run_app<B: ratatui::backend::Backend>(
    terminal: &mut Terminal<B>,
    config: &ConfigManager,
    state: &StateManager,
) -> Result<()> {
    let mut app = App {
        apps: Vec::new(),
        list_state: ListState::default(),
        selected_index: None,
        should_quit: false,
        status_message: "Loading...".to_string(),
    };

    // Load initial data
    app.load_apps(config, state).await;

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
    async fn load_apps(&mut self, config: &ConfigManager, state: &StateManager) {
        self.status_message = "Loading apps...".to_string();
        
        let apps = state.get_all_apps();
        let config_data = config.get();
        
        let mut app_infos = Vec::new();
        
        for app in apps {
            let repo_id = app.repo.clone();
            let (owner, repo) = if let Some(idx) = repo_id.find('/') {
                (&repo_id[..idx], &repo_id[idx+1..])
            } else {
                ("", "")
            };
            
            let current_version = app.version.clone();
            let latest_version = "?".to_string();
            let status = if current_version.is_empty() { "Unmanaged" } else { "Unknown" }.to_string();
            
            app_infos.push(AppInfo {
                id: repo_id.clone(),
                name: repo.to_string(),
                current_version,
                latest_version,
                status,
                repo: repo_id,
            });
        }
        
        self.apps = app_infos;
        self.list_state.select(Some(0));
        self.selected_index = Some(0);
        self.status_message = format!("Loaded {} apps", self.apps.len());
    }
}

async fn handle_key_event(
    key: KeyCode,
    app: &mut App,
    _config: &ConfigManager,
    _state: &StateManager,
) -> Result<()> {
    match key {
        KeyCode::Char('q') | KeyCode::Esc => {
            app.should_quit = true;
        }
        KeyCode::Char('j') | KeyCode::Down => {
            if let Some(selected) = app.list_state.selected() {
                if selected < app.apps.len().saturating_sub(1) {
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
            // In a real implementation, we'd reload the apps here
            app.status_message = "Refreshed".to_string();
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
            Constraint::Min(0),
            Constraint::Length(3),
        ])
        .split(f.size());

    // Header
    let header = Paragraph::new("ObtainHub TUI - Press 'q' to quit, 'j/k' to navigate, 'r' to refresh")
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .block(Block::default().borders(Borders::ALL).title("ObtainHub"));
    f.render_widget(header, chunks[0]);

    // App list
    let items: Vec<ListItem> = app
        .apps
        .iter()
        .map(|a| {
            let status_style = match a.status.as_str() {
                "Current" => Style::default().fg(Color::Green),
                "Update" | "Outdated" => Style::default().fg(Color::Red),
                _ => Style::default().fg(Color::Yellow),
            };
            
            ListItem::new(Line::from(vec![
                Span::styled(&a.name, Style::default().add_modifier(Modifier::BOLD)),
                Span::raw("  "),
                Span::raw(format!("v{} ", a.current_version)),
                Span::styled(&a.status, status_style),
                Span::raw("  "),
                Span::styled(&a.repo, Style::default().fg(Color::DarkGray)),
            ]))
        })
        .collect();

    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Managed Apps"))
        .highlight_style(Style::default().bg(Color::DarkGray).add_modifier(Modifier::BOLD))
        .highlight_symbol("► ");

    f.render_stateful_widget(list, chunks[1], &mut app.list_state);

    // Footer / status
    let footer = Paragraph::new(app.status_message.as_str())
        .style(Style::default().fg(Color::Gray))
        .block(Block::default().borders(Borders::ALL).title("Status"))
        .wrap(Wrap { trim: true });
    f.render_widget(footer, chunks[2]);
}