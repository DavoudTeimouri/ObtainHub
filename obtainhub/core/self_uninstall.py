"""Self-uninstaller for ObtainHub CLI.

Removes ObtainHub completely (download folder, application folder, config, state)
with optional backup to zip for restore on current or another machine.
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from obtainhub.core.config import get_config_manager, ConfigManager, Config
from obtainhub.core.state import get_state_manager, StateManager
from obtainhub.utils.backup import get_backup_retention_count, create_backups


# Default locations
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "ObtainHub"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "obtainhub"
DEFAULT_STATE_DIR = Path.home() / ".config" / "ObtainHub"


class SelfUninstaller:
    """Handles complete removal of ObtainHub with optional backup."""
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        state_manager: Optional[StateManager] = None,
        backup_retention: Optional[int] = None,
    ):
        self.config_manager = config_manager or get_config_manager()
        self.state_manager = state_manager or get_state_manager()
        self.backup_retention = backup_retention or get_backup_retention_count()
        self.config = self.config_manager.load()
        self.state = self.state_manager
        
    def get_ohub_paths(self) -> Dict[str, Path]:
        """Get all ObtainHub-related paths."""
        config_file = self.config_manager.config_file
        state_file = self.state_manager.state_file
        
        paths = {
            "config_dir": config_file.parent,
            "config_file": config_file,
            "state_dir": state_file.parent,
            "state_file": state_file,
            "download_dir": DEFAULT_DOWNLOAD_DIR,
        }
        
        # Check for alternate locations from config
        if self.config.config_dir:
            config_dir = Path(self.config.config_dir)
            paths["config_dir"] = config_dir
            paths["config_file"] = config_dir / "config.json"
        
        return paths
    
    def collect_files_to_backup(self) -> Dict[str, Path]:
        """Collect all files that should be backed up."""
        paths = self.get_ohub_paths()
        to_backup = {}
        
        # Config and state files
        if paths["config_file"].exists():
            to_backup["config.json"] = paths["config_file"]
        if paths["state_file"].exists():
            to_backup["state.json"] = paths["state_file"]
        
        # Check for other config/state files in the directories
        for config_file in paths["config_dir"].glob("*.json"):
            if config_file.name not in ("config.json",):
                to_backup[f"config_extra/{config_file.name}"] = config_file
        
        for state_file in paths["state_dir"].glob("*.json"):
            if state_file.name not in ("state.json",):
                to_backup[f"state_extra/{state_file.name}"] = state_file
        
        return to_backup
    
    def create_backup_zip(self, output_path: Path, include_downloads: bool = False) -> bool:
        """
        Create a zip backup of ObtainHub data.
        
        Args:
            output_path: Path to the output zip file
            include_downloads: Whether to include the download folder
            
        Returns:
            True if successful
        """
        files = self.collect_files_to_backup()
        
        if include_downloads:
            download_dir = self.get_ohub_paths()["download_dir"]
            if download_dir.exists():
                for file_path in download_dir.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(download_dir)
                        files[f"downloads/{rel_path}"] = file_path
        
        # Add metadata
        metadata = {
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "ohub_version": self._get_ohub_version(),
            "includes_downloads": include_downloads,
            "files": list(files.keys()),
            "github_token": self.config.github_token or "",
        }
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                
                # Write all files to temp directory
                for rel_path, src_path in files.items():
                    dest = tmpdir_path / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest)
                
                # Write metadata
                meta_file = tmpdir_path / "metadata.json"
                with open(meta_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                
                # Create zip
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, filenames in os.walk(tmpdir_path):
                        for filename in filenames:
                            file_path = Path(root) / filename
                            arc_path = file_path.relative_to(tmpdir_path)
                            zf.write(file_path, arc_path)
            
            return True
        except Exception as e:
            print(f"Failed to create backup: {e}")
            return False
    
    def _get_ohub_version(self) -> str:
        """Get ObtainHub version."""
        try:
            from obtainhub import __version__
            return __version__
        except Exception:
            return "unknown"
    
    def restore_from_zip(
        self,
        zip_path: Path,
        target_config_dir: Optional[Path] = None,
        target_state_dir: Optional[Path] = None,
        target_download_dir: Optional[Path] = None,
        restore_token: bool = True,
    ) -> bool:
        """
        Restore ObtainHub from a backup zip.
        
        Args:
            zip_path: Path to the backup zip
            target_config_dir: Target config directory (default: current)
            target_state_dir: Target state directory (default: current)
            target_download_dir: Target download directory (default: current)
            restore_token: Whether to restore GitHub token to keyring
            
        Returns:
            True if successful
        """
        if not zip_path.exists():
            print(f"Backup file not found: {zip_path}")
            return False
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                
                # Extract zip
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmpdir_path)
                
                # Read metadata
                meta_file = tmpdir_path / "metadata.json"
                metadata = {}
                if meta_file.exists():
                    with open(meta_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                
                # Determine target directories
                paths = self.get_ohub_paths()
                config_dir = target_config_dir or paths["config_dir"]
                state_dir = target_state_dir or paths["state_dir"]
                download_dir = target_download_dir or paths["download_dir"]
                
                # Restore config
                config_src = tmpdir_path / "config.json"
                if config_src.exists():
                    config_dir.mkdir(parents=True, exist_ok=True)
                    dest = config_dir / "config.json"
                    shutil.copy2(config_src, dest)
                    
                    # Reload config manager to new location
                    if target_config_dir:
                        self.config_manager.config_dir = config_dir
                        self.config_manager.config_file = dest
                
                # Restore state
                state_src = tmpdir_path / "state.json"
                if state_src.exists():
                    state_dir.mkdir(parents=True, exist_ok=True)
                    dest = state_dir / "state.json"
                    shutil.copy2(state_src, dest)
                    
                    if target_state_dir:
                        self.state_manager.state_file = dest
                
                # Restore extra config files
                extra_config = tmpdir_path / "config_extra"
                if extra_config.exists():
                    config_dir.mkdir(parents=True, exist_ok=True)
                    for src in extra_config.glob("*"):
                        shutil.copy2(src, config_dir / src.name)
                
                # Restore extra state files
                extra_state = tmpdir_path / "state_extra"
                if extra_state.exists():
                    state_dir.mkdir(parents=True, exist_ok=True)
                    for src in extra_state.glob("*"):
                        shutil.copy2(src, state_dir / src.name)
                
                # Restore downloads
                downloads_src = tmpdir_path / "downloads"
                if downloads_src.exists() and metadata.get("includes_downloads"):
                    download_dir.mkdir(parents=True, exist_ok=True)
                    for src in downloads_src.rglob("*"):
                        if src.is_file():
                            rel = src.relative_to(downloads_src)
                            dest = download_dir / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
                
                # Restore token to keyring if requested
                if restore_token and metadata.get("github_token"):
                    try:
                        import keyring
                        keyring.set_password("obtainhub", "github_token", metadata["github_token"])
                        print("GitHub token restored to keyring")
                    except Exception as e:
                        print(f"Warning: Could not restore token to keyring: {e}")
                
                return True
        except Exception as e:
            print(f"Failed to restore from backup: {e}")
            return False
    
    def uninstall(
        self,
        backup_path: Optional[Path] = None,
        include_downloads: bool = False,
        force: bool = False,
    ) -> bool:
        """
        Uninstall ObtainHub completely.
        
        Args:
            backup_path: If provided, create backup zip at this path before uninstalling
            include_downloads: Include download folder in backup
            force: Skip confirmation prompts
            
        Returns:
            True if successful
        """
        if not force:
            print("WARNING: This will completely remove ObtainHub from your system.")
            print("The following will be removed:")
            paths = self.get_ohub_paths()
            print(f"  - Config: {paths['config_dir']}")
            print(f"  - State: {paths['state_dir']}")
            print(f"  - Downloads: {paths['download_dir']} {'(included in backup)' if include_downloads else '(NOT backed up)'}")
            
            if backup_path:
                print(f"\nA backup will be created at: {backup_path}")
            
            confirm = input("\nAre you sure you want to continue? [y/N]: ")
            if confirm.lower() != "y":
                print("Aborted.")
                return False
        
        # Create backup if requested
        if backup_path:
            print(f"Creating backup at {backup_path}...")
            if not self.create_backup_zip(backup_path, include_downloads):
                print("Failed to create backup. Aborting uninstall.")
                return False
            print("Backup created successfully.")
        
        # Remove all ObtainHub data
        paths = self.get_ohub_paths()
        removed = []
        
        # Remove config directory
        if paths["config_dir"].exists():
            shutil.rmtree(paths["config_dir"])
            removed.append(f"Config directory: {paths['config_dir']}")
        
        # Remove state directory
        if paths["state_dir"].exists():
            shutil.rmtree(paths["state_dir"])
            removed.append(f"State directory: {paths['state_dir']}")
        
        # Remove downloads
        if paths["download_dir"].exists():
            shutil.rmtree(paths["download_dir"])
            removed.append(f"Download directory: {paths['download_dir']}")
        
        # Try to remove the ohub.exe itself (if we can find it)
        exe_path = self._find_ohub_exe()
        if exe_path and exe_path.exists():
            try:
                # On Windows, we can't delete the running exe
                # Schedule it for deletion on reboot or just warn
                if os.name == "nt":
                    print(f"Note: Cannot remove running executable {exe_path}. It will be removed on next reboot.")
                    # Could use MoveFileEx with MOVEFILE_DELAY_UNTIL_REBOOT
                else:
                    exe_path.unlink()
                    removed.append(f"Executable: {exe_path}")
            except Exception as e:
                print(f"Warning: Could not remove executable: {e}")
        
        # Clear token from keyring
        try:
            import keyring
            keyring.delete_password("obtainhub", "github_token")
            removed.append("GitHub token (from keyring)")
        except Exception:
            pass
        
        print("\nObtainHub has been uninstalled.")
        print("Removed:")
        for item in removed:
            print(f"  - {item}")
        
        if backup_path:
            print(f"\nBackup saved to: {backup_path}")
            print("To restore on this or another machine, run:")
            print(f"  ohub self-uninstall --restore {backup_path}")
        
        return True
    
    def _find_ohub_exe(self) -> Optional[Path]:
        """Try to find the ohub.exe executable."""
        # Check common locations
        candidates = [
            Path(sys.executable),
            Path(sys.argv[0]),
        ]
        
        # Check PATH
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("ohub.exe", "ObtainHub.exe", "ohub"):
                candidates.append(Path(path_dir) / name)
        
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    return candidate.resolve()
            except Exception:
                pass
        
        return None


def cmd_self_uninstall(
    parsed,
    config_manager: ConfigManager,
    state_manager: StateManager,
) -> int:
    """Handle self-uninstall command."""
    from obtainhub import __version__
    
    uninstaller = SelfUninstaller(config_manager, state_manager)
    
    if parsed.restore:
        # Restore from backup
        backup_path = Path(parsed.restore)
        if not backup_path.exists():
            print(f"Backup file not found: {backup_path}")
            return 1
        
        print(f"Restoring from {backup_path}...")
        target_config = Path(parsed.target_config) if parsed.target_config else None
        target_state = Path(parsed.target_state) if parsed.target_state else None
        target_downloads = Path(parsed.target_downloads) if parsed.target_downloads else None
        
        if uninstaller.restore_from_zip(
            backup_path,
            target_config_dir=target_config,
            target_state_dir=target_state,
            target_download_dir=target_downloads,
            restore_token=not parsed.no_token,
        ):
            print("Restore completed successfully.")
            print("Run 'ohub' to verify the installation.")
            return 0
        else:
            return 1
    
    # Normal uninstall
    backup_path = Path(parsed.backup) if parsed.backup else None
    success = uninstaller.uninstall(
        backup_path=backup_path,
        include_downloads=parsed.include_downloads,
        force=parsed.force,
    )
    
    return 0 if success else 1