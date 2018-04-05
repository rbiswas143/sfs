# Operations related to merging of VFS directories

import json
import os
import shutil
import time

import config
import core
import freeze_ops
from log_utils import logger


# Check that two directories can be merged
def _validate_merge_targets(source_path, dest_path):
    logger.debug('Validating merge for source dir: %s and dest dir %s', source_path, dest_path)

    # Valid dirs
    if source_path is None or not os.path.isdir(source_path):
        raise core.VfsException("Invalid source path: %s" % source_path)
    if dest_path is None or not os.path.isdir(dest_path):
        raise core.VfsException("Invalid dest path: %s" % dest_path)

    # Not nested
    if core.is_parent_dir(source_path, dest_path) or core.is_parent_dir(dest_path, source_path):
        raise core.VfsException("Source and destination paths cannot be nested")

    # Same VFS
    source_vfs = core.get_vfs_by_path(source_path)
    if source_vfs is None:
        raise core.VfsException('Path %s is not part of any available VFS' % source_path)
    dest_vfs = core.get_vfs_by_path(dest_path)
    if dest_vfs is None:
        raise core.VfsException('Path %s is not part of any available VFS' % dest_path)
    if source_vfs is not dest_vfs:
        raise core.VfsException('Sorce VFS %s is different from destination VFS %s' % source_vfs.name,
                                dest_vfs.name)


# Identifies potential merge conflicts
def get_merge_conflicts(source_path, dest_path, mark_del_source=False):
    logger.debug('Identifying merge conflicts for source dir: %s and dest dir %s', source_path, dest_path)

    # Validate
    _validate_merge_targets(source_path, dest_path)

    dest_index = {}
    conflicts = []
    for tree_type in ['dest', 'source']:
        for root, dirs, files in core.vfs_walk(dest_path if tree_type == 'dest' else source_path):
            if root not in [source_path, dest_path]:
                rel_root_path = os.path.relpath(root, dest_path if tree_type == 'dest' else source_path)
                other_tree_path = os.path.join(source_path if tree_type == 'dest' else dest_path, rel_root_path)
                if os.path.islink(other_tree_path) or os.path.isfile(other_tree_path):
                    raise core.VfsException('Cannot merge non directory %s with directory %s', other_tree_path, root)
                if freeze_ops.is_frozen(root):
                    logger.debug('Found frozen directory %s. Skipping children', root)
                    if os.path.isdir(other_tree_path):
                        raise core.VfsException('Cannot merge frozen directory %s', root)
                    else:
                        dirs[:] = []
                        continue
            for file_ in files:
                file_path = os.path.join(root, file_)
                # Get file stats
                islink = os.path.islink(file_path)
                if islink:
                    file_stats = core.get_file_stats_for_symlink(file_path)
                else:
                    file_stats = None
                if file_stats is None:
                    logger.warn('Stats not found for file %s. Is symlink: %s', file_path, islink)
                # Relative path to root directory of merge
                rel_file_path = os.path.relpath(file_path, dest_path if tree_type == 'dest' else source_path)

                if tree_type == 'dest':
                    # Save the rel file path and stats
                    dest_index[rel_file_path] = file_stats
                else:
                    # Lookup rel file path. If found, a conflict is registered
                    if rel_file_path in dest_index:
                        dest_file_stats = dest_index[rel_file_path]
                        source_rename = list(os.path.splitext(os.path.basename(rel_file_path)))
                        source_rename.insert(1, "_merged_at_%d" % time.time())
                        source_rename = ''.join(source_rename)
                        conflict = {
                            "rel_path": rel_file_path,
                            "source": {
                                "actual_path": file_stats.actual_path if file_stats is not None else None,
                                "size": core.get_readable_size(
                                    file_stats.size) if file_stats is not None else None,
                                "is_symlink": os.path.islink(os.path.join(source_path, rel_file_path)),
                                "created": time.ctime(file_stats.ctime) if file_stats is not None else None,
                                "modified": time.ctime(file_stats.mtime) if file_stats is not None else None,
                                "keep": 1,
                                "rename": source_rename
                            },
                            "dest": {
                                "actual_path": dest_file_stats.actual_path if dest_file_stats is not None else None,
                                "size": core.get_readable_size(
                                    dest_file_stats.size) if dest_file_stats is not None else None,
                                "is_symlink": os.path.islink(os.path.join(dest_path, rel_file_path)),
                                "created": time.ctime(dest_file_stats.ctime) if dest_file_stats is not None else None,
                                "modified": time.ctime(dest_file_stats.mtime) if dest_file_stats is not None else None,
                                "keep": 1,
                            }
                        }
                        conflict['source']['keep'] = (0 if mark_del_source and conflict['source']['size'] is not None
                                                           and conflict['source']['size'] ==
                                                               conflict['dest']['size'] else 1)
                        conflict['equal_size'] = (conflict['source']['size'] is not None
                                                  and conflict['source']['size'] == conflict['dest']['size'])
                        conflicts.append(conflict)
                        logger.debug('Conflict identified: %s', conflict)

    logger.debug('Num conflicts: %d', len(conflicts))
    return conflicts


