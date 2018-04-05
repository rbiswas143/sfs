# Operations at the VFS level

import core
from log_utils import logger


# CLI TARGET: Show details of a VFS which contains the specified path
def show_vfs_by_path(path):
    logger.debug('Arguments: path%s', path)

    vfs = core.get_vfs_by_path(path)
    if vfs is None:
        logger.info('Specified path %s is not part of any available VFS', path)
    else:
        logger.info('VFS Name: %s', vfs.name)
        logger.info('Virtual Base Directory: %s', vfs.virtual_base)


# CLI TARGET: Show details of a VFS corresponding to the specified name
def show_vfs_by_name(name):
    logger.debug('Arguments: name%s', name)

    vfs = core.get_vfs_by_name(name)
    if vfs is None:
        logger.info('VFS with name %s does not exist', name)
    else:
        logger.info('VFS Name: %s', vfs.name)
        logger.info('Virtual Base Directory: %s', vfs.virtual_base)


# CLI TARGET: List details of all available VFS
def list_vfs():
    all_vfs = core.get_all_vfs()
    if len(all_vfs) == 0:
        logger.info('No VFS has been created yet')
    else:
        all_vfs.sort(key=lambda x: x.name)
        logger.info('Following VFS are available:')
        for vfs in all_vfs:
            logger.info('%s (%s)', vfs.name, vfs.virtual_base)


# CLI TARGET: Create a new VFS
def new_vfs(name, path):
    logger.debug('Arguments: name: %s, path: %s', name, path)

    core.setup_vfs(name, path)
    logger.info('New VFS named %s has successfully been setup at %s', name, path)


# CLI TARGET: Delete a VFS by name
def del_vfs(name):
    logger.debug('Arguments: name%s', name)

    core.del_vfs(name)
    logger.info('VFS named %s has been successfully deleted', name)
