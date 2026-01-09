import logging
import sys
from typing import cast

# Color codes for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color

# Symbol map for each log level
LEVEL_SYMBOLS = {
    "DEBUG": f"{BLUE}ℹ{NC}",
    "INFO": f"{BLUE}ℹ{NC}",
    "SUCCESS": f"{GREEN}✓{NC}",
    "WARNING": f"{YELLOW}⚠{NC}",
    "ERROR": f"{RED}✗{NC}",
    "CRITICAL": f"{GREEN}✓{NC}",
}

# Custom log level
SUCCESS_LEVEL = 25
STDOUT_LEVEL = 26


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colored symbols based on log level"""

    def format(self, record: logging.LogRecord) -> str:
        # For stdout, don't add any symbols
        if record.levelno == STDOUT_LEVEL:
            return super().format(record)

        symbol = LEVEL_SYMBOLS.get(record.levelname, "")
        record.msg = f"{symbol} {record.msg}"
        return super().format(record)


class CCLogger(logging.Logger):
    """Custom logger with success and stdout methods"""

    def success(self, message: str, *args, **kwargs) -> None:
        """Log success message"""
        self.log(SUCCESS_LEVEL, message, *args, **kwargs)

    def stdout(self, message: str, *args, **kwargs) -> None:
        """Log a message to stdout"""
        self.log(STDOUT_LEVEL, message, *args, **kwargs)


configured = False


def configure_logging(level: str = "info") -> None:
    """
    Configure root logger.

    - All logs except STDOUT go to stderr.
    - STDOUT level logs go to stdout.
    - Log level is configurable (debug, info, warning, error, critical, none).
    """
    global configured
    if configured:
        return
    # Set custom logger class
    logging.setLoggerClass(CCLogger)

    # Add custom levels
    logging.SUCCESS = SUCCESS_LEVEL  # type: ignore
    logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
    logging.STDOUT = STDOUT_LEVEL  # type: ignore
    logging.addLevelName(STDOUT_LEVEL, "STDOUT")

    root_logger = logging.getLogger()

    # Only configure if not already configured
    if root_logger.handlers:
        return

    # Map string level to logging constant
    level_upper = level.upper()
    log_level = logging.getLevelName(level_upper)

    root_logger.setLevel(log_level)

    # Handler for stderr (all logs except stdout)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(log_level)
    stderr_handler.addFilter(lambda record: record.levelno != STDOUT_LEVEL)
    stderr_handler.setFormatter(ColoredFormatter("%(asctime)s %(message)s"))
    root_logger.addHandler(stderr_handler)

    # Handler for stdout (only for STDOUT level)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(STDOUT_LEVEL)
    stdout_handler.addFilter(lambda record: record.levelno == STDOUT_LEVEL)
    # No formatter needed, just output the message
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(stdout_handler)

    # Suppress noisy third-party logs
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    logging.getLogger("azure.mgmt").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("http.connectionpool").setLevel(logging.WARNING)
    configured = True


def get_logger(name: str) -> CCLogger:
    """
    Get a properly typed CCLogger instance.

    This should be called after configure_logging() has been called in main().

    Args:
        name: Logger name (usually __name__)

    Returns:
        CCLogger instance with success() method
    """
    configure_logging()
    return cast(CCLogger, logging.getLogger(name))