# Merges two directories handling conflicts as specified
def resolve_merge_conflicts(source_path, dest_path, conflicts):
    logger.debug('Merging source dir: %s and dest dir %s', source_path, dest_path)

    # Validate
    _validate_merge_targets(source_path, dest_path)

    conflicts_index = {conf['rel_path']: conf for conf in conflicts}
    new_dir_count = del_count = move_count = copy_count = 0

    for tree_type in ['dest', 'source']:
        for root, dirs, files in core.vfs_walk(dest_path if tree_type == 'dest' else source_path):
            # Relative path of directory wrt merge root
            rel_root = os.path.relpath(root, dest_path if tree_type == 'dest' else source_path)

            if tree_type == 'source':
                # Try to copy source directory
                merge_dir_path = os.path.join(dest_path, rel_root)
                try:
                    os.mkdir(merge_dir_path)
                    new_dir_count += 1
                    logger.debug('Created new directory: %s', merge_dir_path)
                except OSError:
                    logger.debug('Failed to create directory: %s. It already exists', merge_dir_path)

            for file_ in files:
                file_path = os.path.join(root, file_)
                rel_file_path = os.path.relpath(file_path, dest_path if tree_type == 'dest' else source_path)
                merge_file_dest_default = os.path.join(dest_path, rel_file_path)

                # The following parameters are determined for each file before any operation
                merge_file_mode = None  # copy/move/del
                merge_file_dest = None

                if tree_type == 'source':
                    # Decide whether to copy the file or not in case of a conflict
                    if rel_file_path in conflicts_index:
                        source_info = conflicts_index[rel_file_path]['source']
                        if bool(source_info['keep']):
                            merge_file_mode = 'copy'
                            merge_file_dest = merge_file_dest_default if 'rename' not in source_info else os.path.join(
                                os.path.dirname(merge_file_dest_default), source_info['rename'])
                    else:
                        merge_file_mode = 'copy'
                        merge_file_dest = merge_file_dest_default
                else:  # tree_type == 'dest'
                    # Decide whether to move or delete the file in case of a conflict
                    if rel_file_path in conflicts_index:
                        dest_info = conflicts_index[rel_file_path]['dest']
                        if bool(dest_info['keep']):
                            merge_file_mode = 'move'
                            merge_file_dest = merge_file_dest_default if 'rename' not in dest_info else os.path.join(
                                os.path.dirname(merge_file_dest_default), dest_info['rename'])
                        else:
                            merge_file_mode = 'del'

                # Perform action on file
                if merge_file_mode == 'del':
                    os.unlink(file_path)
                    del_count += 1
                    logger.debug('Deleted file %s', file_path)
                elif merge_file_mode == 'move' and file_path != merge_file_dest:
                    os.rename(file_path, merge_file_dest)
                    move_count += 1
                    logger.debug('Moved file %s to %s', file_path, merge_file_dest)
                elif merge_file_mode == 'copy':
                    if os.path.islink(file_path):
                        core.copy_symlink(file_path, merge_file_dest)
                        logger.debug('Copied symlink %s to %s', file_path, merge_file_dest)
                    else:
                        shutil.copy2(file_path, merge_file_dest)
                        logger.debug('Copied file %s to %s', file_path, merge_file_dest)
                    copy_count += 1
                else:  # no action
                    logger.debug('No action performed for file %s', file_path)

    logger.debug('Merge complete. new_dir_count:%d, del_count:%d, move_count:%d, copy_count:%d',
                 new_dir_count, del_count, move_count, copy_count)

    return new_dir_count, del_count, move_count, copy_count


