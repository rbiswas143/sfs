# Command line mappings for VFS

import argparse
import os
import sys

import backup_ops
import config
import core
import collection_ops
import dedup_ops
import disc_ops
import filter_ops
import freeze_ops
from log_utils import logger, cli_handler
import merge_ops
import props_ops
import query_ops
import save_map_ops
import save_ops
import vfs_ops

# Create VFS Home
logger.debug('Trying to create VFS home at %s', core.get_vfs_home())
try:
    core.setup_vfs_home()
    logger.debug('VFS Home has been setup')
except core.VfsException as ex:
    if not core.validate_vfs_home():
        logger.error('Failed to setup VFS Home at %s. The current setup is invalid. ' +
                     'Please reset the VFS home directory before continuing', core.get_vfs_home())
        logger.debug('', exc_info=True)
    else:
        logger.debug('VFS home exists and is valid')


# Wrap command execution to do common tasks around them
# command - name of command
# cargs - parsed arguments
# target - function to call
# targs - arguments for the function to call
def exec_command(cargs, target, *targs):
    try:
        logger.debug("Executing command %s with arguments %s", cargs.command, cargs)
        target(*targs)
    except Exception as exc:
        logger.error("Failed to execute command %s. Reason for failure: %s", cargs.command, str(exc))
        logger.debug("", exc_info=True)
        core.do_pending_meta_writes()
        sys.exit(1)
    else:
        core.do_pending_meta_writes()
        logger.debug("Command %s executed successfully", cargs.command)
        sys.exit(0)


# Log a validation failure message and exit
def validation_error(cargs, err_msg):
    logger.error('Validation error occurred while executing command %s: %s', cargs.command, err_msg)
    sys.exit(1)


# Find and set VFS for a path
def set_vfs_by_path(cargs, path):
    vfs = core.get_vfs_by_path(path)
    if not vfs:
        validation_error(cargs, 'VFS not available for path %s' % path)
    core.set_current_vfs(vfs)


# VFS primary parser

parser = argparse.ArgumentParser(prog='vfs',
                                 description='Virtual File System for backing up and organizing your data')

# Subparsers

command_subparsers = parser.add_subparsers(dest='command', title='VFS Commands',
                                           description='List of all available VFS commands')

# Parent parsers

verbosity_parser = argparse.ArgumentParser(add_help=False)
verbosity_parser.add_argument('-v', '--verbose', action='store_true', help='Get a verbose output')

vfs_common_parser = argparse.ArgumentParser(add_help=False)
vfs_common_parser.add_argument('--vfs',
                               help='VFS Name to check for collections. VFS corresponding to the current directory is used by default')

# VFS ops subparsers

vfs_list_parser = command_subparsers.add_parser('list-vfs', parents=[verbosity_parser],
                                                help='List all available VFS')

vfs_new_parser = command_subparsers.add_parser('new-vfs', parents=[verbosity_parser],
                                               help='Create a new VFS in the current or specified directory')
vfs_new_parser.add_argument('name', help='VFS name')
vfs_new_parser.add_argument('-p', '--path',
                            help='Path to a directory in which the VFS will be created. Defaults to current directory.')

vfs_del_parser = command_subparsers.add_parser('del-vfs', parents=[verbosity_parser],
                                               help='Delete a VFS by name')
vfs_del_parser.add_argument('name', help='VFS name')

vfs_show_parser = command_subparsers.add_parser('show-vfs', parents=[verbosity_parser],
                                                help='Shows the details of the current or specified VFS')
vfs_show_parser.add_argument('-n', '--name', help='VFS name')
vfs_show_parser.add_argument('-p', '--path', help='Path to a directory within a VFS. Defaults to current directory')

# Collection ops subparsers
# Collection ops subparsers

collection_list_parser = command_subparsers.add_parser('list-collections',
                                                       parents=[verbosity_parser, vfs_common_parser],
                                                       help='List all added collections in the current or specified VFS')

collection_add_parser = command_subparsers.add_parser('add-collection', parents=[verbosity_parser, vfs_common_parser],
                                                      help='Create a new VFS in the current or specified directory')
collection_add_parser.add_argument('-n', '--name', help='Collection name. Defaults to root of the collection')
collection_add_parser.add_argument('path', help='Path of the collection to be added to the VFS')

collection_add_parser = command_subparsers.add_parser('sync-collection', parents=[verbosity_parser, vfs_common_parser],
                                                      help='Sync VFS meta data and Virtual directories with an actual collection')
