fn main() {
    winres::WindowsResource::new()
        .set_icon("installer/icon.ico")
        .compile()
        .expect("Failed to compile Windows resources");
}