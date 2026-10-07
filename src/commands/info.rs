use crate::core::{ConfigManager, StateManager};
use crate::cli::InfoArgs;
use anyhow::Result;
use minreq::get;
use tracing::info;

#[derive(serde::Deserialize, Debug)]
struct GitHubRepo {
    full_name: String,
    description: Option<String>,
    html_url: String,
    stargazers_count: u32,
    forks_count: u32,
    language: Option<String>,
    license: Option<License>,
    created_at: String,
    updated_at: String,
    pushed_at: String,
    default_branch: String,
    open_issues_count: u32,
    size: u32,
    topics: Vec<String>,
    owner: Owner,
}

#[derive(serde::Deserialize, Debug)]
struct License {
    name: String,
    spdx_id: Option<String>,
}

#[derive(serde::Deserialize, Debug)]
struct Owner {
    login: String,
    html_url: String,
}

pub async fn execute(args: InfoArgs, config: &ConfigManager, _state: &StateManager) -> Result<()> {
    info!("Fetching info for {}", args.repo);
    
    let token = config.get().github_token.as_deref();
    let mut req = get(format!("https://api.github.com/repos/{}", args.repo));
    
    if let Some(token) = token {
        req = req.with_header("Authorization", format!("Bearer {}", token));
    }
    
    let resp = req.send()?;
    
    if resp.status_code == 404 {
        anyhow::bail!("Repository not found: {}", args.repo);
    }
    
    if resp.status_code == 403 {
        anyhow::bail!("Rate limited or access denied. Set GitHub token with 'ohub config set github_token <token>'");
    }
    
    if resp.status_code < 200 || resp.status_code >= 300 {
        anyhow::bail!("GitHub API error: {}", resp.status_code);
    }
    
    let repo: GitHubRepo = resp.json()?;
    
    println!("Repository: {}", repo.full_name);
    println!("URL: {}", repo.html_url);
    println!("Owner: {} ({})", repo.owner.login, repo.owner.html_url);
    println!("Description: {}", repo.description.unwrap_or_else(|| "None".to_string()));
    println!("Stars: {}", repo.stargazers_count);
    println!("Forks: {}", repo.forks_count);
    println!("Watchers: {}", repo.open_issues_count);
    println!("Language: {}", repo.language.unwrap_or_else(|| "None".to_string()));
    println!("License: {}", repo.license.map(|l| l.name).unwrap_or_else(|| "None".to_string()));
    println!("Default branch: {}", repo.default_branch);
    println!("Size: {} KB", repo.size);
    println!("Created: {}", repo.created_at);
    println!("Updated: {}", repo.updated_at);
    println!("Last push: {}", repo.pushed_at);
    println!("Topics: {}", if repo.topics.is_empty() { "None".to_string() } else { repo.topics.join(", ") });
    
    Ok(())
}