collection_add_parser.add_argument('name', help='Collection name')

collection_show_parser = command_subparsers.add_parser('show-collection', parents=[verbosity_parser, vfs_common_parser],
                                                       help='Shows the details of the current or spec1ified Collection')
collection_show_parser.add_argument('-n', '--name', help='Collection name')
collection_show_parser.add_argument('-p', '--path',
                                    help='Path to a directory within a Collection. Defaults to current directory')

# Disc ops parsers

discs_list_parser = command_subparsers.add_parser('list-discs', parents=[verbosity_parser, vfs_common_parser],
                                                  help='List all added discs in the current or specified VFS')

disc_add_parser = command_subparsers.add_parser('add-disc', parents=[verbosity_parser, vfs_common_parser],
                                                help='Create a new disc in the current or specified VFS')
disc_add_parser.add_argument('-n', '--name', help='Disc name. Defaults to root of the disc')
disc_add_parser.add_argument('-c', '--capacity', type=int,
                             help='Max capacity of disc. No capacity restriction by default.')
disc_add_parser.add_argument('path', help='Base path of the disc to be added to the VFS')

disc_del_parser = command_subparsers.add_parser('del-disc', parents=[verbosity_parser, vfs_common_parser],
                                                help='Delete a disc')
disc_del_parser.add_argument('name', help='Disc name')

# Save map ops parsers

save_maps_list_parser = command_subparsers.add_parser('list-save-maps', parents=[verbosity_parser, vfs_common_parser],
                                                      help='List all save mappings added to the current or specified VFS')

save_maps_add_parser = command_subparsers.add_parser('add-save-map', parents=[verbosity_parser, vfs_common_parser],
                                                     help='Add a new save mapping to the current or specified VFS')
save_maps_add_parser.add_argument('virtual_path', help='Path to a directory in the specified or current VFS')
save_maps_add_parser.add_argument('actual_path', help='Path to a directory in an existing collection')

save_maps_del_parser = command_subparsers.add_parser('del-save-maps', parents=[verbosity_parser, vfs_common_parser],
                                                     help='Delete all save mappings from the current or specified VFS')

# Query ops subparsers

query_file_meta_parser = command_subparsers.add_parser('query-meta', parents=[verbosity_parser, vfs_common_parser],
                                                       help='Query the meta data of a symlink in a VFS')
query_file_meta_parser.add_argument('path', nargs='?', help='Path to a symlink within a VFS')

# Backup ops subparsers

backup_parser = command_subparsers.add_parser('backup', parents=[verbosity_parser, vfs_common_parser],
                                              help='Backup the current or specified VFS')
backup_parser.add_argument('-c', '--comment', help='Comment regarding the backup')

backup_del_parser = command_subparsers.add_parser('del-backup', parents=[verbosity_parser],
                                                  help='Delete the specified backup')
backup_del_parser.add_argument('name', help='Name of the backup to delete')

backup_list_parser = command_subparsers.add_parser('list-backups', parents=[verbosity_parser, vfs_common_parser],
                                                   help='List backups for the specified VFS or by default all VFS')

backup_restore_parser = command_subparsers.add_parser('restore', parents=[verbosity_parser],
                                                      help='Restore a specified VFS backup')
backup_restore_parser.add_argument('name', help='Name of the backup to restore')

# Freeze ops subparsers

freeze_parser = command_subparsers.add_parser('freeze', parents=[verbosity_parser],
                                              help='Freeze a directory. It will be excluded from various operations like deuplication and merge')
freeze_parser.add_argument('path', nargs='?',
                           help='Path to virtual directory to freeze. Defaults to current directory')

unfreeze_parser = command_subparsers.add_parser('unfreeze', parents=[verbosity_parser], help='Unfreeze a directory')
unfreeze_parser.add_argument('path', nargs='?',
                             help='Path to virtual directory to unfreeze. Defaults to current directory')

freeze_list_parser = command_subparsers.add_parser('list-frozen', parents=[verbosity_parser],
                                                   help='List all frozen directories under a specified virtual directory')
freeze_list_parser.add_argument('path', nargs='?',
                                help='Path to virtual directory to check for frozen sub directories. Defaults to current directory')

# Dedup ops subparsers

