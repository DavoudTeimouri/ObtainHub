#[cfg(target_os = "windows")]
fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
    let icon_path = std::path::Path::new(&manifest_dir).join("installer/icon.ico");
    winres::WindowsResource::new()
        .set_icon(icon_path.to_str().unwrap())
        .compile()
        .expect("Failed to compile Windows resources");
}

#[cfg(not(target_os = "windows"))]
fn main() {}