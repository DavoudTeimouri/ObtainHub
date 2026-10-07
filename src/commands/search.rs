use crate::core::{ConfigManager, StateManager};
use crate::cli::{SearchArgs, OutputFormat};
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use tracing::info;
use urlencoding;
use chrono;
use comfy_table::{Table, Cell, Attribute};

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
    total_count: u32,
}

pub async fn execute(args: SearchArgs, config: &ConfigManager, _state: &StateManager, format: OutputFormat) -> Result<()> {
    info!("Searching for: {}", args.query);
    
    let token = config.get().github_token.as_deref();
    
    let mut url = format!(
        "https://api.github.com/search/repositories?q={}&per_page={}&sort={}&order=desc",
        urlencoding::encode(&args.query),
        args.limit.min(100),
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
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    
    let resp: SearchResponse = req.with_timeout(config.get().timeout_seconds as u64).send()?.json()?;
    
    let mut results: Vec<_> = resp.items.into_iter()
        .filter(|r| r.stargazers_count >= args.min_stars)
        .collect();
    
    if args.case_insensitive {
        // Already handled by GitHub API
    }
    
    // Output based on format
    match format {
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&results)?);
        }
        OutputFormat::Yaml => {
            println!("{}", serde_yaml::to_string(&results)?);
        }
        OutputFormat::Table => {
            print_table(&results);
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