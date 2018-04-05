# VFS filter related ops

import errno
import mimetypes
import os
import shutil

import config
import core
import freeze_ops
from log_utils import logger

# Initialization
mimetypes.init()


# Get a sorted list of unique mimetypes
def get_all_mime_types():
    return sorted(list(set([mimetype.split('/')[0] for ext, mimetype in mimetypes.types_map.items()]))
                  + [config.FILTER_MIMETYPE_UNKNOWN])


# Path of a filter directory
def compute_filter_path(filter_name):
    vfs_path = core.compute_vfs_path()
    path = os.path.join(vfs_path, config.VFS_FILTERS_DIR, filter_name)
    logger.debug('Filter path computed: %s', path)
    return path


# Test for mimetypes
def filter_test_mimetype(virtual_file, mimes):
    if os.path.isdir(virtual_file):
        return False
    filename = os.path.basename(virtual_file)
    mimetype_full, encoding = mimetypes.guess_type(filename)
    if mimetype_full is None:
        mimetype = config.FILTER_MIMETYPE_UNKNOWN
    else:
        mimetype = mimetype_full.split('/')[0]
    return mimetype in mimes


# Test for file size range
def filter_test_size(virtual_file, lower, upper):
    if os.path.isdir(virtual_file):
        return False
    stats = core.get_file_stats_for_symlink(virtual_file) if os.path.islink(virtual_file) else None
    if stats is None:
        return False
    lower_pass = lower < 0 or stats.size >= lower
    upper_pass = upper < 0 or stats.size <= upper
    return lower_pass and upper_pass


# Test for file and dir prop
def filter_test_prop(virtual_file, props):
    pass_ = False
    for prop in props:
        value = True if len(prop) == 1 else prop[1]
        if value == core.get_virtual_path_prop(prop[0], virtual_file):
            pass_ = True
            break
    return pass_


        # Get names of all applied filters
def get_all_filter_names():
    all_filters_dir = os.path.join(core.compute_vfs_path(), config.VFS_FILTERS_DIR)
    return os.listdir(all_filters_dir)


# CLI TARGET: Apply the specified filter to the current VFS
def apply_filter(filter_name, filter_test, *test_args):
    vfs = core.get_current_vfs()
    logger.debug('Applying filter %s on VFS %s', filter_name, vfs.name)

    # Check and create filter path
    filter_path = compute_filter_path(filter_name)
    logger.debug('Trying to create filter directory %s', filter_path)
    if os.path.isdir(filter_path):
        raise core.VfsException('Filter %s has already been applied', filter_name)
    os.mkdir(filter_path)

    # Move to filter path
    logger.debug('Moving files and directories to filter directory based on filter test')
    pass_count = total_count = 0
    for root, dirs, files in os.walk(vfs.virtual_base):
        if freeze_ops.is_frozen(root):
            logger.debug('Skipping frozen directory %s', root)
            dirs[:] = []
            continue
        dir_passed = filter_test(root, *test_args)
        if dir_passed:
            total_count += len(files)
            pass_count += len(files)
            logger.debug('Directory passed filter test: %s', root)
            logger.debug('Cumulative aggregates: total: %d, passed: %d', total_count, pass_count)
            dirs[:] = []
            continue
        failed_files = []
        for file_ in files:
            if core.is_vfs_file(file_):
                continue
            file_path = os.path.join(root, file_)
            rel_file_path = os.path.relpath(file_path, vfs.virtual_base)
            passed = filter_test(file_path, *test_args)
            if not passed:
                failed_files.append(rel_file_path)
        total_count += len(files)
        pass_count += len(files) - len(failed_files)
        logger.debug('Cumulative aggregates: total: %d, passed: %d', total_count, pass_count)
        logger.debug('Failed files: %s', failed_files)
        if (len(files) == 0 or len(failed_files) > 0) and root != vfs.virtual_base:
            rel_root_path = os.path.relpath(root, vfs.virtual_base)
            dest_dir = os.path.abspath(os.path.join(filter_path, rel_root_path))
            logger.debug('Creating directory: %s', dest_dir)
            os.makedirs(dest_dir)
            prop_path = core.compute_virtual_dir_prop_path(root)
            prop_rel = os.path.relpath(prop_path, vfs.virtual_base)
            prop_dest = os.path.abspath(os.path.join(filter_path, prop_rel))
            try:
                shutil.copy(prop_path, prop_dest)
                logger.debug('Coped prop file from %s to %s', prop_path, prop_dest)
            except IOError as ex:
                if ex.errno != errno.ENOENT:
                    raise
        for rel_file_path in failed_files:
            src_path = os.path.abspath(os.path.join(vfs.virtual_base, rel_file_path))
            dest_path = os.path.abspath(os.path.join(filter_path, rel_file_path))
            logger.debug('Moving file %s to %s', src_path, dest_path)
            shutil.move(src_path, dest_path)
            prop_path = core.compute_virtual_file_prop_path(src_path)
            prop_rel = os.path.relpath(prop_path, vfs.virtual_base)
            prop_dest = os.path.abspath(os.path.join(filter_path, prop_rel))
            try:
                shutil.move(prop_path, prop_dest)
                logger.debug('Moved prop file from %s to %s', prop_path, prop_dest)
            except IOError as ex:
                if ex.errno != errno.ENOENT:
                    raise

    # Cleanup empty dirs
    def _cleanup_empty_dirs(root):
        if freeze_ops.is_frozen(root):
            logger.debug('Skipping frozen directory %s', root)
            return False
        can_del = root != vfs.virtual_base
        elems = os.listdir(root)
        for elem in elems:
            elem_path = os.path.join(root, elem)
            if os.path.isdir(elem_path):
                can_del = can_del if _cleanup_empty_dirs(elem_path) else False
            elif not core.is_vfs_file(elem_path):
                can_del = False
        if can_del:
            logger.debug('Deleting empty directory %s', root)
            shutil.rmtree(root)
        return can_del

    logger.debug('Cleaning up empty directories')
    _cleanup_empty_dirs(vfs.virtual_base)
    logger.info('Filter %s has been successfully applied. Files remaining: %d of %d',
                filter_name, pass_count, total_count)


