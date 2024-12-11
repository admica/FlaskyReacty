#!/opt/pcapserver/venv_linux/bin/python3
"""
PCAP Analysis functions
PATH: ./analysis_functions.py
"""
import os
import sys
import logging
import configparser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

class CallerPathFilter(logging.Filter):
    """Filter that corrects the caller information in log records."""

    def filter(self, record):
        """
        Modify the record to use the correct caller information.
        Skip past SimpleLogger's internal frames to find the actual caller.
        """
        # Start with the current frame
        frame = sys._getframe(0)

        # Walk up until we're out of SimpleLogger's code
        while frame:
            code = frame.f_code
            if (code.co_filename != __file__ and
                'logging' not in code.co_filename):
                # Found the caller's frame - update the record
                record.filename = os.path.basename(code.co_filename)
                record.lineno = frame.f_lineno
                record.funcName = code.co_name
                record.pathname = code.co_filename
                break
            frame = frame.f_back

        return True

class SimpleLogger:
    """
    A streamlined, thread-safe logging class with file rotation and fallback capabilities.
    Includes source file, line number, and function name in log output.

    Example usage:
        logger = SimpleLogger('myLogName', app_name='myapp')
        logger.info("Application started")

        # Output example:
        # 2024-10-31_10:11:12 myLogName INFO [myapp.py:42 myfunction] Application started
    """

    # Default configuration if no config.ini is found
    DEFAULT_CONFIG = {
        'app_name': 'autopcap',             # Default application name
        'log_path': '/opt/pcapserver/logs', # Default log directory
        'max_size_mb': 1024,                # Default max file size in MB
        'backup_count': 3,                  # Default number of backup files
        'console_output': False,            # Default console output setting
        'dir_perms': 0o770,                 # Default dir permissions (rwxrwx---)
        'file_perms': 0o640                 # Default file permissions (rw-r-----)
    }

    # Standard log format to use across all handlers
    LOG_FORMAT = '%(asctime)s %(name)s %(levelname)s [%(filename)s:%(lineno)d %(funcName)s] %(message)s'
    DATE_FORMAT = '%Y-%m-%d_%H:%M:%S'

    @classmethod
    def _load_config(cls, app_name: str) -> dict:
        """Load configuration from config.ini with fallback to defaults."""
        config = cls.DEFAULT_CONFIG.copy()  # Start with default values
        config['app_name'] = app_name  # Override default app_name with provided value

        try:
            parser = configparser.ConfigParser()

            # Check multiple common config locations
            config_paths = [
                'config.ini',                    # Current dir
                'conf/config.ini',               # Config dir
                f'/opt/{app_name}/config.ini',   # Application config dir
                f'/etc/{app_name}/config.ini'    # System config dir
            ]

            # Try to find and read a config file
            found_config = False
            for path in config_paths:
                try:
                    if os.path.exists(path):
                        parser.read(path)
                        found_config = True
                        break
                except Exception as e:
                    pass

            # Update config with values from file if found
            if found_config and 'LOG' in parser:
                logging_config = parser['LOG']
                config.update({
                    'log_path': logging_config.get('log_path', config['log_path']),
                    'max_size_mb': logging_config.getint('max_size', config['max_size_mb']) // (1024 * 1024),  # Convert bytes to MB
                    'backup_count': logging_config.getint('backup_count', config['backup_count']),
                    'console_output': logging_config.getboolean('console_output', config['console_output']),
                    'dir_perms': int(logging_config.get('dir_perms', '0o770'), 8),
                    'file_perms': int(logging_config.get('file_perms', '0o640'), 8)
                })
        except Exception as e:
            print(f"Warning: Error loading config.ini, using defaults: {str(e)}", file=sys.stderr)

        return config

    def __init__(
        self,
        log_name: str,
        app_name: Optional[str] = None,
        log_path: Optional[str] = None,
        max_size_mb: Optional[int] = None,
        backup_count: Optional[int] = None,
        console_output: Optional[bool] = None,
        dir_perms: Optional[int] = None,
        file_perms: Optional[int] = None
    ):
        """
        Initialize the logger with given or default parameters.

        Args:
            log_name: Name for the log file (without .log extension)
            app_name: Application name for config file lookup (optional)
            log_path: Directory to store log files (optional)
            max_size_mb: Maximum size of each log file in MB (optional)
            backup_count: Number of backup files to keep (optional)
            console_output: Whether to output to console (optional)
            dir_perms: Directory permissions in octal (optional)
            file_perms: File permissions in octal (optional)
        """
        # Use provided app_name or default from DEFAULT_CONFIG
        self.app_name = app_name if app_name is not None else self.DEFAULT_CONFIG['app_name']

        # Load defaults from config file
        config = self._load_config(self.app_name)  # Get config values with fallbacks

        # Set instance variables with priority: passed args > config > defaults
        self.log_name = f"{log_name}.log" # Add .log extension to the name
        self.log_path = log_path if log_path is not None else config['log_path']
        self.max_size_mb = max_size_mb if max_size_mb is not None else config['max_size_mb']
        self.backup_count = backup_count if backup_count is not None else config['backup_count']
        self.console_output = console_output if console_output is not None else config['console_output']
        self.dir_perms = dir_perms if dir_perms is not None else config['dir_perms']
        self.file_perms = file_perms if file_perms is not None else config['file_perms']

        self.logger: Optional[logging.Logger] = None

        try:
            # Normalize the log path
            self.log_path = str(Path(self.log_path).resolve())  # Convert to absolute path

            # Create logs directory if it doesn't exist with specified permissions
            os.makedirs(self.log_path, mode=self.dir_perms, exist_ok=True)

            # Initialize the logger
            self.logger = logging.getLogger(log_name)  # Use log_name directly for cleaner output
            self.logger.setLevel(logging.DEBUG)  # Capture all log levels

            # Add our caller path filter to correct the caller information
            self.logger.addFilter(CallerPathFilter())

            # Only add handlers if none exist
            if not self.logger.handlers:
                handlers = []

                # Try to create file handler
                try:
                    max_bytes = self.max_size_mb * 1024 * 1024  # Convert MB to bytes
                    log_file_path = os.path.join(self.log_path, self.log_name)

                    # Create file handler with specified permissions
                    file_handler = RotatingFileHandler(
                        filename=log_file_path,
                        maxBytes=max_bytes,
                        backupCount=self.backup_count,
                        encoding='utf-8',
                        delay=True  # Don't create file until first write
                    )

                    # Set file permissions when the file is created
                    def on_file_creation(filename):
                        os.chmod(filename, self.file_perms)

                    # Hook into the file creation
                    original_do_rollover = file_handler.doRollover
                    def custom_do_rollover():
                        original_do_rollover()
                        # Set permissions on the new file after rotation
                        on_file_creation(file_handler.baseFilename)
                    file_handler.doRollover = custom_do_rollover

                    # Set initial file permissions
                    file_handler.stream = open(log_file_path, file_handler.mode, encoding=file_handler.encoding)
                    on_file_creation(log_file_path)

                    file_formatter = logging.Formatter(self.LOG_FORMAT, datefmt=self.DATE_FORMAT)
                    file_handler.setFormatter(file_formatter)
                    handlers.append(file_handler)

                except (OSError, PermissionError) as e:
                    print(f"Warning: Failed to create file handler: {str(e)}", file=sys.stderr)

                # Add console handler if requested or if file handler failed
                if self.console_output or not handlers:
                    console_handler = logging.StreamHandler(sys.stdout)
                    console_formatter = logging.Formatter(self.LOG_FORMAT, datefmt=self.DATE_FORMAT)
                    console_handler.setFormatter(console_formatter)
                    handlers.append(console_handler)

                # Add all handlers to logger
                for handler in handlers:
                    self.logger.addHandler(handler)

        except Exception as e:
            # Fall back to basic console logger if everything else fails
            print(f"Warning: Failed to initialize logger: {str(e)}", file=sys.stderr)
            self.logger = logging.getLogger(log_name)  # Use log_name for consistency
            self.logger.setLevel(logging.DEBUG)

            # Basic console handler with same format
            console_handler = logging.StreamHandler(sys.stdout)
            basic_formatter = logging.Formatter(self.LOG_FORMAT, datefmt=self.DATE_FORMAT)
            console_handler.setFormatter(basic_formatter)
            self.logger.addHandler(console_handler)

    def _log(self, level: int, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Internal method to safely handle all logging."""
        try:
            # Convert each message to string and join them
            formatted_messages = [
                str(msg) if not isinstance(msg, Exception) else str(msg)
                for msg in messages
            ]
            final_message = " ".join(formatted_messages)
            self.logger.log(level, final_message)
        except Exception as e:
            print(f"Failed to log message: {str(e)}", file=sys.stderr)

    def d(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log debug messages, short hand."""
        self._log(logging.DEBUG, *messages)

    def debug(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log debug messages."""
        self._log(logging.DEBUG, *messages)

    def i(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log info messages, short hand."""
        self._log(logging.INFO, *messages)

    def info(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log info messages."""
        self._log(logging.INFO, *messages)

    def w(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log warning messages, short hand."""
        self._log(logging.WARNING, *messages)

    def warning(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log warning messages."""
        self._log(logging.WARNING, *messages)

    def warn(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log warning messages, alternate name."""
        self._log(logging.WARNING, *messages)

    def e(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log error messages, short hand."""
        self._log(logging.ERROR, *messages)

    def error(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log error messages."""
        self._log(logging.ERROR, *messages)

    def c(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log critical messages, short hand."""
        self._log(logging.CRITICAL, *messages)

    def critical(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log critical messages."""
        self._log(logging.CRITICAL, *messages)

    def exception(self, *messages: Union[str, Exception, dict, list, tuple, set, int, float, bool]) -> None:
        """Log exception messages with traceback."""
        try:
            final_message = " ".join(str(msg) for msg in messages)
            self.logger.exception(final_message)
        except Exception as e:
            print(f"Failed to log exception: {str(e)}", file=sys.stderr)

if __name__ == '__main__':
    """Test the SimpleLogger with various scenarios."""

    def test_function():
        """Test function to demonstrate function name in logs."""
        logger.debug("Debug from test function")
        logger.info("Info from test function")
        logger.warning("Warning from test function")

    # Test with default settings
    logger = SimpleLogger('testapp')

    # Basic logging test
    logger.info("Starting tests...")

    # Test function name logging
    test_function()

    # Test exception logging
    try:
        result = 1 / 0
    except Exception as e:
        logger.exception("Caught a division by zero error!")

    # Test nested function calling
    def outer_function():
        def inner_function():
            logger.error("Error from inner function")
        inner_function()

    outer_function()

    # Test logging with a loop to check rotation
    print("\nTesting file rotation...")
    for i in range(100):
        logger.debug(f"Test message {i} for rotation")

    print("\nTests complete! Check the log files to see the output format.")
