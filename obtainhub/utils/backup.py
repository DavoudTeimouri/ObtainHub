"""Backup rotation utility for ObtainHub.

Provides consistent backup rotation across all backup operations:
- config repair
- self-uninstall
- config backup
- apps backup
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime


DEFAULT_RETENTION_COUNT = 2
MAX_RETENTION_COUNT = 10
MIN_RETENTION_COUNT = 1


def get_backup_retention_count(config_value: Optional[int] = None) -> int:
    """Get the configured backup retention count (1-10, default 2)."""
    if config_value is not None:
        return max(MIN_RETENTION_COUNT, min(MAX_RETENTION_COUNT, config_value))
    return DEFAULT_RETENTION_COUNT


def _parse_backup_timestamp(suffix: str):
    """Parse timestamp from backup filename suffix."""
    # Try format with microseconds first: YYYYMMDD_HHMMSS_ffffff
    try:
        return datetime.strptime(suffix, "%Y%m%d_%H%M%S_%f")
    except ValueError:
        pass
    # Try format without microseconds: YYYYMMDD_HHMMSS
    try:
        return datetime.strptime(suffix, "%Y%m%d_%H%M%S")
    except ValueError:
        pass
    # Try numeric format
    try:
        num = int(suffix)
        return datetime.fromtimestamp(num)
    except ValueError:
        pass
    return None


def rotate_backups(file_path: Path, retention_count: Optional[int] = None) -> List[Path]:
    """
    Rotate backups for a given file.
    
    Keeps the most recent `retention_count` backups, deletes older ones.
    Backup naming pattern: {file_path}.bak.{timestamp}
    
    Args:
        file_path: The original file being backed up
        retention_count: Number of backups to keep (default: 2)
        
    Returns:
        List of remaining backup file paths (newest first)
    """
    if retention_count is None:
        retention_count = DEFAULT_RETENTION_COUNT
    
    retention_count = max(MIN_RETENTION_COUNT, min(MAX_RETENTION_COUNT, retention_count))
    
    # Find existing backups
    backup_pattern = f"{file_path.name}.bak.*"
    parent = file_path.parent
    existing_backups = []
    
    for backup in parent.glob(backup_pattern):
        # Parse timestamp from backup name
        try:
            suffix = backup.name.replace(f"{file_path.name}.bak.", "")
            ts = _parse_backup_timestamp(suffix)
            if ts:
                existing_backups.append((ts, backup))
        except Exception:
            pass
    
    # Sort by timestamp (newest first)
    existing_backups.sort(key=lambda x: x[0], reverse=True)
    
    # Delete excess backups
    deleted = []
    for ts, backup in existing_backups[retention_count:]:
        try:
            backup.unlink()
            deleted.append(backup)
        except Exception:
            pass
    
    # Return remaining backups
    return [b for _, b in existing_backups[:retention_count]]


def create_backup(file_path: Path, retention_count: Optional[int] = None) -> Optional[Path]:
    """
    Create a timestamped backup of a file and rotate old backups.
    
    Args:
        file_path: File to backup
        retention_count: Number of backups to keep (default: 2)
        
    Returns:
        Path to the created backup, or None if original doesn't exist
    """
    if not file_path.exists():
        return None
    
    if retention_count is None:
        retention_count = DEFAULT_RETENTION_COUNT
    
    # Create timestamped backup with unique timestamp
    import time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = file_path.parent / f"{file_path.name}.bak.{timestamp}"
    
    try:
        shutil.copy2(file_path, backup_path)
    except Exception:
        return None
    
    # Rotate old backups
    rotate_backups(file_path, retention_count)
    
    return backup_path


def create_backups(file_paths: List[Path], retention_count: Optional[int] = None) -> List[Path]:
    """
    Create backups for multiple files with rotation.
    
    Args:
        file_paths: List of files to backup
        retention_count: Number of backups to keep per file (default: 2)
        
    Returns:
        List of created backup paths
    """
    created = []
    for file_path in file_paths:
        backup = create_backup(file_path, retention_count)
        if backup:
            created.append(backup)
    return created


def restore_from_backup(backup_path: Path, target_path: Optional[Path] = None) -> bool:
    """
    Restore a file from its backup.
    
    Args:
        backup_path: Path to the backup file
        target_path: Where to restore (defaults to original location)
        
    Returns:
        True if successful
    """
    if not backup_path.exists():
        return False
    
    if target_path is None:
        # Derive original path from backup name
        # backup_path = original.bak.timestamp
        name = backup_path.name
        if ".bak." in name:
            original_name = name.split(".bak.")[0]
            target_path = backup_path.parent / original_name
        else:
            return False
    
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, target_path)
        return True
    except Exception:
        return False


def list_backups(file_path: Path) -> List[Path]:
    """List all backups for a file, newest first."""
    parent = file_path.parent
    pattern = f"{file_path.name}.bak.*"
    backups = []
    for backup in parent.glob(pattern):
        try:
            suffix = backup.name.replace(f"{file_path.name}.bak.", "")
            ts = _parse_backup_timestamp(suffix)
            if ts:
                backups.append((ts, backup))
        except Exception:
            pass
    backups.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in backups]