dedup_json_parser = command_subparsers.add_parser('dedup-json', parents=[verbosity_parser, vfs_common_parser],
                                                  help='Find duplicates and save them as a JSON file in the current or specified directory')
dedup_json_parser.add_argument('path', nargs='?',
                               help='Path to virtual directory to find duplicates in. Defaults to current directory')
dedup_json_parser.add_argument('-o', '--override', action='store_true',
                               help='Indicate whether to override the existing JSON file')
dedup_json_parser.add_argument('-d', '--del-duplicates', action='store_true',
                               help='Indicate whether to mark duplicate files for deletion in the JSON')

dedup_parser = command_subparsers.add_parser('dedup', parents=[verbosity_parser, vfs_common_parser],
                                             help='Delete duplicates using the JSON file generated using the command "dedup-json"')
dedup_parser.add_argument('path', nargs='?',
                          help='Path to virtual directory to delete duplicates from which also contains the JSON file. Defaults to current directory')
dedup_parser.add_argument('-j', '--del-json', action='store_true',
                          help='Indicate whether to delete the JSON file after the deduplication process. Default False.')

# Merge ops subparsers

merge_parser = command_subparsers.add_parser('merge', parents=[verbosity_parser, vfs_common_parser],
                                             help='Merge source directory into destination directory. ' +
                                                  'Conflicts are saved in a JSON file in the destination directory')
merge_parser.add_argument('dest', nargs='?',
                          help='Destination directory to merge. Defaults to current directory')
merge_parser.add_argument('source', nargs='?',
                          help='Source directory to merge. ' +
                               'If skipped, the source directory will be picked up from the conflicts JSON')
merge_parser.add_argument('-g', '--gen-json', action='store_true',
                          help='Indicate whether to override the existing JSON file. Default False')
merge_parser.add_argument('-s', '--del-source', action='store_true',
                          help='Indicate whether to delete the orignal source directory after the merge. Default False.')
merge_parser.add_argument('-j', '--del-json', action='store_true',
                          help='Indicate whether to delete the merge conflicts JSON file after the merge. Default False.')
merge_parser.add_argument('-d', '--mark-del-source', action='store_true',
                          help='Indicate whether to mark conflicting source files (with same size) for deletion in the JSON')

# Filter ops subparsers

filter_mime_parser = command_subparsers.add_parser('filter-by-mime', parents=[verbosity_parser, vfs_common_parser],
                                                   help='Filter the contents of a VFS by the specified file MIME types')
filter_mime_parser.add_argument('-m', '--mime', dest='mimes', action='append', choices=filter_ops.get_all_mime_types(),
                                help='Add a MIME type to the filter')

filter_size_parser = command_subparsers.add_parser('filter-by-size', parents=[verbosity_parser, vfs_common_parser],
                                                   help='Filter the contents of a VFS by the specified size range in Bytes')
filter_size_parser.add_argument('size_start', type=int,
                                help='Show files greater than this size. Negative size implies no lower limit')
filter_size_parser.add_argument('size_end', type=int,
                                help='Show files smaller than this size. Negative size implies no upper limit')

filter_prop_parser = command_subparsers.add_parser('filter-by-prop', parents=[verbosity_parser, vfs_common_parser],
                                                   help='Filter the contents of a VFS by the specified property and value')
filter_prop_parser.add_argument('-p', '--prop', dest='props', action='append',
                                help='Name of a property followed optionally by a value (Separated by a Pipe(|))')

filter_list_parser = command_subparsers.add_parser('list-filters', parents=[verbosity_parser, vfs_common_parser],
                                                   help='Lists the applied filters')

filter_clear_parser = command_subparsers.add_parser('clear-filters', parents=[verbosity_parser, vfs_common_parser],
                                                    help='Clear all filters')

# Props ops subparsers

prop_set_parser = command_subparsers.add_parser('set-prop', parents=[verbosity_parser],
                                                help='Add or update a property and value to a virtual file or directory')
prop_set_parser.add_argument('path', help='Virtual path of file or directory. Defaults to the current directory')
prop_set_parser.add_argument('prop', help='Name of the property to set')
prop_set_parser.add_argument('--val', default=True, help='String value of the property. Default is True')

prop_del_parser = command_subparsers.add_parser('del-prop', parents=[verbosity_parser],
                                                help='Delete a property of a virtual file or directory')
prop_del_parser.add_argument('path', help='Virtual path of file or directory Defaults to the current directory')
prop_del_parser.add_argument('prop', help='Name of the property to delete')

