"""Structured logging for ObtainHub."""

import json
import logging
import logging.handlers
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class LogLevel(Enum):
    """Log levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


@dataclass
class LogRecord:
    """Structured log record."""
    timestamp: str
    level: str
    logger: str
    message: str
    context: Optional[dict[str, Any]] = None
    exception: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        data: dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
        }
        if self.context:
            data["context"] = self.context
        if self.exception:
            data["exception"] = self.exception
        return json.dumps(data, ensure_ascii=False)


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_record = LogRecord(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            context=getattr(record, 'context', None),
            exception=self.formatException(record.exc_info) if record.exc_info else None,
        )
        return log_record.to_json()


class ConsoleFormatter(logging.Formatter):
    """Console log formatter with colors."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'RESET': '\033[0m',
    }
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '') if self.use_colors else ''
        reset = self.COLORS['RESET'] if self.use_colors else ''
        
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level = f"{color}{record.levelname:8}{reset}"
        logger_name = f"{record.name}:"
        
        msg = record.getMessage()
        
        # Add context if present
        context = getattr(record, 'context', None)
        if context:
            ctx_str = " ".join(f"{k}={v}" for k, v in context.items())
            msg = f"{msg} [{ctx_str}]"
        
        return f"{timestamp} {level} {logger_name:<20} {msg}"


class StructuredLogger:
    """Structured logger with context support."""
    
    def __init__(self, name: str, logger: logging.Logger):
        self.name = name
        self.logger = logger
        self._context: dict[str, Any] = {}
    
    def bind(self, **kwargs) -> 'StructuredLogger':
        """Create a new logger with additional context."""
        new_logger = StructuredLogger(self.name, self.logger)
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal log method."""
        context = {**self._context, **kwargs}
        extra = {'context': context} if context else {}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        context = {**self._context, **kwargs}
        extra = {'context': context} if context else {}
        self.logger.exception(message, extra=extra)


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    log_dir: Optional[Path] = None,
    console: bool = True,
    json_file: bool = True,
) -> None:
    """Set up global logging configuration."""
    
    # Get log directory
    if log_dir is None:
        log_dir = Path.home() / ".local" / "share" / "obtainhub" / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Root logger - handle LogLevel enum, int, or string
    root_logger = logging.getLogger()
    if hasattr(level, 'value'):
        level_val = level.value
    elif isinstance(level, str):
        level_val = getattr(logging, level.upper(), logging.INFO)
    else:
        level_val = level
    root_logger.setLevel(level_val)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level_val)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # JSON file handler (rotating)
    if json_file:
        log_file = log_dir / "obtainhub.json"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8',
        )
        file_handler.setLevel(level_val)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Human-readable file handler
    log_file_txt = log_dir / "obtainhub.log"
    txt_handler = logging.handlers.RotatingFileHandler(
        log_file_txt,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    txt_handler.setLevel(level_val)
    txt_handler.setFormatter(ConsoleFormatter(use_colors=False))
    root_logger.addHandler(txt_handler)


def get_logger(name: str = "obtainhub") -> StructuredLogger:
    """Get a structured logger instance."""
    logger = logging.getLogger(name)
    return StructuredLogger(name, logger)


# Default logger
_default_logger: Optional[StructuredLogger] = None


def get_default_logger() -> StructuredLogger:
    """Get the default logger."""
    global _default_logger
    if _default_logger is None:
        _default_logger = get_logger("obtainhub")
    return _default_logger


__all__ = [
    'LogLevel',
    'LogRecord',
    'JSONFormatter',
    'ConsoleFormatter',
    'StructuredLogger',
    'setup_logging',
    'get_logger',
    'get_default_logger',
]