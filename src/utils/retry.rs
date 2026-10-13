use crate::core::ConfigManager;
use minreq::Response;
use std::time::Duration;
use tokio::time::sleep;
use tracing::{debug, warn};

/// HTTP retry configuration
#[derive(Debug, Clone)]
pub struct RetryConfig {
    pub max_retries: u32,
    pub initial_delay_ms: u64,
    pub backoff_factor: f64,
    pub max_delay_ms: u64,
}

impl RetryConfig {
    pub fn from_config(config: &ConfigManager) -> Self {
        let cfg = config.get();
        Self {
            max_retries: cfg.http_retries,
            initial_delay_ms: cfg.http_retry_delay_ms,
            backoff_factor: cfg.http_retry_backoff,
            max_delay_ms: 30_000, // 30 seconds max
        }
    }
    
    pub fn default() -> Self {
        Self {
            max_retries: 3,
            initial_delay_ms: 1000,
            backoff_factor: 2.0,
            max_delay_ms: 30_000,
        }
    }
}

/// Execute an HTTP request with retry logic
pub async fn execute_with_retry<F, Fut, T>(
    retry_config: &RetryConfig,
    operation: F,
    operation_name: &str,
) -> anyhow::Result<T>
where
    F: Fn() -> Fut + Send + Sync,
    Fut: std::future::Future<Output = anyhow::Result<T>> + Send,
{
    let mut last_error = None;
    let mut delay = retry_config.initial_delay_ms;
    
    for attempt in 0..=retry_config.max_retries {
        match operation().await {
            Ok(result) => {
                if attempt > 0 {
                    debug!("{} succeeded on attempt {}", operation_name, attempt + 1);
                }
                return Ok(result);
            }
            Err(e) => {
                last_error = Some(e);
                
                // Check if we should retry
                if attempt < retry_config.max_retries {
                    // Check if error is retryable (network errors, 5xx, 429)
                    let should_retry = match &last_error {
                        Some(err) => {
                            let err_str = err.to_string().to_lowercase();
                            // Retry on network errors, timeouts, 5xx server errors, 429 rate limit
                            err_str.contains("timeout") ||
                            err_str.contains("connection") ||
                            err_str.contains("network") ||
                            err_str.contains("500") ||
                            err_str.contains("502") ||
                            err_str.contains("503") ||
                            err_str.contains("504") ||
                            err_str.contains("429") ||
                            err_str.contains("eof") ||
                            err_str.contains("reset")
                        }
                        None => false,
                    };
                    
                    if should_retry {
                        warn!("{} failed (attempt {}/{}): {}. Retrying in {}ms...", 
                            operation_name, attempt + 1, retry_config.max_retries + 1, 
                            last_error.as_ref().unwrap(), delay);
                        sleep(Duration::from_millis(delay)).await;
                        delay = (delay as f64 * retry_config.backoff_factor) as u64;
                        delay = delay.min(retry_config.max_delay_ms);
                        continue;
                    }
                }
                
                // Non-retryable error or max retries exceeded
                break;
            }
        }
    }
    
    Err(last_error.unwrap())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::ConfigManager;
    
    #[test]
    fn test_retry_config_defaults() {
        let config = RetryConfig::default();
        assert_eq!(config.max_retries, 3);
        assert_eq!(config.initial_delay_ms, 1000);
        assert_eq!(config.backoff_factor, 2.0);
    }
}