import logging
import sys
from logging.handlers import RotatingFileHandler

logging.getLogger("wavelink").setLevel(logging.WARNING)


# ANSI Color Codes
class ColorFormatter(logging.Formatter):
    """
    A custom logging formatter that applies ANSI color codes to log messages
    based on their severity level for enhanced console readability.

    Attributes
    ----------
    COLORS : dict
        A mapping of logging levels (e.g., INFO, WARNING) to their
        corresponding ANSI color escape sequences.
    RESET : str
        The ANSI escape sequence used to reset text formatting to default.

    Methods
    -------
    format(record)
        Formats the log record with ANSI color codes based on severity.
    """

    COLORS = {
        logging.DEBUG: "\033[94m",  # Blue
        logging.INFO: "\033[92m",  # Green
        logging.WARNING: "\033[93m",  # Yellow
        logging.ERROR: "\033[91m",  # Red
        logging.CRITICAL: "\033[41m\033[97m",  # White on Red
    }
    RESET = "\033[0m"

    def format(self, record):
        """
        Formats the specified log record as text, wrapping it with ANSI color
        escape sequences based on the log level.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to be formatted.

        Returns
        -------
        str
            The formatted log message string containing ANSI color codes.
        """
        log_color = self.COLORS.get(record.levelno, self.RESET)
        formatted = super().format(record)
        return f"{log_color}{formatted}{self.RESET}"


def get_logger(name: str):
    """
    Initializes and retrieves a logger instance configured with dual handlers:
    a colored console output and a plain text rotating file.

    This ensures that logs are easy to read during live debugging in the
    terminal while being persisted safely on disk without ANSI artifacts.

    Parameters
    ----------
    name : str
        The name of the logger, typically passed as `__name__`.

    Returns
    -------
    logging.Logger
        A pre-configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = ColorFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console Handler with Color
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        logger.addHandler(console)

        # File Handler (No color codes in files, it breaks text editors!)
        plain_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_h = RotatingFileHandler(
            "music_bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_h.setFormatter(plain_formatter)
        logger.addHandler(file_h)

    return logger
