# Operations at the Collection level

import core
from log_utils import logger


# CLI TARGET: Show details of a collection corresponding to the specified name
def show_collection_by_name(col_name):
    logger.debug('Arguments: col_name%s', col_name)

    vfs = core.get_current_vfs()
    col = core.get_collection_by_name(col_name)
    if col is None:
        logger.info('Collection named %s has not been added to VFS %s', col_name, vfs.name)
    else:
        logger.info('Collection Name: %s', col.name)
        logger.info('Actual Base Directory: %s', col.actual_base)


# CLI TARGET: Show details of a collection that contains the specified path
def show_collection_by_path(col_path):
    logger.debug('Arguments: col_path%s', col_path)

    vfs = core.get_current_vfs()
    col = core.get_collection_by_path(col_path)
    if col is None:
        logger.info('Specified path %s is not part of any collection in the VFS %s', col_path, vfs.name)
    else:
        logger.info('Collection Name: %s', col.name)
        logger.info('Actual Base Directory: %s', col.actual_base)


# CLI TARGET: List details of all available collections in the current VFS
def list_collections():
    vfs = core.get_current_vfs()
    all_col = core.get_all_collections()
    if len(all_col) == 0:
        logger.info('No collections have been added to VFS %s', vfs.name)
    else:
        logger.info('Following Collections have been added:')
        for col in all_col:
            logger.info('%s (%s)', col.name, col.actual_base)


# CLI TARGET: Add a new collection
def add_col(col_name, col_path):
    logger.debug('Arguments: col_name%s, col_path:%s', col_name, col_path)

    vfs = core.get_current_vfs()
    core.setup_collection(col_name, col_path)
    logger.info('Collection %s at actual path %s has successfully been added to VFS %s', col_name, col_path, vfs.name)


# CLI TARGET: Sync a collection
def sync_col(col_name):
    logger.debug('Syncing collection: %s', col_name)
    core.sync_collection(col_name)
    logger.info('Collection %s has been synced', col_name)
