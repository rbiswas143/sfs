"""CLI for collection related operations and queries"""

import os

import sfs.core as core
import sfs.events as events
import sfs.exceptions as exceptions
import sfs.file_system as fs
import sfs.log_utils as log
import sfs.ops.helper as ops_helper

messages = {
    'ADD_COL': {
        'HELP': 'Add a directory (aka collection) to the current SFS',
        'HELP_OPT': {
            'PATH': 'Path of the collection to be added to the SFS',
            'NAME': 'Collection name. Defaults to root of the collection'
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
            'INVALID_PATH': 'Not a directory',
            'NESTED_SFS': 'Given directory is inside another SFS',
            'NESTED_COL': 'Given directory is inside another collection',
            'NAME_EXISTS': 'A collection already exists with the given name'
        },
        'OUTPUT': 'Number of links added: '
    },
    'IS_COL': {
        'HELP': 'Check whether a path is inside an collection',
        'HELP_OPT': {
            'PATH': 'Path to or in a collection'
        },
        'OUTPUT': {
            'YES': 'Yes. Collection Root: ',
            'NO': 'No'
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
        }
    },
    'LIST_COLS': {
        'HELP': 'List all collections in the current SFS',
        'OUTPUT': {
            'COUNT': 'No of collections available: ',
            'COL_NAME': 'Collection: ',
            'COL_ROOT': 'Base: ',
            'NOT_AVAILABLE': 'No collections available'
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
        }
    },
    'SYNC_COL': {
        'HELP': 'Synchronize latest changes in a collection with the current SFS',
        'HELP_OPT': {
            'NAME': 'Collection name'
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
            'NOT_A_COL_NAME': 'Collection not available with the specified name'
        },
        'OUTPUT': {
            'ADDED': 'Number of links added: ',
            'UPDATED': 'Number of links updated: ',
            'DELETED': 'Number of links deleted: ',
        }
    },
    'DEL_COL': {
        'HELP': 'Delete a collection and all associated files from the current SFS',
        'HELP_OPT': {
            'NAME': 'Collection name'
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
            'NOT_A_COL_NAME': 'Collection not available with the specified name'
        },
        'OUTPUT': 'Number of links deleted: '
    },
    'DEL_ORPHANS': {
        'HELP': 'Delete any orphaned links in the current SFS. An orphaned link ' +
                'is one that is not part of any registered collection',
        'HELP_OPT': {
            'PATH': ''
        },
        'ERROR': {
            'NOT_IN_SFS': 'Path is not in an SFS',
        },
        'OUTPUT': 'Number of links deleted: '
    },
}

commands = {
    'ADD_COL': 'add-col',
    'IS_COL': 'is-col',
    'LIST_COLS': 'list-cols',
    'SYNC_COL': 'sync-col',
    'DEL_COL': 'del-col',
    'DEL_ORPHANS': 'del-orphans',
}


@events.subscriber(events.events['CLI_REGISTRY'])
def _collection_ops_cli(parser, parents=()):
    add_col = parser.add_parser(
        commands['ADD_COL'],
        parents=parents,
        help=messages['ADD_COL']['HELP']
    )
    add_col.add_argument('path', help=messages['ADD_COL']['HELP_OPT']['PATH'])
    add_col.add_argument('-n', '--name', help=messages['ADD_COL']['HELP_OPT']['NAME'])

    is_col = parser.add_parser(
        commands['IS_COL'],
        parents=parents,
        help=messages['IS_COL']['HELP']
    )
    is_col.add_argument(
        'path',
        help=messages['IS_COL']['HELP_OPT']['PATH']
    )

    list_cols = parser.add_parser(
        commands['LIST_COLS'],
        parents=parents,
        help=messages['LIST_COLS']['HELP']
    )

    sync_col = parser.add_parser(
        commands['SYNC_COL'],
        parents=parents,
        help=messages['SYNC_COL']['HELP']
    )
    sync_col.add_argument(
        'name',
        help=messages['SYNC_COL']['HELP_OPT']['NAME']
    )

    del_col = parser.add_parser(
        commands['DEL_COL'],
        parents=parents,
        help=messages['DEL_COL']['HELP']
    )
    del_col.add_argument(
        'name',
        help=messages['DEL_COL']['HELP_OPT']['NAME']
    )

    del_orphans = parser.add_parser(
        commands['DEL_ORPHANS'],
        parents=parents,
        help=messages['DEL_ORPHANS']['HELP']
    )


@ops_helper.cli_command(commands['ADD_COL'])
def _add_collection(args):
    """
    Add a collection (directory) named args.name at located at args.path to an SFS creating symlinks to each file in
    the directory and saving the meta-data
    """
    cwd = os.getcwd()
    log.logger.debug('Current working directory: "%s"', cwd)
    sfs = core.SFS.get_by_path(cwd)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['ADD_COL']['ERROR']['NOT_IN_SFS'])
    path = fs.expand_path(args.path)
    log.logger.debug('SFS Root: "%s"', sfs.root)
    log.logger.debug('Collection Path: "%s"', path)
    if not os.path.isdir(path):
        raise exceptions.CLIValidationException(messages['ADD_COL']['ERROR']['INVALID_PATH'])
    if core.SFS.get_by_path(path):
        raise exceptions.CLIValidationException(messages['ADD_COL']['ERROR']['NESTED_SFS'])
    if sfs.get_collection_by_path(path):
        raise exceptions.CLIValidationException(messages['ADD_COL']['ERROR']['NESTED_COL'])
    name = os.path.basename(path) if args.name is None else args.name
    log.logger.debug('Collection Name: "%s"', name)
    if sfs.get_collection_by_name(name):
        raise exceptions.CLIValidationException(messages['ADD_COL']['ERROR']['NAME_EXISTS'])
    sfs_updates = sfs.add_collection(name, path)
    log.logger.debug('SFS Updates: "%s"', sfs_updates)
    log.cli_output("{} {}".format(messages['ADD_COL']['OUTPUT'], sfs_updates.added))


