# File and directory stats querying related operations

import os

import core
from log_utils import logger


# CLI TARGET: Show the stats for the specified directory
def query_dir_meta(dir_path):
    dir_size = core.get_virtual_dir_size(dir_path)
    logger.info('Directory size: %s', core.get_readable_size(dir_size))


# CLI TARGET: Show the stats for the specified file
def query_file_meta(file_path):
    file_stat = core.get_file_stats_for_symlink(file_path)
    if file_stat is None:
        raise core.VfsException('Meta data missing for file %s' % file_path)
    logger.info('Actual File Path: %s', file_stat.actual_path)
    actual_available = os.path.isfile(file_stat.actual_path) or os.path.islink(file_stat.actual_path)
    logger.info('Symlink is active: %s', actual_available)
    disc = core.get_disc_by_path(file_stat.actual_path)
    logger.info('Disc: %s', disc.name if disc is not None else 'Unknown')
    logger.info('Actual File Size: %s', core.get_readable_size(file_stat.size))