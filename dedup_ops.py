# Operations related to deduplication of VFS files

import json
import os
import time

import config
import core
import freeze_ops
from log_utils import logger


# Identifies duplicates in a VFS directory
def get_duplicates(path, del_duplicates_flag=False):
    dup_file_size = {}
    for root, dirs, files in core.vfs_walk(path):
        if freeze_ops.is_frozen(root):
            logger.debug('Dir %s is frozen. Skipping all paths in it', root)
            dirs[:] = []
            continue
        for file_ in files:
            file_name = os.path.join(root, file_)
            if not os.path.islink(file_name):
                logger.warn('Skipping deduplication for file %s as it is not a symlink', file_name)
                continue
            file_stat = core.get_file_stats_for_symlink(file_name)
            file_name = os.path.basename(file_stat.actual_path)
            if file_name not in dup_file_size:
                dup_file_size[file_name] = {}
            if file_stat.size not in dup_file_size[file_name]:
                dup_file_size[file_name][file_stat.size] = []
            file_path = os.path.join(root, file_)
            rel_path = os.path.relpath(file_path, path)
            dup_file_size[file_name][file_stat.size].append((rel_path, file_stat))
    logger.debug('Unique symlinks in file size index: %d', len(dup_file_size))

    duplicates = []
    for file_name in dup_file_size.keys():
        for file_size in dup_file_size[file_name].keys():
            if len(dup_file_size[file_name][file_size]) > 1:
                dup = []
                i = 0
                for rel_path, file_stats in dup_file_size[file_name][file_size]:
                    dup.append({
                        'path': rel_path,
                        'created': time.ctime(file_stat.ctime),
                        'modified': time.ctime(file_stat.mtime),
                        'keep': 1 if i == 0 else (0 if del_duplicates_flag else 1)
                    })
                    i += 1
                duplicates.append(dup)
    logger.debug('Num duplicates: %d', len(duplicates))

    return duplicates


# Deletes identified duplicates from a VFS directory
def del_duplicates(path, duplicates):
    del_count = 0
    for dup_entry in duplicates:
        for dup_file in dup_entry:
            rel_path, keep = dup_file['path'], bool(dup_file['keep'])
            if not keep:
                full_path = os.path.join(path, rel_path)
                logger.info('Deleting file: %s' % full_path)
                os.unlink(full_path)
                del_count += 1
    return del_count


# Path to dedup json file
def _get_json_path(dir_path):
    path = os.path.join(dir_path, os.path.basename(dir_path) + config.DUP_FILE_EXT)
    logger.debug('Dedup JSON path generated: %s', path)
    return path


# CLI TARGET: Identifies duplicates and saves them as JSON
def generate_dedup_json(path, override=False, del_duplicates_flag=False):
    logger.debug('Arguments: path%s, override:%s', path, override)

    duplicates = get_duplicates(path, del_duplicates_flag)
    if len(duplicates) == 0:
        logger.info("No duplicates found")
        return
    json_path = _get_json_path(path)
    if not override and os.path.exists(json_path):
        raise core.VfsException(
            'JSON file %s already exists. Use the override flag or delete it in order to proceed' % json_path)
    with open(json_path, 'w') as jf:
        json.dump(duplicates, jf, indent=2, sort_keys=True)
    logger.info("%d duplicates have been identified and stored in the JSON file %s. " +
                "Review the file and use it to delete duplicates", len(duplicates), json_path)


# CLI TARGET: Deduplicates using the JSON file
def dedup_using_json(path, del_json=False):
    logger.debug('Arguments: path%s, del_json:%s', path, del_json)

    json_path = _get_json_path(path)
    with open(json_path, 'r') as jf:
        duplicates = json.load(jf)
    logger.info('Contents of path %s might be permanently altered. Proceed with deduplication?(y/[n])', path)
    inp = raw_input()
    logger.debug('User input recd: %s', inp)
    if inp != 'y':
        logger.info('Deduplication has been cancelled')
        return
    del_count = del_duplicates(path, duplicates)
    logger.info("%d duplicates have been deleted successfully", del_count)
    if del_json:
        logger.debug('Trying to delete JSON file at %s', json_path)
        os.unlink(json_path)
        logger.info("Deleted the JSON file %s", json_path)