prop_list_parser = command_subparsers.add_parser('list-props', parents=[verbosity_parser],
                                                 help='List the properties of a virtual file or directory')
prop_list_parser.add_argument('path', help='Virtual path of file or directory Defaults to the current directory')

prop_list_parser = command_subparsers.add_parser('unique-props', parents=[verbosity_parser],
                                                 help='Compute and list an exhaustive set of all properties in a directory tree')
prop_list_parser.add_argument('path', help='Virtual path of a directory. Defaults to the current directory')

# Save ops subparsers

save_parser = command_subparsers.add_parser('save', parents=[verbosity_parser, vfs_common_parser],
                                            help='Save a VFS using the disc info and save mappings or resume a pending save')
save_parser.add_argument('-m', '--mode', choices=['copy', 'move'], default='copy',
                         help='Specify the save mode. Defaults to "copy"')
save_parser.add_argument('-r', '--restart', action='store_true',
                         help='Indicate whether to restart the save process ignoring any previous progress.')
save_parser.add_argument('-d', '--del-save-file', action='store_true',
                         help='Indicate whether to delete the save file after the save is complete. Default False.')

# Parse the command and arguments
logger.debug('Parsing command line arguments')
args = parser.parse_args()

# Verbosity
if args.verbose:
    cli_handler.setLevel('DEBUG')

# Add VFS to env where required
if args.command in ['list-collections', 'add-collection', 'sync-collection', 'show-collection',
                    'list-discs', 'add-disc', 'del-disc',
                    'list-save-maps', 'add-save-map', 'del-save-maps',
                    'filter-by-mime', 'filter-by-size', 'filter-by-prop', 'list-filters', 'clear-filters',
                    'backup', 'save']:
    vfs_name = args.vfs
    if vfs_name is None:
        cur_path = os.getcwd()
        set_vfs_by_path(args, cur_path)
    else:
        vfs = core.get_vfs_by_name(vfs_name)
        if vfs is None:
            validation_error(args, 'VFS named %s is not available' % vfs_name)
        core.set_current_vfs(vfs)

# Parse and execute commands

# VFS ops
if args.command == 'list-vfs':
    exec_command(args, vfs_ops.list_vfs)
elif args.command == 'new-vfs':
    path = args.path if args.path is not None else os.getcwd()
    if not os.path.isdir(path):
        validation_error(args, 'Path %s is not a directory' % path)
    exec_command(args, vfs_ops.new_vfs, args.name, path)
elif args.command == 'del-vfs':
    exec_command(args, vfs_ops.del_vfs, args.name)
elif args.command == 'show-vfs':
    vfs_name = args.name
    path = args.path
    if vfs_name is not None and path is not None:
        validation_error(args, 'Only one of name or path must be specified')
    elif vfs_name is path is None:
        path = os.getcwd()
    if vfs_name is not None:
        exec_command(args, vfs_ops.show_vfs_by_name, vfs_name)
    else:
        exec_command(args, vfs_ops.show_vfs_by_path, path)

# Collection ops
if args.command == 'list-collections':
    exec_command(args, collection_ops.list_collections)
elif args.command == 'add-collection':
    col_path = args.path
    if not os.path.isdir(col_path):
        validation_error(args, 'Path %s does not exist or is not a directory' % col_path)
    col_name = args.name if args.name is not None else os.path.basename(os.path.abspath(col_path))
    exec_command(args, collection_ops.add_col, col_name, col_path)
elif args.command == 'sync-collection':
    exec_command(args, collection_ops.sync_col, args.name)
elif args.command == 'show-collection':
    col_name = args.name
    col_path = args.path
    if col_name is not None and col_path is not None:
        validation_error(args, 'Only one of name or path must be specified')
    elif col_name is col_path is None:
        col_path = os.getcwd()
    if col_name is not None:
        exec_command(args, collection_ops.show_collection_by_name, col_name)
    else:
        exec_command(args, collection_ops.show_collection_by_path, col_path)

# Disc ops
if args.command == 'list-discs':
    exec_command(args, disc_ops.list_discs)
elif args.command == 'add-disc':
    disc_base = args.path
    if not os.path.isdir(disc_base):
        validation_error(args, 'Path %s does not exist or is not a directory' % disc_base)
    disc_name = args.name if args.name is not None else os.path.basename(os.path.abspath(disc_base))
    exec_command(args, disc_ops.add_disc, disc_name, disc_base, args.capacity)
