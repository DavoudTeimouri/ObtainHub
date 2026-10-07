use anyhow::Result;
use tracing_subscriber::{EnvFilter, fmt, layer::SubscriberExt, util::SubscriberInitExt};

pub fn init() -> Result<()> {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info"));
    
    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer()
            .with_writer(std::io::stdout)
            .with_target(false)
            .with_thread_ids(false)
            .with_thread_names(false)
            .with_file(false)
            .with_line_number(false)
        )
        .init();
    
    Ok(())
}

pub fn init_with_level(level: &str) -> Result<()> {
    let filter = EnvFilter::new(level);
    
    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer()
            .with_writer(std::io::stdout)
            .with_target(false)
            .with_thread_ids(false)
            .with_thread_names(false)
            .with_file(false)
            .with_line_number(false)
        )
        .init();
    
    Ok(())
}