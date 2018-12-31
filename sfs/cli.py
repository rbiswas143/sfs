"""
CLI module for SFS
This module is responsible for bootstrapping the application and executing the CLI
"""

import argparse
import contextlib
import sys

import sfs.events as events
import sfs.exceptions as exceptions
import sfs.log_utils as log
import sfs.ops as ops

# Messages

error_messages = {
    'VALIDATION': 'Invalid Command:',
    'INTERNAL': 'Internal Error: ',
    'UNKNOWN': 'Unknown error occurred'
}

# Primary parser

parser = argparse.ArgumentParser(
    prog='sfs',
    description='Symbolic File System for backing up, organizing your data and more'
)
parser.add_argument(
    '-v', '--verbose',
    action='store_true',
    help='Get a verbose output'
)

# Command parser

command_subparsers = parser.add_subparsers(
    dest='command',
    title='SFS Commands',
    description='List of all available SFS commands'
)
command_subparsers.required = True


@contextlib.contextmanager
def cli_manager(command=None, exit_on_error=True, raise_error=False):
    """
    Provides a context for processing parsed CLI commands while catching and handling exceptions
    :param command: Command list to be forwarded to argparse. If None, system arguments are used
    :param exit_on_error: If True, process exits on error
    :param raise_error: If True, caught exception is raised
    """
    error = False
    args = parser.parse_args() if command is None else parser.parse_args(command)
    try:
        # Do anything with the processed arguments
        yield args
    except exceptions.CLIValidationException as exc:
        log.cli_output("{} {}".format(error_messages['VALIDATION'], str(exc)))
        error = True
    except exceptions.SFSException as exc:
        log.cli_output('{} {}'.format(error_messages['INTERNAL'], str(exc)))
        log.logger.exception("Internal Error")
        error = True
    except Exception:
        log.cli_output(error_messages['UNKNOWN'])
        log.logger.exception("Unknown Error")
        error = True
    finally:
        if error and raise_error:
            raise
        if exit_on_error:
            sys.exit(1 if error else 0)


def exec_cli():
    """Executes the CLI when this module is run as a script"""

    # Import all CLI modules, which also makes them auto-subscribe to CLI events
    ops.import_ops()

    # Extend CLI parser with sub-command parsers
    events.invoke_subscribers(events.events['CLI_REGISTRY'], command_subparsers, parents=[])

    with cli_manager() as args:
        # Parse and process arguments
        if args.verbose:
            log.cli_handler.setLevel('DEBUG')

        # Execute command
        events.invoke_subscribers(events.command_key(args.command), args)
