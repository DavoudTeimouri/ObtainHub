use assert_cmd::Command;
use predicates::prelude::*;
use serial_test::serial;

#[tokio::test]
#[serial]
async fn test_help_command() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.arg("--help");
    cmd.assert().success().stdout(predicate::str::contains("Search, install, and manage GitHub repositories"));
}

#[tokio::test]
#[serial]
async fn test_version_command() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.arg("--version");
    cmd.assert().success().stdout(predicate::str::contains("3.0.0"));
}

#[tokio::test]
#[serial]
async fn test_search_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["search", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Search GitHub repositories"));
}

#[tokio::test]
#[serial]
async fn test_install_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["install", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Install a repository"));
}

#[tokio::test]
#[serial]
async fn test_install_file_flag() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["install", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("--file"));
}

#[tokio::test]
#[serial]
async fn test_install_url_flag() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["install", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("--url"));
}

#[tokio::test]
#[serial]
async fn test_list_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["list", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("List installed repositories"));
}

#[tokio::test]
#[serial]
async fn test_check_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["check", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Check for updates"));
}

#[tokio::test]
#[serial]
async fn test_update_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["update", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Update installed repositories"));
}

#[tokio::test]
#[serial]
async fn test_uninstall_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["uninstall", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Uninstall a repository"));
}

#[tokio::test]
#[serial]
async fn test_config_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["config", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Manage configuration"));
}

#[tokio::test]
#[serial]
async fn test_config_auth_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["config", "auth", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Show GitHub token source"));
}

#[tokio::test]
#[serial]
async fn test_backup_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["backup", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Backup installed repositories"));
}

#[tokio::test]
#[serial]
async fn test_restore_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["restore", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Restore from backup"));
}

#[tokio::test]
#[serial]
async fn test_doctor_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["doctor", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Diagnose installation issues"));
}

#[tokio::test]
#[serial]
async fn test_info_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["info", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Show detailed info"));
}

#[tokio::test]
#[serial]
async fn test_remove_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["remove", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Remove a repository from management"));
}

#[tokio::test]
#[serial]
async fn test_add_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["add", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Add a repository to management"));
}

#[tokio::test]
#[serial]
async fn test_self_uninstall_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["self-uninstall", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Completely remove ohub"));
}

#[tokio::test]
#[serial]
async fn test_state_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["state", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Export/import ohub state"));
}

#[tokio::test]
#[serial]
async fn test_state_validate_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["state", "validate", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Validate state integrity"));
}

#[tokio::test]
#[serial]
async fn test_state_clean_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["state", "clean", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Clean orphaned state entries"));
}

#[tokio::test]
#[serial]
async fn test_source_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["source", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Manage custom sources"));
}

#[tokio::test]
#[serial]
async fn test_source_subcommands() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["source", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("list"))
        .stdout(predicate::str::contains("add"))
        .stdout(predicate::str::contains("remove"))
        .stdout(predicate::str::contains("verify"))
        .stdout(predicate::str::contains("update"))
        .stdout(predicate::str::contains("enable"))
        .stdout(predicate::str::contains("disable"));
}

#[tokio::test]
#[serial]
async fn test_schedule_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["schedule", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Manage scheduled background checks"));
}

#[tokio::test]
#[serial]
async fn test_schedule_run_prerelease() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["schedule", "run", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("prerelease"));
}

#[tokio::test]
#[serial]
async fn test_group_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["group", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Manage app groups"));
}

#[tokio::test]
#[serial]
async fn test_group_subcommands() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["group", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("install"))
        .stdout(predicate::str::contains("update"))
        .stdout(predicate::str::contains("check"))
        .stdout(predicate::str::contains("uninstall"));
}

#[tokio::test]
#[serial]
async fn test_shim_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["shim", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Manage portable shims"));
}

#[tokio::test]
#[serial]
async fn test_shim_add_app_arg() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["shim", "add", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("<APP>"))
        .stdout(predicate::str::contains("--name"));
}

#[tokio::test]
#[serial]
async fn test_apps_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["apps", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Backup/restore application folders"));
}

#[tokio::test]
#[serial]
async fn test_apps_backup_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["apps", "backup", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("include-downloads"))
        .stdout(predicate::str::contains("output"));
}

#[tokio::test]
#[serial]
async fn test_apps_restore_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["apps", "restore", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("input"))
        .stdout(predicate::str::contains("target-dir"))
        .stdout(predicate::str::contains("dry-run"));
}

#[tokio::test]
#[serial]
async fn test_cleanup_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["cleanup", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Clean up leftover files"));
}

#[tokio::test]
#[serial]
async fn test_cleanup_subcommands() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["cleanup", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("all"))
        .stdout(predicate::str::contains("tasks"))
        .stdout(predicate::str::contains("downloads"))
        .stdout(predicate::str::contains("cache"));
}

#[tokio::test]
#[serial]
async fn test_reset_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["reset", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Reset ohub state"));
}

#[tokio::test]
#[serial]
async fn test_tui_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["tui", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Launch Textual User Interface"));
}

#[tokio::test]
#[serial]
async fn test_completion_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["completion", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Generate shell completions"));
}

#[tokio::test]
#[serial]
async fn test_self_update_help() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.args(["self-update", "--help"]);
    cmd.assert().success().stdout(predicate::str::contains("Update ohub itself"))
        .stdout(predicate::str::contains("--check-only"))
        .stdout(predicate::str::contains("--prerelease"))
        .stdout(predicate::str::contains("--force"))
        .stdout(predicate::str::contains("--json"))
        .stdout(predicate::str::contains("--quiet"));
}