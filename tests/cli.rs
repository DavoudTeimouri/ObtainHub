//! CLI-level smoke tests: binary runs, help renders, completions generate.
use assert_cmd::Command;
use predicates::prelude::*;

#[test]
fn version_prints_name_and_version() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::contains("ohub"));
}

#[test]
fn help_lists_core_commands() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.arg("--help")
        .assert()
        .success()
        .stdout(predicate::str::contains("search"))
        .stdout(predicate::str::contains("install"))
        .stdout(predicate::str::contains("webui"));
}

#[test]
fn completion_generates_for_all_shells() {
    for shell in ["bash", "zsh", "fish", "powershell", "elvish"] {
        let mut cmd = Command::cargo_bin("ohub").unwrap();
        cmd.arg("completion")
            .arg(shell)
            .assert()
            .success()
            .stdout(predicate::str::is_empty().not());
    }
}

#[test]
fn search_dry_run_prints_query_without_network() {
    let mut cmd = Command::cargo_bin("ohub").unwrap();
    cmd.arg("search")
        .arg("obtainhub-test-query")
        .arg("--dry-run")
        .assert()
        .success()
        .stdout(predicate::str::contains("api.github.com/search/repositories?q=obtainhub-test-query"));
}
