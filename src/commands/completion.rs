use crate::cli::CompletionArgs;
use anyhow::Result;
use clap_complete::Shell;
use clap::CommandFactory;
use crate::cli::Cli;

pub async fn execute(args: CompletionArgs) -> Result<()> {
    let mut cmd = Cli::command();
    let name = cmd.get_name().to_string();
    clap_complete::generate(args.shell, &mut cmd, name, &mut std::io::stdout());
    Ok(())
}