# Check and throw an error for any potential conflicts that can occur during a clear filters merge
def _check_filter_conflicts():
    rel_path_index = {}
    vfs = core.get_current_vfs()
    filter_names = get_all_filter_names()
    filter_paths = [compute_filter_path(filter_name) for filter_name in filter_names]
    logger.debug('Creating relative path index for all filters and virtual directories in VFS %s', vfs.name)
    for tree_type in [vfs.virtual_base] + filter_paths:
        for root, dirs, files in os.walk(tree_type):
            for elem in [root] + [os.path.join(root, file_) for file_ in files]:
                rel_path = os.path.relpath(elem, tree_type)
                if rel_path not in rel_path_index:
                    rel_path_index[rel_path] = []
                rel_path_index[rel_path].append(elem)
    logger.debug('Checking for merge conflicts')
    for rel_path, elems in rel_path_index.items():
        if len(elems) == 1:
            continue
        logger.debug('Multiple candidates for rel path %s: %s', rel_path, elems)
        non_frozen_dirs = filter(lambda elem: os.path.isdir(elem) and not freeze_ops.is_frozen(elem), elems)
        vfs_files = filter(lambda elem: os.path.isfile(elem) and core.is_vfs_file(elem), elems)
        if len(non_frozen_dirs) != len(elems) and len(vfs_files) != len(elems):
            raise core.VfsException('Conflict detected while clearing filters in the following paths: %s' % elems)
    logger.debug('No filter merge conflicts were identified')


# CLI TARGET: Clear all filters
def clear_filters():
    vfs = core.get_current_vfs()
    filter_names = get_all_filter_names()
    logger.debug('Clearing filters: %s', filter_names)

    if len(filter_names) == 0:
        logger.info('No filters to clear')
        return

    # Check for conflicts
    _check_filter_conflicts()

    # Merge
    filter_paths = [compute_filter_path(filter_name) for filter_name in filter_names]
    for filter_path in filter_paths:
        logger.debug('Merging filter path: %s', filter_path)

        for root, dirs, files in os.walk(filter_path):
            # Merge directories
            rel_root = os.path.relpath(root, filter_path)
            target_path = os.path.abspath(os.path.join(vfs.virtual_base, rel_root))
            logger.debug('Trying to create directory %s', target_path)
            try:
                os.makedirs(target_path)
            except OSError as ex:
                if ex.errno == errno.EEXIST:
                    logger.debug('Directory %s already exists', target_path)
                else:
                    raise

            # Move files
            for file_ in files:
                file_path = os.path.join(root, file_)
                rel_file_path = os.path.join(rel_root, file_)
                target_file_path = os.path.abspath(os.path.join(vfs.virtual_base, rel_file_path))
                logger.debug('Moving file %s to %s', file_path, target_file_path)
                shutil.move(file_path, target_file_path)

    logger.debug('Deleting filter directories')
    # Remove filter directory
    for filter_path in filter_paths:
        logger.debug('Deleting directory: %s', filter_path)
        shutil.rmtree(filter_path)

    logger.info('The following filters have been cleared: %s', ", ".join(filter_names))


# CLI TARGET: Display a list of applied filter names
def list_filters():
    filters = get_all_filter_names()
    if len(filters) == 0:
        logger.info('No filters have been applied')
    else:
        logger.info('Following filters have been applied:')
        for i, filter_ in enumerate(filters):
            logger.info("%d. %s", i + 1, filter_)