@ops_helper.cli_command(commands['IS_COL'])
def _is_col(args):
    """Check whether args.path lies in any collection added to the current SFS"""
    cwd = os.getcwd()
    log.logger.debug('Current working directory: "%s"', cwd)
    sfs = core.SFS.get_by_path(cwd)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['IS_COL']['ERROR']['NOT_IN_SFS'])
    path = fs.expand_path(args.path)
    log.logger.debug('Path: "%s"', path)
    col = sfs.get_collection_by_path(path)
    log.cli_output("{} {}".format(messages['IS_COL']['OUTPUT']['YES'], col.base)
                   if col is not None else messages['IS_COL']['OUTPUT']['NO'])


@ops_helper.cli_command(commands['LIST_COLS'])
def _list_cols(args):
    """List information related to all added collections for the current SFS"""
    cwd = os.getcwd()
    log.logger.debug('Current working directory: "%s"', cwd)
    sfs = core.SFS.get_by_path(cwd)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['LIST_COLS']['ERROR']['NOT_IN_SFS'])
    log.logger.debug('SFS Root: "%s"', sfs.root)
    cols = sfs.get_all_collections()
    if len(cols) <= 0:
        log.cli_output(messages['LIST_COLS']['OUTPUT']['NOT_AVAILABLE'])
    else:
        log.cli_output("{}{}".format(messages['LIST_COLS']['OUTPUT']['COUNT'], len(cols)))
        for col in sorted(cols.values(), key=lambda c: c.name):
            log.cli_output('{}"{}"\t{}"{}"'.format(
                messages['LIST_COLS']['OUTPUT']['COL_NAME'], col.name,
                messages['LIST_COLS']['OUTPUT']['COL_ROOT'], col.base
            ))


@ops_helper.cli_command(commands['SYNC_COL'])
def _sync_col(args):
    """
    Update the saved collection meta-data for collection named args.name in the current SFS, adding links for new files
    and deleting links for deleted files
    Note:
        If a file is moved in a collection, it is interpreted as being deleted from the original path and then adding to
        the new path. So, existing links will also be deleted and added accordingly. If such a link has been relocated
        inside the SFS, it will be brought back to its original path after a synchronization
    """
    cwd = os.getcwd()
    log.logger.debug('Current working directory: "%s"', cwd)
    sfs = core.SFS.get_by_path(cwd)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['SYNC_COL']['ERROR']['NOT_IN_SFS'])
    log.logger.debug('SFS Root: "%s"', sfs.root)
    col = sfs.get_collection_by_name(args.name)
    if col is None:
        raise exceptions.CLIValidationException(messages['SYNC_COL']['ERROR']['NOT_A_COL_NAME'])
    log.logger.debug('Collection Name: "%s"', col.name)
    updates = col.update()
    log.logger.debug('Updates: "%s"', updates)
    dels = sfs.del_orphans(col_root=col.base)
    log.logger.debug('Deletions: "%s"', dels)
    log.cli_output('{}{}'.format(messages['SYNC_COL']['OUTPUT']['ADDED'], updates.added))
    log.cli_output('{}{}'.format(messages['SYNC_COL']['OUTPUT']['UPDATED'], updates.updated))
    log.cli_output('{}{}'.format(messages['SYNC_COL']['OUTPUT']['DELETED'], dels.deleted))


@ops_helper.cli_command(commands['DEL_COL'])
def _del_col(args):
    """Delete a collection named args.name from the current SFS"""
    cwd = os.getcwd()
    log.logger.debug('Current working directory: "%s"', cwd)
    sfs = core.SFS.get_by_path(cwd)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['DEL_COL']['ERROR']['NOT_IN_SFS'])
    log.logger.debug('SFS Root: "%s"', sfs.root)
    col = sfs.get_collection_by_name(args.name)
    if col is None:
        raise exceptions.CLIValidationException(messages['DEL_COL']['ERROR']['NOT_A_COL_NAME'])
    log.logger.debug('Collection Name: "%s"', col.name)
    sfs.del_collection(args.name)
    dels = sfs.del_orphans(col_root=col.base)
    log.logger.debug('Deletions: "%s"', dels)
    log.cli_output('{}{}'.format(messages['DEL_COL']['OUTPUT'], dels.deleted))


@ops_helper.cli_command(commands['DEL_ORPHANS'])
def _del_orphans(args):
    """
    Delete all orphan links in the current SFS
    An orphan link is a symlink that is not managed by the SFS, ie, it is not belong to any collection added to the SFS
    """
    cwd = os.getcwd()
    log.logger.debug('Current working directory: "%s"', cwd)
    sfs = core.SFS.get_by_path(cwd)
    if sfs is None:
        raise exceptions.CLIValidationException(messages['DEL_ORPHANS']['ERROR']['NOT_IN_SFS'])
    log.logger.debug('SFS Root: "%s"', sfs.root)
    dels = sfs.del_orphans()
    log.logger.debug('Deletions: "%s"', dels)
    log.cli_output('{}{}'.format(messages['DEL_ORPHANS']['OUTPUT'], dels.deleted))
