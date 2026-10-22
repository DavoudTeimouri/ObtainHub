use anyhow::Result;
use tracing_subscriber::{EnvFilter, fmt, layer::SubscriberExt, util::SubscriberInitExt};

/// Start logging. `verbose` turns the level up to debug; `RUST_LOG` still
/// wins when it is set.
pub fn init(verbose: bool) -> Result<()> {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(if verbose { "debug" } else { "info" }));
    
    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer()
            .with_writer(std::io::stdout)
            .with_target(false)
            .with_thread_ids(false)
            .with_thread_names(false)
            .with_file(false)
            .with_line_number(false)
            .without_time()
        )
        .init();
    
    Ok(())
}
