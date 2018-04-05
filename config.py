import os

# VFS home props and files
VFS_HOME_ENV_VAR = 'VFS_HOME'
VFS_HOME_DEFAULT = os.path.expanduser('~/.vfs/home')
VFS_DATA_DIR = 'data'
VFS_BACKUP_DIR = 'backup'

# VFS meta files
VFS_META_FILE = 'meta'
VFS_COLLECTIONS_DIR = 'collections'
VFS_DISCS_FILE = 'discs'
VFS_SAVE_MAPS_FILE = 'save_maps'
VFS_FILTERS_DIR = 'filters'

# Collections meta files
COLLECTION_META_FILE = 'meta'
COLLECTION_STATS_FILE = 'stats'

# Backup
BACKUP_META_FILE = 'meta'
BACKUP_VFS_DIR = 'vfs'
BACKUP_VIRTUAL_DIR = 'virtual'

# VFS file extensions
VFS_FILE_EXT = '.vfs'
PROP_FILE_EXT = '.props' + VFS_FILE_EXT
DUP_FILE_EXT = '.dedup.json' + VFS_FILE_EXT
MERGE_FILE_EXT = '.merge_conflicts.json' + VFS_FILE_EXT

# Save ops
SAVE_FILE_NAME = 'save-status'
DIR_SIZE = 1  # bytes

# Freeze
FREEZE_PROP = 'frozen'
FREEZE_VAL_TRUE = True
FREEZE_VAL_FALSE = None

# Filter
FILTER_NAME_MIMETYPE = 'filter-by-mime'
FILTER_NAME_SIZE = 'filter-by-size'
FILTER_NAME_PROP = 'filter-by-prop'
FILTER_MIMETYPE_UNKNOWN = 'unknown'

# Logging
LOG_DIR_ENV_VAR = 'VFS_LOG_DIR'
LOG_DIR_DEFAULT = os.path.expanduser('~/.vfs/logs')
LOG_FILE_NAME = "vfs.log"

# Tests
TEST_DIR = './vfs_temp_test_dir'
