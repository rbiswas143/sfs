import logging.handlers
import os
import sys

import config


def get_log_dir():
    try:
        path = os.environ[config.LOG_DIR_ENV_VAR]
    except KeyError:
        path = config.LOG_DIR_DEFAULT
    return path


# Create log directory if it does not exist
try:
    os.makedirs(get_log_dir())
except OSError:
    pass

# Formatters
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] " +
                                   "|| %(module)s :: %(funcName)s :: %(lineno)s || %(message)s")
cli_formatter = logging.Formatter(" > %(message)s")

# File Handler
LOG_LEVEL_FILE = 'DEBUG'
file_handler = logging.handlers.RotatingFileHandler(os.path.join(get_log_dir(), config.LOG_FILE_NAME), mode='a',
                                                    maxBytes=5 * 1024 * 1024, backupCount=10)
file_handler.setFormatter(file_formatter)
file_handler.setLevel(LOG_LEVEL_FILE)

# CLI Handler
LOG_LEVEL_CLI = 'INFO'
cli_handler = logging.StreamHandler(stream=sys.stdout)
cli_handler.setFormatter(cli_formatter)
cli_handler.setLevel(LOG_LEVEL_CLI)

# Primary logger
logger = logging.getLogger()
logger.addHandler(file_handler)
logger.addHandler(cli_handler)
logger.setLevel('DEBUG')

logger.debug('Logging has been configured')
