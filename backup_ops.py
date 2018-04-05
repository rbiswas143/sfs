# Backup and restore related ops

import time

import core
from log_utils import logger


# CLI TARGET: Backup a VFS
def create_backup(comment):
    vfs = core.get_current_vfs()
    backup_name = core.create_backup(vfs.name, comment)
    logger.info('VFS %s has been successfully backed up (Backup file is %s)', vfs.name, backup_name)


# CLI TARGET: Delete a backup
def del_backup(backup_name):
    core.del_backup(backup_name)
    logger.info('Backup %s has been successfully deleted', backup_name)


# CLI TARGET: List backups for single or all VFS
def list_all_backups(vfs_name=None):
    all_backups = core.list_backups()
    if vfs_name is not None:
        vfs = core.get_vfs_by_name(vfs_name)
        if vfs is None:
            raise core.VfsException('VFS %s has not yet been created', vfs_name)
        all_backups = filter(lambda x: x.vfs == vfs_name, all_backups)
    if len(all_backups) == 0:
        logger.info('No backups found')
        return
    all_backups.sort(key=lambda x: x.created, reverse=True)
    logger.info('Following backups are available: ')
    for backup in all_backups:
        created = time.ctime(backup.created)
        logger.info('Backup name: %s\tVFS: %s\tCreated: %s\tComment: %s',
                    backup.name, backup.vfs, created, backup.comment)


# CLI TARGET: Restore a backup
def restore_backup(backup_name):
    core.restore_backup(backup_name)
    logger.info('Backup %s has been successfully restored', backup_name)
