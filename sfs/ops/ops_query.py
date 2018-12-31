"""CLI for querying collection and directory related meta-data"""

import os
import time

import sfs.core as core
import sfs.events as events
import sfs.exceptions as exceptions
import sfs.file_system as fs
import sfs.helper as helper
import sfs.log_utils as log
import sfs.ops.helper as ops_helper

messages = {
    'QUERY': {
        'HELP': 'Get information about a link or directory in an SFS',
        'HELP_OPT': {
            'PATH': 'Path of a link or directory (Defaults to current working directory)'
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
            'COLLECTION_NOT_FOUND': 'No collection available for the specified link',
            'STATS_NOT_FOUND': 'Information about this link is not available',
            'NOT_LINK_OR_DIR': 'Path is neither a link nor a directory',
        },
        'OUTPUT': {
            'LINK': {
                'COL_NAME': 'Collection: ',
                'COL_PATH': 'Path: ',
                'CTIME': 'Last changed: ',
                'SIZE': 'File Size: ',
            },
            'DIR': {
                'SIZE': 'Directory Size: ',
                'CTIME': 'Last content changed: ',
                'ACTIVE_LINKS': 'No of active links: ',
                'FOREIGN_LINKS': 'No of foreign links: ',
                'ORPHAN_LINKS': 'No of orphan links: ',
                'FILES': 'No of files: ',
                'SUB_DIRECTORIES': 'No of sub directories: ',
            }
        }
    }
}

commands = {
    'QUERY': 'query'
}


@events.subscriber(events.events['CLI_REGISTRY'])
def _query_ops_cli(parser, parents=()):
    query = parser.add_parser(
        commands['QUERY'],
        parents=parents,
        help=messages['QUERY']['HELP']
    )
    query.add_argument('path', nargs='?', help=messages['QUERY']['HELP_OPT']['PATH'])


@ops_helper.cli_command(commands['QUERY'])
def _query(args):
    """
    Get meta-data of the collection file corresponding to to a link located at args.path or the meta-data of a directory
    by aggregating the meta-data corresponding to all links in the directory
    Path defaults to the current working directory if not specified
    """
    path = fs.expand_path(args.path) if args.path is not None else os.getcwd()
    log.logger.debug('Path: "%s"', path)
    sfs = core.SFS.get_by_path(path)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['QUERY']['ERROR']['NOT_IN_SFS'])
    log.logger.debug('SFS Root: "%s"', sfs.root)
    if os.path.islink(path):
        log.logger.debug('Getting Link Stats')
        col_path = os.readlink(path)
        col = sfs.get_collection_by_path(col_path)
        if col is None:
            raise exceptions.CLIValidationException(messages['QUERY']['ERROR']['COLLECTION_NOT_FOUND'])
        log.logger.debug('Col Name: "%s"', col.name)
        stats = col.get_stats(col_path)
        if stats is None:
            raise exceptions.CLIValidationException(messages['QUERY']['ERROR']['STATS_NOT_FOUND'])
        log.logger.debug('Link Stats: "%s"', stats)
        file_size = helper.get_readable_size(stats.size)
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['LINK']['COL_NAME'], col.name))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['LINK']['COL_PATH'], col_path))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['LINK']['CTIME'], time.ctime(stats.ctime)))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['LINK']['SIZE'], file_size))
    elif os.path.isdir(path):
        log.logger.debug('Getting Directory Stats')
        dir_stats = compute_directory_stats(sfs, path)
        log.logger.debug('Directory Stats: "%s"', dir_stats)
        dir_size = helper.get_readable_size(dir_stats.size)
        dir_ctime = time.ctime(dir_stats.ctime) if dir_stats.ctime > 0 else 'na'
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['DIR']['SIZE'], dir_size))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['DIR']['CTIME'], dir_ctime))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['DIR']['ACTIVE_LINKS'], dir_stats.active_links))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['DIR']['FOREIGN_LINKS'], dir_stats.foreign_links))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['DIR']['ORPHAN_LINKS'], dir_stats.orphan_links))
        log.cli_output("{}{}".format(messages['QUERY']['OUTPUT']['DIR']['FILES'], dir_stats.files))
        log.cli_output("{}{}".format(
            messages['QUERY']['OUTPUT']['DIR']['SUB_DIRECTORIES'],
            dir_stats.sub_directories
        ))
    else:
        raise exceptions.CLIValidationException(messages['QUERY']['ERROR']['NOT_LINK_OR_DIR'])


class DirectoryStats:

    def __init__(self, stats=None):
        self.size = 0
        self.ctime = 0
        self.active_links = 0
        self.foreign_links = 0
        self.orphan_links = 0
        self.files = 0
        self.sub_directories = 0
        if stats:
            self.__dict__.update(stats)

    def __repr__(self):
        return "{}(stats={})".format(DirectoryStats.__name__, self.__dict__)


def compute_directory_stats(sfs, sfs_dir):
    """
    Aggregate the meta-data of all links inside an SFS Directory
    :param sfs: SFS instnce being operated on
    :param sfs_dir: A directory inside the SFS
    :return: An instance of DirectoryStats
    """
    dir_stats = DirectoryStats()
    for root, files, dirs, links in core.SFS.walk(fs.walk_bfs, sfs_dir):
        dir_stats.files += len(files)
        dir_stats.sub_directories += len(dirs)
        for lnk in links:
            col_path = os.readlink(lnk.path)
            col = sfs.get_collection_by_path(col_path)
            if col is None:
                dir_stats.foreign_links += 1
                continue
            stats = col.get_stats(col_path)
            if stats is None:
                dir_stats.orphan_links += 1
                continue
            dir_stats.active_links += 1
            dir_stats.size += stats.size
            dir_stats.ctime = max(dir_stats.ctime, stats.ctime)
    return dir_stats
