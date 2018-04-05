# Operations at the Disc level

import core
from log_utils import logger


# CLI TARGET: List details of all added discs
def list_discs():
    vfs = core.get_current_vfs()
    all_discs = core.get_all_discs()
    if len(all_discs) == 0:
        logger.info('No discs have been added to VFS %s', vfs.name)
    else:
        logger.info('Following discs have been added:')
        for disc in all_discs:
            capacity = '' if disc.capacity is None else ' Capacity: %s' % core.get_readable_size(disc.capacity)
            logger.info('%s (%s)%s' , disc.name, disc.disc_base, capacity)


# CLI TARGET: Add a new disc
def add_disc(disc_name, disc_path, disc_capacity):
    vfs = core.get_current_vfs()
    core.add_disc(disc_name, disc_path, disc_capacity)
    logger.info('Disc %s at base path %s has successfully been added to VFS %s' , disc_name, disc_path, vfs.name)


# CLI TARGET: Delete a disc
def del_disc(disc_name):
    vfs = core.get_current_vfs()
    core.del_disc(disc_name)
    logger.info('Disc %s has been deleted from the VFS %s' , disc_name, vfs.name)
