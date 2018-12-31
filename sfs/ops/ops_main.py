"""CLI for initializing SFS and SFS related queries"""

import os

import sfs.core as core
import sfs.events as events
import sfs.exceptions as exceptions
import sfs.file_system as fs
import sfs.log_utils as log
import sfs.ops.helper as ops_helper


messages = {
    'INIT': {
        'HELP': 'Initialize a new SFS in the current directory. The current directory must be empty',
        'ERROR': {
            'NON_EMPTY_DIR': 'SFS can only be initialized in an empty directory',
            'NESTED_SFS': 'Current directory is inside another SFS',
        }
    },
    'IS_SFS': {
        'HELP': 'Check whether a path is inside an SFS',
        'HELP_OPT': {
            'PATH': 'Path to check (defaults to current working directory)'
        },
        'OUTPUT': {
            'YES': 'Yes. SFS Root: ',
            'NO': 'No'
        }
    }
}

commands = {
    'SFS_INIT': 'init',
    'IS_SFS': 'is-sfs'
}


@events.subscriber(events.events['CLI_REGISTRY'])
def _sfs_ops_cli(parser, parents=()):
    parser.add_parser(
        commands['SFS_INIT'],
        parents=parents,
        help=messages['INIT']['HELP']
    )

    is_sfs = parser.add_parser(
        commands['IS_SFS'],
        parents=parents,
        help=messages['IS_SFS']['HELP']
    )
    is_sfs.add_argument(
        'path', nargs='?',
        help=messages['IS_SFS']['HELP_OPT']['PATH']
    )


@ops_helper.cli_command(commands['SFS_INIT'])
def _init_sfs(args):
    """
    Initialize an SFS in the current working directory
    Validations:
        Current directory must be empty
        Current directory must not be inside another SFS
    """
    path = os.getcwd()
    log.logger.debug('Path "%s"', path)
    if not fs.is_empty_dir(path):
        raise exceptions.CLIValidationException(messages['INIT']['ERROR']['NON_EMPTY_DIR'])
    if core.SFS.get_by_path(path):
        raise exceptions.CLIValidationException(messages['INIT']['ERROR']['NESTED_SFS'])
    core.SFS.init_sfs(path)


@ops_helper.cli_command(commands['IS_SFS'])
def _is_sfs(args):
    """Check whether 'args.path' (or by default current working directory) lies inside an SFS"""
    path = fs.expand_path(args.path) if args.path is not None else os.getcwd()
    log.logger.debug('Path "%s"', path)
    sfs = core.SFS.get_by_path(path)
    log.cli_output("{}{}".format(messages['IS_SFS']['OUTPUT']['YES'], sfs.root)
                   if sfs is not None else messages['IS_SFS']['OUTPUT']['NO'])
