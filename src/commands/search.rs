use crate::core::{ConfigManager, StateManager};
use crate::cli::{SearchArgs, OutputFormat};
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use tracing::info;
use urlencoding;
use chrono;
use comfy_table::{Table, Cell, Attribute};
use dialoguer::{MultiSelect, Confirm, theme::ColorfulTheme};

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRepo {
    full_name: String,
    description: Option<String>,
    stargazers_count: u32,
    language: Option<String>,
    updated_at: String,
    html_url: String,
    default_branch: String,
}

#[derive(Deserialize, Debug)]
struct SearchResponse {
    items: Vec<GitHubRepo>,
    #[allow(dead_code)]
    total_count: u32,
}

pub async fn execute(args: SearchArgs, config: &ConfigManager, state: &mut StateManager, format: OutputFormat) -> Result<()> {
    info!("Searching for: {}", args.query);

    let token = config.get().github_token.as_deref();

    let mut url = format!(
        "https://api.github.com/search/repositories?q={}&per_page={}&page={}&sort={}&order=desc",
        urlencoding::encode(&args.query),
        args.per_page.min(100),
        args.page,
        if args.sort_stars { "stars" } else { "best-match" }
    );

    if args.active_only {
        let year_ago = chrono::Utc::now() - chrono::Duration::days(365);
        url.push_str(&format!("+pushed:>={}", year_ago.format("%Y-%m-%d")));
    }

    if let Some(lang) = &args.language {
        url.push_str(&format!("+language:{}", urlencoding::encode(lang)));
    }

    let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", format!("Bearer {token}"));
    }

    let resp = req.with_timeout(config.get().timeout_seconds).send()?;

    if resp.status_code == 403 {
        return Err(anyhow::anyhow!(
            "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
        ));
    }

    let resp: SearchResponse = resp.json()?;

    let mut results: Vec<_> = resp.items.into_iter()
        .filter(|r| r.stargazers_count >= args.min_stars)
        .collect();

    results.truncate(args.limit);

    if results.is_empty() {
        println!("No repositories found for '{}'.", args.query);
        return Ok(());
    }

    let theme = ColorfulTheme::default();

    match format {
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&results)?);
        }
        OutputFormat::Yaml => {
            println!("{}", serde_yaml::to_string(&results)?);
        }
        OutputFormat::Table => {
            print_table(&results);

            let repo_names: Vec<String> = results.iter().map(|r| r.full_name.clone()).collect();

            let selections = MultiSelect::with_theme(&theme)
                .with_prompt("Select repositories from search results (Space to select, Enter to confirm)")
                .items(&repo_names)
                .interact_opt()?;

            if let Some(selected_indices) = selections {
                if selected_indices.is_empty() {
                    println!("No repositories selected.");
                    return Ok(());
                }

                println!("\nSelected {} repository(-ies).", selected_indices.len());

                let add = Confirm::with_theme(&theme)
                    .with_prompt("Add selected repositories to managed list?")
                    .default(true)
                    .interact()?;

                if add {
                    for idx in &selected_indices {
                        let repo = &results[*idx].full_name;
                        let new_repo = crate::core::state::InstalledRepo {
                            repo: repo.clone(),
                            version: "unknown".to_string(),
                            install_path: std::path::PathBuf::new(),
                            installed_at: chrono::Utc::now(),
                            updated_at: None,
                            checksum: None,
                            metadata: serde_json::Value::Null,
                            previous_version: None,
                            previous_install_path: None,
                            dependencies: Vec::new(),
                            is_dependency: false,
                            ..Default::default()
                        };
                        state.add_installed(new_repo.clone());
                        state.save()?;
                        println!("Added '{}' to managed repositories.", repo);
                    }
                }

                let install = Confirm::with_theme(&theme)
                    .with_prompt("Install selected repositories now?")
                    .default(false)
                    .interact()?;

                if install {
                    for idx in &selected_indices {
                        let repo = &results[*idx].full_name;
                        println!("Installing '{}'...", repo);
                        let install_args = crate::cli::InstallArgs {
                            repo: repo.clone(),
                            version: None,
                            tag: None,
                            prerelease: false,
                            force: false,
                            download_only: false,
                            skip_deps: false,
                            timeout: None,
                            arch: crate::cli::Arch::Auto,
                            yes: false,
                            reset: false,
                            interactive: false,
                            dry_run: false,
                            file: None,
                            url: None,
                            dependencies: Vec::new(),
                        };
                        let retry_config = crate::utils::retry::RetryConfig::from_config(config);
                        if let Err(e) = crate::commands::install::execute(install_args, config, state, &retry_config).await {
                            eprintln!("Failed to install '{}': {}", repo, e);
                        }
                    }
                }
            }
        }
    }

    Ok(())
}

fn print_table(repos: &[GitHubRepo]) {
    let mut table = Table::new();
    table.set_header(vec!["Repository", "Stars", "Language", "Updated", "Description"]);

    for repo in repos {
        table.add_row(vec![
            Cell::new(&repo.full_name).add_attribute(Attribute::Bold),
            Cell::new(repo.stargazers_count.to_string()),
            Cell::new(repo.language.as_deref().unwrap_or("-")),
            Cell::new(&repo.updated_at[..10]),
            Cell::new(repo.description.as_deref().unwrap_or("-")),
        ]);
    }

    println!("{}", table);
}
