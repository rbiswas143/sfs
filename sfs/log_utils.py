import logging.handlers
import os
import sys

import sfs.config as config


def _get_log_dir():
    """The log directory is first checked in the environment and then in the config file"""
    try:
        path = os.environ[config.LOG_DIR_ENV_VAR]
    except KeyError:
        path = config.LOG_DIR_DEFAULT
    return path


def cli_output(message):
    """
    Logs a message with severity equal to INFO
    The logging level of the CLI logger is also INFO and hence this logs the message on the terminal
    """
    cli_logger.info(message)


# Create log directory if it does not exist
os.makedirs(_get_log_dir(), exist_ok=True)

# File Handler

_file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] || %(module)s :: %(funcName)s :: %(lineno)s || %(message)s"
)
file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(_get_log_dir(), config.LOG_FILE_NAME),
    mode='a',
    maxBytes=config.LOG_FILE_MAX_SIZE,
    backupCount=config.LOG_FILE_NUM_BACKUPS
)
file_handler.setFormatter(_file_formatter)
file_handler.setLevel(config.LOG_LEVEL_FILE)

# CLI Handler

_cli_formatter = logging.Formatter("{}%(message)s".format(config.CLI_OUTPUT_PREFIX))
cli_handler = logging.StreamHandler(stream=sys.stdout)
cli_handler.setFormatter(_cli_formatter)

# File logger

logger = logging.getLogger('sfs')
logger.addHandler(file_handler)
logger.setLevel('DEBUG')

# CLI logger

cli_logger = logging.getLogger('sfs-cli')
cli_logger.addHandler(file_handler)
cli_logger.addHandler(cli_handler)
cli_logger.setLevel('DEBUG')