# Path to merge conflicts JSON
def _get_json_path(dir_path):
    path = os.path.join(os.path.abspath(dir_path), os.path.basename(os.path.abspath(dir_path)) + config.MERGE_FILE_EXT)
    logger.debug('Merge conflicts JSON path generated: %s', path)
    return path


# CLI TARGET: Identifies merge conflicts and saves them to JSON
# Merges source directory into destination directory applying necessary conflict resolutions
def merge(dest_path, source_path=None, del_source=False, gen_json=False, del_json=False, mark_del_source=False):
    logger.debug('Arguments: dest_path:%s, source_path:%s, del_source:%s, gen_json:%s, del_json:%s',
                 dest_path, source_path, del_source, gen_json, del_json)

    json_path = _get_json_path(dest_path)
    if not os.path.isfile(json_path) or gen_json:  # Generate JSON
        logger.debug('Generating dedup json')
        conflicts = get_merge_conflicts(source_path, dest_path, mark_del_source)
        if len(conflicts) > 0:  # Save JSON
            json_data = {
                "source_base": os.path.abspath(source_path),
                "dest_base": os.path.abspath(dest_path),
                "conflicts": conflicts
            }
            with open(json_path, 'w') as jf:
                json.dump(json_data, jf, indent=2, sort_keys=True)
            logger.info("%d merge conflicts have been identified and stored in the JSON file %s. " +
                        "Review the file and use it to resolve the conflicts", len(conflicts), json_path)
            return
        else:  # No conflicts. Continue merge
            logger.info("No conflicts detected")
    else:  # Load JSON
        logger.debug('Loading dedup json')
        with open(json_path, 'r') as jf:
            json_data = json.load(jf)
        source_path = json_data['source_base']
        conflicts = json_data['conflicts']

    # Confirm Merge
    logger.info("The destination directory might be modified during the merge." +
                "Are you sure you want to merge source directory '%s' into destination directory '%s'?(y/[n])",
                source_path, dest_path)
    inp = raw_input()
    logger.debug('User input recd: %s', inp)
    if inp != 'y':
        logger.info('Merge has been cancelled')
        return

    # Merge
    new_dir_count, del_count, move_count, copy_count = resolve_merge_conflicts(source_path, dest_path, conflicts)
    logger.info("Merge completed successfully")
    logger.info("New directories created: %d", new_dir_count)
    logger.info("Files deleted: %d", del_count)
    logger.info("Files moved: %d", move_count)
    logger.info("Files copied: %d", copy_count)

    # Delete source
    logger.debug("Delete source: %s", del_source)
    if del_source:
        shutil.rmtree(source_path)
        logger.info("Source directory %s has been removed", source_path)

    # Delete JSON
    logger.debug("Delete JSON: %s", del_json)
    if os.path.isfile(json_path) and del_json:
        os.unlink(json_path)
        logger.info("Merge conflicts JSON file %s has been deleted" % json_path)
