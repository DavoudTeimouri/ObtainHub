use crate::cli::CompletionArgs;
use anyhow::Result;
use clap_complete::Shell;
use clap::CommandFactory;
use crate::cli::Cli;

pub async fn execute(args: CompletionArgs) -> Result<()> {
    let mut cmd = Cli::command();
    let name = cmd.get_name().to_string();
    // ponytail: generate into a buffer, then write once — clap_complete panics on
    // a closed stdout (`ohub completion fish | head`). Upgrade path: stream directly
    // once clap_complete handles EPIPE.
    let mut buf: Vec<u8> = Vec::new();
    clap_complete::generate(args.shell, &mut cmd, name, &mut buf);

    use std::io::Write;
    match std::io::stdout().write_all(&buf) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::BrokenPipe => Ok(()),
        Err(e) => Err(e.into()),
    }
}