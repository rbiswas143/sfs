import os

SFS_ROOT_DIR = os.path.expanduser('~/.sfs')

# Logging
LOG_DIR_ENV_VAR = 'SFS_LOG_DIR'
LOG_DIR_DEFAULT = os.path.join(SFS_ROOT_DIR, 'logs')
LOG_FILE_NAME = 'sfs.log'
LOG_LEVEL_FILE = 'DEBUG'

# Rotating file logging
LOG_FILE_MAX_SIZE = 10 * 1024 * 1024
LOG_FILE_NUM_BACKUPS = 10

# CLI
CLI_OUTPUT_PREFIX = '>> '

# Tests
TEST_DIR = os.path.join(SFS_ROOT_DIR, 'tests')
