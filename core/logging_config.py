"""Console and optional rotating-file logging shared by application entry points."""

import logging
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from utils.env_vars import get_env_var

_FORMAT: Final = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT: Final = "%Y-%m-%d %H:%M:%S"
_MAX_LOG_BYTES: Final = 10 * 1024 * 1024
_BACKUP_COUNT: Final = 5
_ENV_FILE: Final = Path(__file__).resolve().parents[1] / ".env"
_LOG_LEVELS: Final[dict[str, int]] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


class LoggingConfigurationError(ValueError):
    """Raised when a configured log level is unsupported."""

    def __init__(self, level: str) -> None:
        supported = ", ".join(_LOG_LEVELS)
        super().__init__(f"Unsupported LOG_LEVEL: {level!r}. Supported values: {supported}.")


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Minimum log level and an optional file path relative to the working directory."""

    level: int = logging.INFO
    log_file: Path | None = None


def load_logging_config() -> LoggingConfig:
    """Read the project's .env file without overriding existing environment variables."""
    load_dotenv(dotenv_path=_ENV_FILE)
    raw_level = get_env_var("LOG_LEVEL", "INFO").strip().upper()
    try:
        level = _LOG_LEVELS[raw_level]
    except KeyError as exc:
        raise LoggingConfigurationError(raw_level) from exc

    raw_file = get_env_var("LOG_FILE", "").strip()
    return LoggingConfig(level=level, log_file=Path(raw_file) if raw_file else None)


def configure_logging(config: LoggingConfig | None = None) -> None:
    """Configure logging at process startup; repeated calls replace previous handlers."""
    if config is None:
        config = load_logging_config()

    access_logger = logging.getLogger("uvicorn.access")
    access_log_enabled = bool(access_logger.handlers) or access_logger.propagate

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.log_file is not None:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                config.log_file,
                maxBytes=_MAX_LOG_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=config.level,
        format=_FORMAT,
        datefmt=_DATE_FORMAT,
        handlers=handlers,
        force=True,
    )

    # Uvicorn installs its own handlers before importing the app. Propagate once
    # through the shared root handlers so server messages also reach the log file.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(config.level)
        # Preserve Uvicorn's --no-access-log setting, including on reconfiguration.
        logger.propagate = name != "uvicorn.access" or access_log_enabled
        logger.disabled = False