elif args.command == 'del-disc':
    exec_command(args, disc_ops.del_disc, args.name)

# Save map ops
if args.command == 'list-save-maps':
    exec_command(args, save_map_ops.list_save_maps)
elif args.command == 'add-save-map':
    virtual_dir = args.virtual_path
    if not os.path.isdir(virtual_dir):
        validation_error(args, 'Path %s does not exist or is not a directory' % virtual_dir)
    actual_dir = args.actual_path
    if not os.path.isdir(actual_dir):
        validation_error(args, 'Path %s does not exist or is not a directory' % actual_dir)
    exec_command(args, save_map_ops.add_save_map, virtual_dir, actual_dir)
elif args.command == 'del-save-maps':
    exec_command(args, save_map_ops.del_save_maps)

# Query ops
if args.command == 'query-meta':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    if os.path.isdir(path):
        exec_command(args, query_ops.query_dir_meta, path)
    elif os.path.islink(path):
        exec_command(args, query_ops.query_file_meta, path)
    else:
        validation_error(args, 'Path %s is neither directory nor symlink' % path)

# Backup ops
if args.command == 'backup':
    exec_command(args, backup_ops.create_backup, args.comment)
elif args.command == 'del-backup':
    exec_command(args, backup_ops.del_backup, args.name)
elif args.command == 'list-backups':
    exec_command(args, backup_ops.list_all_backups, args.vfs)
elif args.command == 'restore':
    exec_command(args, backup_ops.restore_backup, args.name)

# Freeze ops
if args.command == 'freeze':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, freeze_ops.freeze_dir, path)
elif args.command == 'unfreeze':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, freeze_ops.unfreeze_dir, path)
elif args.command == 'list-frozen':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, freeze_ops.list_frozen_dirs, path)

# Dedup ops
if args.command == 'dedup-json':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, dedup_ops.generate_dedup_json, path, args.override, args.del_duplicates)
elif args.command == 'dedup':
    path = args.path if args.path is not None else os.getcwd()
    exec_command(args, dedup_ops.dedup_using_json, path, args.del_json)

# Merge ops
if args.command == 'merge':
    dest = args.dest if args.dest is not None else os.getcwd()
    set_vfs_by_path(args, dest)
    exec_command(args, merge_ops.merge, dest, args.source, args.del_source, args.gen_json,
                 args.del_json, args.mark_del_source)

# Filter ops
if args.command == 'filter-by-mime':
    if args.mimes is None:
        validation_error(args, 'At least one MIME type must be specified')
    exec_command(args, filter_ops.apply_filter, config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype,
                 args.mimes)
elif args.command == 'filter-by-size':
    exec_command(args, filter_ops.apply_filter, config.FILTER_NAME_SIZE, filter_ops.filter_test_size, args.size_start,
                 args.size_end)
elif args.command == 'filter-by-prop':
    if args.props is None:
        validation_error(args, 'At least one property must be specified')
    props = []
    for prop in args.props:
        prop_val = prop.split('|')
        if len(prop_val) not in [1, 2]:
            validation_error(args, 'Invalid format for property: %s' % prop)
        props.append(prop_val)
    exec_command(args, filter_ops.apply_filter, config.FILTER_NAME_PROP, filter_ops.filter_test_prop, props)
elif args.command == 'list-filters':
    exec_command(args, filter_ops.list_filters)
elif args.command == 'clear-filters':
    exec_command(args, filter_ops.clear_filters)

# Props ops
if args.command == 'set-prop':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, props_ops.set_prop, path, args.prop, args.val)
elif args.command == 'del-prop':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, props_ops.del_prop, path, args.prop)
elif args.command == 'list-props':
    path = args.path if args.path is not None else os.getcwd()
    set_vfs_by_path(args, path)
    exec_command(args, props_ops.list_props, path)
elif args.command == 'unique-props':
    path = args.path if args.path is not None else os.getcwd()
    if not os.path.isdir(path):
        validation_error(args, 'Path "%s" is not a directory' % path)
    set_vfs_by_path(args, path)
    exec_command(args, props_ops.list_unique_props, path)

# Save ops
if args.command == 'save':
    save_ops.set_save_mode(args.mode)
    save_ops.start_user_input_thread()
    exec_command(args, save_ops.save, args.restart, args.del_save_file)
