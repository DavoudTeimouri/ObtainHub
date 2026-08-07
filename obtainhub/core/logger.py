"""Structured logging for ObtainHub."""

import json
import logging
import logging.handlers
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class LogLevel(Enum):
    """Log levels matching standard logging levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogRecord:
    """Structured log record."""
    timestamp: str
    level: str
    logger: str
    message: str
    extra: Optional[dict] = None


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_record = LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            extra=getattr(record, "extra", None),
        )
        return json.dumps(log_record.__dict__, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = record.levelname.ljust(8)
        logger_name = record.name.split(".")[-1]
        return f"{timestamp} {level} [{logger_name}] {record.getMessage()}"


class StructuredLogger:
    """Wrapper around stdlib logger with structured logging support."""
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
    
    def debug(self, message: str, **extra):
        self._logger.debug(message, extra={"extra": extra} if extra else None)
    
    def info(self, message: str, **extra):
        self._logger.info(message, extra={"extra": extra} if extra else None)
    
    def warning(self, message: str, **extra):
        self._logger.warning(message, extra={"extra": extra} if extra else None)
    
    def error(self, message: str, **extra):
        self._logger.error(message, extra={"extra": extra} if extra else None)
    
    def critical(self, message: str, **extra):
        self._logger.critical(message, extra={"extra": extra} if extra else None)
    
    def log(self, level: LogLevel, message: str, **extra):
        self._logger.log(level.value, message, extra={"extra": extra} if extra else None)


_LOGGERS: dict[str, StructuredLogger] = {}
_DEFAULT_LOGGER: Optional[StructuredLogger] = None


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    log_dir: Optional[Path] = None,
    console: bool = True,
    json_file: bool = True,
) -> None:
    """Set up global logging configuration.
    
    Args:
        level: Log level (default: INFO)
        log_dir: Directory for log files
        console: Enable console output
        json_file: Enable JSON file logging
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level.value)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level.value)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # JSON file handler
    if json_file and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        json_handler = logging.handlers.RotatingFileHandler(
            log_dir / "obtainhub.json",
            maxBytes=10_485_760,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        json_handler.setLevel(level.value)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    if name not in _LOGGERS:
        _LOGGERS[name] = StructuredLogger(logging.getLogger(name))
    return _LOGGERS[name]


def get_default_logger() -> StructuredLogger:
    """Get the default logger for the application."""
    global _DEFAULT_LOGGER
    if _DEFAULT_LOGGER is None:
        _DEFAULT_LOGGER = get_logger("obtainhub")
    return _DEFAULT_LOGGER