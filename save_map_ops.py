# Operations at the Disc level

import core
from log_utils import logger


# CLI TARGET: List details for all added save mappings
def list_save_maps():
    vfs = core.get_current_vfs()
    all_save_maps = core.get_all_save_maps()
    if len(all_save_maps) == 0:
        logger.info('No save mappings have been added to VFS %s', vfs.name)
    else:
        logger.info('Following save mappings have been added:')
        for save_map in all_save_maps:
            logger.info('Virtual: %s\tActual: %s', save_map.virtual_dir, save_map.actual_dir)


# CLI TARGET: Add a new save mapping
def add_save_map(virtual_dir, actual_dir):
    vfs = core.get_current_vfs()
    core.add_save_map(virtual_dir, actual_dir)
    logger.info('Save mapping has successfully been added to VFS %s', vfs.name)


# CLI TARGET: Delete a save mapping
def del_save_maps():
    vfs = core.get_current_vfs()
    core.del_all_save_maps()
    logger.info('All save mappings have been deleted from the VFS %s', vfs.name)
