# File and directory props related operations

import os

import core
from log_utils import logger


# CLI TARGET: Set a prop
def set_prop(virtual_file, prop, value):
    logger.debug('Setting Prop: %s, Value %s for virtual file "%s"', prop, value, virtual_file)
    core.set_virtual_path_prop(prop, value, virtual_file)
    logger.info('Property has been set')


# CLI TARGET: Delete a prop
def del_prop(virtual_file, prop):
    logger.debug('Deleting Prop: %s of virtual file "%s"', prop, virtual_file)
    core.set_virtual_path_prop(prop, None, virtual_file)
    logger.info('Property has been deleted')


# CLI TARGET: List all props
def list_props(virtual_file):
    props = core.get_virtual_path_props(virtual_file)
    props = {k: v for k, v in props.items() if v is not None}
    if len(props) == 0:
        logger.info('No properties were found')
    else:
        logger.info('Following properties were found:')
        for i, prop in enumerate(props):
            logger.info('%d. %s: %s', i + 1, prop, props[prop])


# CLI TARGET: List unique properties under a directory
def list_unique_props(virtual_dir):
    unique_props = set()
    for root, dirs, files in core.vfs_walk(virtual_dir):
        for elem in [root] + [os.path.join(root, file_) for file_ in files]:
            props = core.get_virtual_path_props(elem)
            for prop in props:
                unique_props.add(prop)
    unique_props = sorted(list(unique_props))
    if len(unique_props) == 0:
        logger.info('No properties were found')
    else:
        logger.info('Following properties were found:')
        for i, prop in enumerate(unique_props):
            logger.info('%d. %s', i+1, prop)