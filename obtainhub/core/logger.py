"""Structured console logger for ObtainHub."""

import logging
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, TextIO
from logging.handlers import RotatingFileHandler


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat:
    """Log format constants."""
    CONSOLE = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    FILE = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
    DATE = "%Y-%m-%d %H:%M:%S"


class ObtainHubLogger:
    """Structured console and file logger for ObtainHub."""
    
    _instance: Optional["ObtainHubLogger"] = None
    _logger: logging.Logger
    
    def __new__(cls) -> "ObtainHubLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._logger = logging.getLogger("obtainhub")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        self._console_handler: Optional[logging.StreamHandler] = None
        self._file_handler: Optional[RotatingFileHandler] = None
        self._console_level = LogLevel.INFO
        self._file_level = LogLevel.DEBUG
        self._setup_console_handler(sys.stdout)
    
    def _setup_console_handler(self, stream: TextIO = sys.stdout) -> None:
        """Set up console handler with colored output."""
        if self._console_handler:
            self._logger.removeHandler(self._console_handler)
        
        self._console_handler = logging.StreamHandler(stream)
        self._console_handler.setLevel(self._console_level.value)
        formatter = logging.Formatter(LogFormat.CONSOLE, datefmt=LogFormat.DATE)
        self._console_handler.setFormatter(formatter)
        self._logger.addHandler(self._console_handler)
    
    def setup_file_logging(
        self,
        log_file: Path,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        level: LogLevel = LogLevel.DEBUG,
    ) -> None:
        """Set up rotating file handler for persistent logging."""
        if self._file_handler:
            self._logger.removeHandler(self._file_handler)
        
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        self._file_handler.setLevel(level.value)
        formatter = logging.Formatter(LogFormat.FILE, datefmt=LogFormat.DATE)
        self._file_handler.setFormatter(formatter)
        self._logger.addHandler(self._file_handler)
        self._file_level = level
    
    def set_console_level(self, level: LogLevel) -> None:
        """Set console log level."""
        self._console_level = level
        if self._console_handler:
            self._console_handler.setLevel(level.value)
    
    def set_file_level(self, level: LogLevel) -> None:
        """Set file log level."""
        self._file_level = level
        if self._file_handler:
            self._file_handler.setLevel(level.value)
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        self._logger.exception(msg, *args, **kwargs)
    
    def success(self, msg: str, *args, **kwargs) -> None:
        """Log success message (info level with success prefix)."""
        self._logger.info(f"✓ {msg}", *args, **kwargs)
    
    def info_verbose(self, msg: str, *args, **kwargs) -> None:
        """Log info message only if verbose mode enabled."""
        if self._console_level <= LogLevel.DEBUG:
            self._logger.info(msg, *args, **kwargs)
    
    def progress(self, msg: str, *args, **kwargs) -> None:
        """Log progress message without newline (for progress bars)."""
        self._logger.info(msg, *args, **kwargs, extra={"end": "\r"})
    
    def section(self, title: str) -> None:
        """Log a section header."""
        self._logger.info(f"\n{'=' * 60}")
        self._logger.info(f"  {title}")
        self._logger.info(f"{'=' * 60}\n")
    
    def subsection(self, title: str) -> None:
        """Log a subsection header."""
        self._logger.info(f"\n--- {title} ---")


def get_logger() -> ObtainHubLogger:
    """Get the global ObtainHub logger instance."""
    return ObtainHubLogger()


def setup_logging(
    log_file: Optional[Path] = None,
    console_level: LogLevel = LogLevel.INFO,
    file_level: LogLevel = LogLevel.DEBUG,
    verbose: bool = False,
) -> ObtainHubLogger:
    """Initialize and configure the global logger."""
    logger = get_logger()
    logger.set_console_level(LogLevel.DEBUG if verbose else console_level)
    if log_file:
        logger.setup_file_logging(log_file, level=file_level)
    return logger