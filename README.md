# ObtainHub

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/ObtainHub/ObtainHub)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**ObtainHub** is a GitHub-based package updater and manager for Windows, designed to simplify installing and updating applications directly from GitHub releases.

## Features

- 🚀 **GitHub Release Integration** - Install and update apps directly from GitHub releases
- 🔄 **Self-Update Mechanism** - Automatically checks for and applies ObtainHub updates
- 📦 **Multiple Installer Support** - Handles MSI, EXE, and ZIP/Portable installers
- 🔍 **Smart Version Detection** - Compares versions and detects updates automatically
- ⚙️ **Custom Manifest Sources** - Add your own application manifests
- 🛡️ **Verification** - Checksum and signature verification for downloads
- 📋 **State Management** - Tracks installed applications with full metadata

## Installation

### From Source

```bash
git clone https://github.com/ObtainHub/ObtainHub.git
cd ObtainHub
pip install -e .
```

### Using pip (once published)

```bash
pip install obtainhub
```

## Quick Start

```bash
# Install an application from GitHub
ohub install microsoft/vscode

# Check for updates
ohub check

# Update all installed applications
ohub update

# List installed applications
ohub list

# Add a custom manifest source
ohub source add my-source https://example.com/manifest.json
```

## Commands

| Command | Description |
|---------|-------------|
| `ohub install <owner/repo>` | Install an application from GitHub |
| `ohub update` | Update all installed applications |
| `ohub check` | Check for available updates |
| `ohub list` | List installed applications |
| `ohub info <owner/repo>` | Show detailed app information |
| `ohub uninstall <owner/repo>` | Uninstall an application |
| `ohub source <add\|remove\|list>` | Manage manifest sources |

## Global Options

| Option | Description |
|--------|-------------|
| `--skip-self-update` | Skip self-update check |
| `--verbose` | Enable verbose output |
| `--config-dir <path>` | Use custom configuration directory |

## Configuration

ObtainHub stores configuration in:
- **Windows**: `%APPDATA%\ObtainHub\config.json`
- **Linux/macOS**: `~/.config/obtainhub/config.json`

### Configuration Options

```json
{
  "download_dir": "~/Downloads/ObtainHub",
  "auto_update": true,
  "skip_self_update": false,
  "verbose": false,
  "log_level": "INFO",
  "manifest_sources": [
    "https://raw.githubusercontent.com/ObtainHub/manifests/main/index.json"
  ],
  "github_token": "",
  "request_timeout": 30,
  "max_retries": 3,
  "preferred_installer_type": "auto",
  "verify_signatures": true,
  "verify_checksums": true,
  "backup_before_update": true
}
```

## State Management

Installed applications are tracked in:
- **Windows**: `%APPDATA%\ObtainHub\state.json`
- **Linux/macOS**: `~/.config/obtainhub/state.json`

Each application record includes:
- Version and installer type
- Installation path and executable location
- Checksums and verification data
- GitHub release metadata

## Architecture

```
obtainhub/
├── __init__.py           # Package metadata
├── main.py               # CLI entry point
├── core/
│   ├── __init__.py       # Core exports
│   ├── config.py         # Configuration management
│   ├── state.py          # Application state tracking
│   ├── logger.py         # Structured logging
│   ├── self_updater.py   # Self-update mechanism
│   └── exceptions.py     # Custom exceptions
├── utils/
│   ├── __init__.py       # Utility exports
│   └── helpers.py        # Helper functions
└── commands/             # Command implementations (future)
```

## Self-Update Mechanism

On every execution, `ohub`:
1. Checks its version against the latest GitHub release
2. If a newer version is found, downloads the installer
3. Launches the installer silently in a detached process
4. Exits gracefully to release file locks
5. User restarts ObtainHub after installation completes

## Manifest Format

Custom manifest sources should provide JSON with this structure:

```json
{
  "applications": [
    {
      "name": "Visual Studio Code",
      "owner": "microsoft",
      "repo": "vscode",
      "version": "1.85.0",
      "description": "Code editor",
      "installer_type": "auto",
      "checksum": "sha256:...",
      "file_size": 123456789,
      "release_date": "2024-01-01",
      "release_notes": "https://github.com/microsoft/vscode/releases/tag/1.85.0",
      "tags": ["editor", "ide"],
      "homepage": "https://code.visualstudio.com",
      "license": "MIT"
    }
  ]
}
```

## Development

### Running Tests

```bash
pip install pytest
pytest tests/ -v
```

### Code Style

```bash
# Format code
black obtainhub/ tests/

# Type check
mypy obtainhub/

# Lint
ruff obtainhub/ tests/
```

## Project Structure

```
ObtainHub/
├── obtainhub/              # Main package
│   ├── main.py            # CLI entry point
│   ├── core/              # Core modules
│   └── utils/             # Utility functions
├── tests/                 # Unit tests
├── requirements.txt       # Dependencies
├── README.md             # This file
└── .gitignore            # Git ignore rules
```

## Roadmap

- [ ] **Step 1**: Core infrastructure (config, state, self-updater, CLI) ✓
- [ ] **Step 2**: Manifest system and GitHub API integration
- [ ] **Step 3**: Download and installer execution engine
- [ ] **Step 4**: Windows registry integration and uninstaller
- [ ] **Step 5**: Package commands (install, update, uninstall)
- [ ] **Step 6**: Cross-platform support (Linux/macOS)
- [ ] **Step 7**: GUI and system tray integration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- **Repository**: https://github.com/ObtainHub/ObtainHub
- **Issues**: https://github.com/ObtainHub/ObtainHub/issues
- **Releases**: https://github.com/ObtainHub/ObtainHub/releases