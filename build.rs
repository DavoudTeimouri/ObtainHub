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
    
    // Rustc version. `cargo` sets RUSTC to the compiler it drives; `rustc
    // --version` prints "rustc 1.85.1 (…)", so the second word is the number
    // the version banner wants.
    let rustc = std::env::var("RUSTC").unwrap_or_else(|_| "rustc".to_string());
    let rustc_version = std::process::Command::new(&rustc)
        .arg("--version")
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| {
            String::from_utf8_lossy(&o.stdout)
                .split_whitespace()
                .nth(1)
                .map(str::to_string)
        })
        .unwrap_or_else(|| "unknown".to_string());
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