# Ops related to freezing and unfreezing virtual directories

import os

import config
import core
from log_utils import logger


# Determine if a directory is frozen
def is_frozen(virtual_dir):
    frozen = core.get_virtual_path_prop(config.FREEZE_PROP, virtual_dir)
    if frozen == config.FREEZE_VAL_TRUE:
        return True
    elif frozen == config.FREEZE_VAL_FALSE:
        return False
    raise core.VfsException('Invalid value for property %s for virtual directory "%s": %s', config.FREEZE_PROP,
                            virtual_dir, frozen)


# Get the frozen parent, if any, of a directory else return None
def get_frozen_parent(virtual_dir):
    vfs = core.get_current_vfs()
    virtual_dir_path = os.path.abspath(virtual_dir)
    while virtual_dir_path.startswith(vfs.virtual_base):
        frozen = is_frozen(virtual_dir_path)
        if frozen:
            return virtual_dir_path
        virtual_dir_path = os.path.dirname(virtual_dir_path)
    return None


# CLI TARGET: Freeze a dir
def freeze_dir(virtual_dir):
    if is_frozen(virtual_dir):
        logger.info('Directory "%s" is already frozen', virtual_dir)
        return
    frozen_parent = get_frozen_parent(virtual_dir)
    if frozen_parent is not None:
        logger.info('Parent directory "%s" is already frozen', frozen_parent)
        return
    core.set_virtual_path_prop(config.FREEZE_PROP, config.FREEZE_VAL_TRUE, virtual_dir)
    logger.info('Directory "%s" has been frozen', virtual_dir)


# CLI TARGET: Unfreeze a dir
def unfreeze_dir(virtual_dir):
    frozen_parent = get_frozen_parent(virtual_dir)
    if frozen_parent is None:
        logger.info('Directory "%s" is not frozen', virtual_dir)
        return
    if not is_frozen(virtual_dir):
        logger.info('Parent directory "%s" is frozen', frozen_parent)
        return
    core.set_virtual_path_prop(config.FREEZE_PROP, config.FREEZE_VAL_FALSE, virtual_dir)
    logger.info('Directory "%s" has been unfrozen', virtual_dir)


# CLI TARGET: List all frozen dirs
def list_frozen_dirs(path):
    frozen_dirs = []
    for root, dirs, files in core.vfs_walk(path):
        if is_frozen(root):
            frozen_dirs.append(root)
            dirs[:] = []
    if len(frozen_dirs) == 0:
        logger.info('No frozen directories were found')
    else:
        logger.info('Following %d frozen directories were found:', len(frozen_dirs))
        for i, dir in enumerate(frozen_dirs):
            logger.info('%d. "%s"', i + 1, dir)
