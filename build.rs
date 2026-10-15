#[cfg(target_os = "windows")]
fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let icon_path = std::path::Path::new(&manifest_dir).join("installer/icon.ico");
    winres::WindowsResource::new()
        .set_icon(icon_path.to_str().unwrap())
        .compile()
        .expect("Failed to compile Windows resources");
    
    // Emit build constants for version template
    emit_build_constants();
}

#[cfg(not(target_os = "windows"))]
fn main() {
    // Emit build constants for version template
    emit_build_constants();
}

fn emit_build_constants() {
    // Build timestamp in ISO 8601 format
    let build_timestamp = chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string();
    println!("cargo:rustc-env=VERGEN_BUILD_TIMESTAMP={}", build_timestamp);
    
    // Rustc version
    let rustc_version = std::env::var("RUSTC_VERSION").unwrap_or_else(|_| "unknown".to_string());
    println!("cargo:rustc-env=VERGEN_RUSTC_SEMVER={}", rustc_version);
    
    // Git info if available
    if let Ok(git_dir) = std::env::var("CARGO_MANIFEST_DIR") {
        let git_cmd = std::process::Command::new("git")
            .args(["rev-parse", "HEAD"])
            .current_dir(&git_dir)
            .output();
        if let Ok(output) = git_cmd {
            if output.status.success() {
                let sha = String::from_utf8_lossy(&output.stdout).trim().to_string();
                println!("cargo:rustc-env=VERGEN_GIT_SHA={}", sha);
            }
        }
        
        let git_cmd = std::process::Command::new("git")
            .args(["describe", "--tags", "--always"])
            .current_dir(&git_dir)
            .output();
        if let Ok(output) = git_cmd {
            if output.status.success() {
                let desc = String::from_utf8_lossy(&output.stdout).trim().to_string();
                println!("cargo:rustc-env=VERGEN_GIT_DESCRIBE={}", desc);
            }
        }
    }
}