# Operations related to saving a VFS

import copy
import errno
import os
import shutil
import threading
import time

import config
import core
import filter_ops
from log_utils import logger


# Meta data classes for disc schemes


# Scheme representing data transfer from one disc to another up to a size
class InterDiscTransfer(core.PrintableObject):
    def __init__(self, disc1, disc2, transfer_size, last, transfer_completed=0, completed=0):
        self.disc1 = disc1
        self.disc2 = disc2
        self.transfer_size = transfer_size
        self.last = last
        self.transfer_completed = transfer_completed
        self.completed = completed


# Scheme representing all file deletions in a disc
class DiscDeletion(core.PrintableObject):
    def __init__(self, disc, completed=False):
        self.disc = disc
        self.completed = completed


# Meta data classes for save status


# Status of  virtual file copy or move
class TransferStatus(core.PrintableObject):
    def __init__(self, virtual_path, completed=False):
        self.virtual_path = virtual_path
        self.completed = completed


# Status of an actual file deletion
class DeletionStatus(core.PrintableObject):
    def __init__(self, actual_path, completed=False):
        self.actual_path = actual_path
        self.completed = completed


# Cached
_disc_sizes = None
_disc_transfers = None
_disc_transfer_sizes = None
_disc_deletions = None
_disc_deletion_sizes = None
_save_mode = None
_save_status = None


# Clear all cache
def _invalidate_save_cache():
    logger.debug('Invalidating save cache')
    global _disc_sizes
    global _disc_transfers
    global _disc_transfer_sizes
    global _disc_deletions
    global _disc_deletion_sizes
    global _save_mode
    global _save_status
    _disc_sizes = None
    _disc_transfers = None
    _disc_transfer_sizes = None
    _disc_deletions = None
    _disc_deletion_sizes = None
    _save_mode = None
    _save_status = None


# Get path to save status file
def compute_save_file_path():
    save_file_path = os.path.join(core.compute_vfs_path(), config.SAVE_FILE_NAME)
    logger.debug('Save file p[ath computed: %s', save_file_path)
    return save_file_path


# Set the save mode globally
def set_save_mode(mode):
    global _save_mode
    if mode is None:
        raise core.VfsException('Invalid save mode: %s' % mode)
    _save_mode = mode
    logger.debug('Save mode has been set to "%s"', mode)


# Get the global save mode
def get_save_mode():
    if _save_mode is None:
        raise core.VfsException('Save mode has not been set')
    return _save_mode


# Get the actual content size for each disc (cached)
def get_all_disc_sizes():
    global _disc_sizes
    if _disc_sizes is not None:
        return _disc_sizes
    logger.debug('Not cached. Fetching all disc sizes')
    discs = core.get_all_discs()
    _disc_sizes = {disc.name: core.get_actual_dir_size(disc.disc_base) for disc in discs}
    logger.debug('All disc sizes have been computed successfully: %s', _disc_sizes)
    return _disc_sizes


# Get the actual content size for a disc
def get_disc_size(disc_name):
    disc_sizes = get_all_disc_sizes()
    return disc_sizes[disc_name]


# Get save status of virtual files and directories as a map of disc transfers (cached)
def get_disc_transfers():
    global _disc_transfers
    if _disc_transfers is not None:
        return _disc_transfers

    logger.debug('Not cached. Computing disc transfers')
    vfs = core.get_current_vfs()
    discs = core.get_all_discs()
    disc_transfers = {d1.name: {d2.name: [] for d2 in discs} for d1 in discs}

    dir_count = file_count = 0

    for root, dirs, files in core.vfs_walk(vfs.virtual_base):

        # Directories
        abs_root = os.path.abspath(root)
        save_map = core.get_save_map_by_virtual_path(abs_root)
        if save_map is None:
            logger.debug('No save map for virtual directory %s', abs_root)
            continue
        dest_disc = core.get_disc_by_path(save_map.actual_dir)
        # Treating source and destination disc as same for directories as they are not actually copied
        root_source_disc = dest_disc
        disc_transfers[root_source_disc.name][dest_disc.name].append(TransferStatus(abs_root))
        dir_count += 0
        logger.debug('Added transfer status for virtual directory %s with source disc %s and destination disc %s',
                     abs_root, root_source_disc.name, dest_disc.name)

        # Files
        for file_ in files:
            abs_file = os.path.abspath(os.path.join(root, file_))
            if not os.path.islink(abs_file):
                logger.warn('File %s is not a symlink. Ignoring it for disc transfers', abs_file)
                continue
            file_stat = core.get_file_stats_for_symlink(abs_file)
            if file_stat is None:
                logger.error('Stats not available for symlink %s. Ignoring it for disc transfers', abs_file)
                continue
            file_source_disc = core.get_disc_by_path(file_stat.actual_path)
            disc_transfers[file_source_disc.name][dest_disc.name].append(TransferStatus(abs_file))
            file_count += 0
            logger.debug('Added transfer status for symlink %s with source disc %s and destination disc %s',
                         abs_file, file_source_disc.name, dest_disc.name)

    _disc_transfers = disc_transfers
    logger.debug('Disc transfers generated successfully. Directories added: %d, Files added: %d', dir_count, file_count)
    logger.debug('Disc transfers: %s', disc_transfers)
    return disc_transfers


# Get sizes of all inter disc transfers(cached)
def get_disc_transfer_sizes():
    global _disc_transfer_sizes
    if _disc_transfer_sizes is not None:
        return _disc_transfer_sizes

    logger.debug('Not cached. Computing disc transfer sizes')
    disc_transfers = get_disc_transfers()
    discs = core.get_all_discs()
    disc_transfer_sizes = {d1.name: {d2.name: 0 for d2 in discs} for d1 in discs}

    for disc1 in discs:
        for disc2 in discs:
            transfers = disc_transfers[disc1.name][disc2.name]
            for transfer_status in transfers:
                if os.path.islink(transfer_status.virtual_path):
                    file_stat = core.get_file_stats_for_symlink(transfer_status.virtual_path)
                    disc_transfer_sizes[disc1.name][disc2.name] += file_stat.size
                elif os.path.isdir(transfer_status.virtual_path):
                    # Directories are assumed ot be of a negligible size,
                    #  so that they are not ignored during scheme generation
                    disc_transfer_sizes[disc1.name][disc2.name] += config.DIR_SIZE

    _disc_transfer_sizes = disc_transfer_sizes
    logger.debug('Computed disc transfer sizes successfully: %s', disc_transfer_sizes)
    return _disc_transfer_sizes


# Get deletion status of actual files by disc (cached)
def get_disc_deletions():
    global _disc_deletions
    if _disc_deletions is not None:
        return _disc_deletions

    logger.debug('Not cahced. Fetching disc deletions')
    discs = core.get_all_discs()
    a2v_map = core.get_actual_to_virtual_map()
    all_stats = core.get_file_stats_for_all_collections()
    disc_deletions = {disc.name: [] for disc in discs}

    del_count = 0

    for actual_path, stats in all_stats.items():
        if isinstance(stats, core.DirStat):
            # Directories are not deleted
            continue
        if actual_path not in a2v_map:
            # Add those actual files for deletion which do not have a virtual link
            disc = core.get_disc_by_path(actual_path)
            disc_deletions[disc.name].append(DeletionStatus(actual_path))
            del_count += 1
            logger.debug('Actual file %s has been added for deletion', actual_path)

    _disc_deletions = disc_deletions
    logger.debug('Disc deletions have been fetched successfully. Num deletions: %d', del_count)
    logger.debug('Disc deletions sizes %s', disc_deletions)
    return disc_deletions


# Get total deletion sizes for each disc (cached)
def get_disc_deletion_sizes():
    global _disc_deletion_sizes
    if _disc_deletion_sizes is not None:
        return _disc_deletion_sizes

    logger.debug('Not cached. Computing disc deletion sizes')
    discs = core.get_all_discs()
    disc_deletions = get_disc_deletions()
    disc_deletion_sizes = {disc.name: 0 for disc in discs}

    for disc_name, deletions in disc_deletions.items():
        size = 0
        for del_status in deletions:
            stats = core.get_file_stats_for_actual_path(del_status.actual_path)
            size += stats.size
        disc_deletion_sizes[disc_name] += size

    _disc_deletion_sizes = disc_deletion_sizes
    logger.debug('Successfully computed disc deletion sizes: %s', disc_deletion_sizes)
    return disc_deletion_sizes


# Ensure that each sub-element of the VFS base directory is mapped for saving
def validate_exhaustive_save_maps():
    vfs = core.get_current_vfs()
    for elem in os.listdir(vfs.virtual_base):
        elem_abs_path = os.path.join(vfs.virtual_base, elem)
        save_map = core.get_save_map_by_virtual_path(elem_abs_path)
        if save_map is None:
            raise core.VfsException('No save mapping for virtual dir %s in VFS %s' % (elem_abs_path, vfs.name))


# Validate that each collection lies within a registered disc
def validate_exhaustive_discs():
    cols = core.get_all_collections()
    for col in cols:
        disc = core.get_disc_by_path(col.actual_base)
        if disc is None:
            raise core.VfsException(
                'Disc has not been registered for Collection %s with actual base %s' % (col.name, col.actual_base))


# Validate that space in each disc is sufficient for the transfers
def validate_space_availability():
    mode = get_save_mode()
    logger.debug('Performing space validations for all discs. Save mode is "%s"', mode)

    discs = core.get_all_discs()
    disc_transfer_sizes = get_disc_transfer_sizes()
    disc_deletion_sizes = get_disc_deletion_sizes()

    for disc1 in discs:
        if disc1.capacity is None:
            # Skip validation for discs with no space restriction
            logger.debug('Slipping space validation for disc %s with capacity %s', disc1.name, disc1.capacity)
            continue

        # Account in deletions
        transfer_out = 0 if mode == 'copy' else disc_deletion_sizes[disc1.name]
        transfer_in = 0
        logger.debug('Deletion size for disc %s: %d', disc1.name, transfer_out)

        # Account in inter disc transfers
        for disc2 in discs:
            if disc1 is not disc2:
                transfer_in += disc_transfer_sizes[disc2.name][disc1.name]
                if mode == 'move':
                    transfer_out += disc_transfer_sizes[disc1.name][disc2.name]
                logger.debug('Disc %s stats after transfer with disc %s: transfer_in: %d, transfer_out: %d', disc1.name,
                             disc2.name, transfer_in, transfer_out)

        # Validate
        req_space = transfer_in
        avail_space = disc1.capacity - get_disc_size(disc1.name) + transfer_out
        logger.debug('Final stats for disc %s: req_space:%d, avail_space:%d', disc1.name, req_space, avail_space)
        if avail_space < req_space:
            raise core.VfsException(
                'Disc %s will not have enough space for the transfers. Required %s. Available %s' % (
                    disc1.name, core.get_readable_size(req_space), core.get_readable_size(avail_space)))


# Validate that no filters have been applied
def validate_filters():
    filters = filter_ops.get_all_filter_names()
    if len(filters) > 0:
        raise core.VfsException('The following filters must be cleared befiore saving: %s', ", ".join(filters))


# Generate optimized order of disc transfers and deletions for save with move "mode"
def generate_disc_scheme_for_move():
    discs = core.get_all_discs()
    disc_transfer_sizes = get_disc_transfer_sizes()
    disc_deletion_sizes = get_disc_deletion_sizes()
    disc_capacities = {
        disc.name: None if disc.capacity is None else
        max(0, disc.capacity - get_disc_size(disc.name)) for disc in discs
    }

    # Generate the scheme with the least inter disc transfers by brute force
    def _gen_scheme(disc_transfer_sizes, disc_deletion_sizes, disc_capacities):
        logger.debug('Begin scheme gen')

        # Are all deletions and transfers completed
        def _completed(disc_transfer_sizes, disc_deletion_sizes):
            transfer_left = sum([sum(disc_transfer_sizes[disc1_name][disc2]
                                     for disc2 in disc_transfer_sizes[disc1_name]) for disc1_name in
                                 disc_transfer_sizes])
            deletion_left = sum([deletions for disc, deletions in disc_deletion_sizes.items()])
            completed = transfer_left <= 0 and deletion_left <= 0
            logger.debug('Evaluated completion: transfer_left:%d, deletion_left:%d, completed: %s', transfer_left,
                         deletion_left, completed)
            return completed

        # Clone data structures
        disc_transfer_sizes_copy = copy.deepcopy(disc_transfer_sizes)
        disc_deletion_sizes_copy = copy.deepcopy(disc_deletion_sizes)
        disc_capacities_copy = copy.deepcopy(disc_capacities)
        scheme = []
        for disc1_name in disc_transfer_sizes:
            for disc2_name in disc_transfer_sizes[disc1_name]:
                logger.debug('Considering discs disc1:%s and disc2:%s', disc1_name, disc2_name)

                # Prioritize deletions
                deletion_1 = disc_deletion_sizes_copy[disc1_name]
                if deletion_1 > 0:
                    scheme.append(DiscDeletion(disc1_name))
                    disc_deletion_sizes_copy[disc1_name] -= deletion_1
                deletion_2 = disc_deletion_sizes_copy[disc2_name]
                if deletion_2 > 0:
                    scheme.append(DiscDeletion(disc2_name))
                    disc_deletion_sizes_copy[disc2_name] -= deletion_2
                logger.debug('Deletions: deletion1:%d, deletion2:%d', deletion_1, deletion_2)

                # Prioritize intra disc transfers
                transfer_11 = disc_transfer_sizes_copy[disc1_name][disc1_name]
                if transfer_11 > 0:
                    self_transfer_1 = InterDiscTransfer(disc1_name, disc1_name, transfer_11, True)
                    scheme.append(self_transfer_1)
                    disc_transfer_sizes_copy[disc1_name][disc1_name] -= transfer_11
                transfer_22 = disc_transfer_sizes_copy[disc2_name][disc2_name]
                if transfer_22 > 0:
                    self_transfer_2 = InterDiscTransfer(disc2_name, disc2_name, transfer_22, True)
                    scheme.append(self_transfer_2)
                    disc_transfer_sizes_copy[disc2_name][disc2_name] -= transfer_22
                logger.debug('Intra disc transfers: transfer_11:%d, transfer_22:%d', transfer_11, transfer_22)

                # Inter disc transfers
                max_transfer_12 = disc_transfer_sizes_copy[disc1_name][disc2_name]
                max_transfer_21 = disc_transfer_sizes_copy[disc2_name][disc1_name]
                capacity_1 = (None if disc_capacities_copy[disc1_name] is None else disc_capacities_copy[disc1_name])
                capacity_2 = (None if disc_capacities_copy[disc2_name] is None else disc_capacities_copy[disc2_name])
                final_transfer_12 = max_transfer_12 if capacity_2 is None else min(max_transfer_12, capacity_2)
                final_transfer_21 = max_transfer_21 if capacity_1 is None else min(max_transfer_21, capacity_1)
                if final_transfer_12 > 0:
                    disc_transfer_sizes_copy[disc1_name][disc2_name] -= final_transfer_12
                    inter_disc_scheme = InterDiscTransfer(disc1_name, disc2_name, final_transfer_12,
                                                          disc_transfer_sizes_copy[disc1_name][disc2_name] <= 0)
                    scheme.append(inter_disc_scheme)
                if final_transfer_21 > 0:
                    disc_transfer_sizes_copy[disc2_name][disc1_name] -= final_transfer_21
                    inter_disc_scheme = InterDiscTransfer(disc2_name, disc1_name, final_transfer_21,
                                                          disc_transfer_sizes_copy[disc2_name][disc1_name] <= 0)
                    scheme.append(inter_disc_scheme)
                if disc_capacities_copy[disc1_name] is not None:
                    disc_capacities_copy[disc1_name] += final_transfer_12 - final_transfer_21
                if disc_capacities_copy[disc2_name] is not None:
                    disc_capacities_copy[disc2_name] += final_transfer_21 - final_transfer_12
                logger.debug('Inter disc transfers: final_transfer_12:%d, final_transfer_21:%d', final_transfer_12,
                             final_transfer_21)

                logger.debug('Current scheme length: %d', len(scheme))
                if _completed(disc_transfer_sizes_copy, disc_deletion_sizes_copy):
                    logger.debug('End scheme gen. Final scheme size:%d', len(scheme))
                    return scheme

    # Generate the scheme with the least inter disc transfers by brute force
    def _gen_scheme_brute(disc_transfer_sizes, disc_deletion_sizes, disc_capacities, depth=0):
        logger.info('Depth: %d', depth)
        logger.debug('Begin scheme gen loop')

        # Are all deletions and transfers completed
        def _completed():
            transfer_left = sum([sum(disc_transfer_sizes[disc1_name][disc2]
                                     for disc2 in disc_transfer_sizes[disc1_name]) for disc1_name in
                                 disc_transfer_sizes])
            deletion_left = sum([deletions for disc, deletions in disc_deletion_sizes.items()])
            completed = transfer_left <= 0 and deletion_left <= 0
            logger.debug('Evaluated completion: transfer_left:%d, deletion_left:%d, completed: %s', transfer_left,
                         deletion_left, completed)
            return completed

        # Compare 2 schemes for the least number of inter disc transfers
        def _better_scheme(scheme1, scheme2):
            if scheme1 is None:
                return scheme2
            if scheme2 is None:
                return []
            better = None
            better_transfers = None
            for scheme in [scheme1, scheme2]:
                num_inter_transfers = len(
                    [idt for idt in scheme if isinstance(idt, InterDiscTransfer) and idt.disc1 != idt.disc2])
                if better is None or num_inter_transfers > better_transfers:
                    better = scheme
                    better_transfers = num_inter_transfers
            logger.debug('Schemes compared: Scheme1:Size(%d) and Scheme2:Size(%d), Better:%s', len(scheme1),
                         len(scheme2), 'Scheme1' if better is scheme1 else 'Scheme2')
            return better

        best_scheme = []
        if _completed():
            return best_scheme

        for disc1_name in disc_transfer_sizes:
            for disc2_name in disc_transfer_sizes[disc1_name]:
                logger.debug('Considering discs disc1:%s and disc2:%s', disc1_name, disc2_name)
                current_scheme = []

                # Clone data structures
                disc_transfer_sizes_copy = copy.deepcopy(disc_transfer_sizes)
                disc_deletion_sizes_copy = copy.deepcopy(disc_deletion_sizes)
                disc_capacities_copy = copy.deepcopy(disc_capacities)

                # Prioritize deletions
                deletion_1 = disc_deletion_sizes_copy[disc1_name]
                if deletion_1 > 0:
                    current_scheme.append(DiscDeletion(disc1_name))
                    disc_deletion_sizes_copy[disc1_name] -= deletion_1
                deletion_2 = disc_deletion_sizes_copy[disc2_name]
                if deletion_2 > 0:
                    current_scheme.append(DiscDeletion(disc2_name))
                    disc_deletion_sizes_copy[disc2_name] -= deletion_2
                logger.debug('Deletions: deletion1:%d, deletion2:%d', deletion_1, deletion_2)

                # Prioritize intra disc transfers
                transfer_11 = disc_transfer_sizes_copy[disc1_name][disc1_name]
                if transfer_11 > 0:
                    self_transfer_1 = InterDiscTransfer(disc1_name, disc1_name, transfer_11, True)
                    current_scheme.append(self_transfer_1)
                    disc_transfer_sizes_copy[disc1_name][disc1_name] -= transfer_11
                transfer_22 = disc_transfer_sizes_copy[disc2_name][disc2_name]
                if transfer_22 > 0:
                    self_transfer_2 = InterDiscTransfer(disc2_name, disc2_name, transfer_22, True)
                    current_scheme.append(self_transfer_2)
                    disc_transfer_sizes_copy[disc2_name][disc2_name] -= transfer_22
                logger.debug('Intra disc transfers: transfer_11:%d, transfer_22:%d', transfer_11, transfer_22)

                # Inter disc transfers
                max_transfer_12 = disc_transfer_sizes_copy[disc1_name][disc2_name]
                max_transfer_21 = disc_transfer_sizes_copy[disc2_name][disc1_name]
                max_capacity_1 = (None if disc_capacities_copy[disc1_name] is None else
                                  disc_capacities_copy[disc1_name] + max_transfer_12)
                max_capacity_2 = (None if disc_capacities_copy[disc2_name] is None else
                                  disc_capacities_copy[disc2_name] + max_transfer_21)
                final_transfer_12 = max_transfer_12 if max_capacity_2 is None else min(max_transfer_12, max_capacity_2)
                final_transfer_21 = max_transfer_21 if max_capacity_1 is None else min(max_transfer_21, max_capacity_1)
                if final_transfer_12 > 0:
                    disc_transfer_sizes_copy[disc1_name][disc2_name] -= final_transfer_12
                    inter_disc_scheme = InterDiscTransfer(disc1_name, disc2_name, final_transfer_12,
                                                          disc_transfer_sizes_copy[disc1_name][disc2_name] <= 0)
                    current_scheme.append(inter_disc_scheme)
                if final_transfer_21 > 0:
                    disc_transfer_sizes_copy[disc2_name][disc1_name] -= final_transfer_21
                    inter_disc_scheme = InterDiscTransfer(disc2_name, disc1_name, final_transfer_21,
                                                          disc_transfer_sizes_copy[disc2_name][disc1_name] <= 0)
                    current_scheme.append(inter_disc_scheme)
                if disc_capacities_copy[disc1_name] is not None:
                    disc_capacities_copy[disc1_name] += final_transfer_12 - final_transfer_21
                if disc_capacities_copy[disc2_name] is not None:
                    disc_capacities_copy[disc2_name] += final_transfer_21 - final_transfer_12
                logger.debug('Inter disc transfers: final_transfer_12:%d, final_transfer_21:%d', final_transfer_12,
                             final_transfer_21)

                logger.debug('Current scheme length: %d', len(current_scheme))
                if len(current_scheme) > 0:
                    new_scheme = current_scheme + _gen_scheme(disc_transfer_sizes_copy, disc_deletion_sizes_copy,
                                                              disc_capacities_copy, depth + 1)
                    best_scheme = new_scheme if len(best_scheme) == 0 else _better_scheme(best_scheme, new_scheme)

        logger.debug('End scheme gen loop. Best scheme size:%d', len(best_scheme))
        return best_scheme

    # Execute scheme gen loops
    final_scheme = _gen_scheme(disc_transfer_sizes, disc_deletion_sizes, disc_capacities)
    for i, scheme in enumerate(final_scheme):
        logger.debug('Scheme %d. Type: %s. Info: %s', i + 1,
                     'Deletion' if isinstance(scheme, DiscDeletion) else 'Transfer', scheme.__dict__)
    return final_scheme


# Generate optimized order of disc transfers and deletions for save with copy mode
def generate_disc_scheme_for_copy():
    logger.debug('Generating disc scheme for copy')

    discs = core.get_all_discs()
    disc_transfer_sizes = get_disc_transfer_sizes()

    scheme = []
    for x in range(len(discs)):
        for y in range(len(discs)):
            logger.debug('Considering transfer from disc %s to disc %s', discs[x].name, discs[y].name)
            transfer_xy = disc_transfer_sizes[discs[x].name][discs[y].name]
            if transfer_xy > 0:
                scheme.append(InterDiscTransfer(discs[x].name, discs[y].name, transfer_xy, True))
            logger.debug('Transfer size: %d', transfer_xy)

    logger.debug('Final scheme of size %d has been generated', len(scheme))
    for i, sch in enumerate(scheme):
        logger.debug('Scheme %d. Type: Transfer. Info: %s', i + 1, sch.__dict__)
    return scheme


# Generate save status that is used to track save progress (cached)
def generate_save_status():
    global _save_status
    mode = get_save_mode()
    logger.debug('Generating save status for mode %s', mode)

    discs = core.get_all_discs()
    disc_transfers = get_disc_transfers()
    # Disc deletions is ignored for mode "copy"
    disc_deletions = {disc.name: [] for disc in discs} if mode == 'copy' else get_disc_deletions()

    # Generate scheme by mode
    if mode == 'move':
        scheme = generate_disc_scheme_for_move()
    else:
        scheme = generate_disc_scheme_for_copy()

    _save_status = {
        'transfers': disc_transfers,
        'deletions': disc_deletions,
        'scheme': scheme,
        'cleanup': mode == 'copy',  # Cleanup is marked completed for mode "copy",
        'mode': mode
    }

    logger.debug('Save status generated successfully: %s', _save_status)
    return _save_status


def load_save_status():
    global _save_status, _disc_deletions, _disc_transfers
    save_file_path = compute_save_file_path()
    _save_status = core.read_meta_data(save_file_path)
    _, _disc_deletions, _, _, _disc_transfers = [_save_status[key] for key in sorted(_save_status)]
    return _save_status


def save_save_status():
    save_file_path = compute_save_file_path()
    core.write_meta_data(_save_status, save_file_path, delay_save_meta=True)


# Delete an actual file and save the changes
def do_del_file(del_status):
    logger.debug('Deleting file: %s', del_status.__dict__)
    # Delete file
    os.unlink(del_status.actual_path)
    # Update and save save status
    del_status.completed = True
    save_save_status()
    # Remove stats
    core.del_file_stats(del_status.actual_path)
    logger.debug('Deleted file: %s', del_status.__dict__)


# Save a virtual directory and save the changes. Does not delete actual directories
def do_save_dir(transfer_status):
    mode = get_save_mode()
    logger.debug('Saving directory in mode %s: info:%s', mode, transfer_status.__dict__)

    # Get destination
    dest_path = core.convert_virtual_to_actual_using_save_map(transfer_status.virtual_path)

    # Create directory
    try:
        os.makedirs(dest_path)
    except OSError as ex:
        if ex.errno == errno.EEXIST and os.path.isdir(dest_path):
            logger.debug('Directory %s already existes. Ignoring error', dest_path)
        else:
            raise

    # Update and save save status
    transfer_status.completed = True
    save_save_status()

    logger.debug('Saved directory successfully: %s', transfer_status.__dict__)


# Save or copy a virtual file and save the changes
def do_save_file(transfer_status, scheme):
    mode = get_save_mode()
    logger.debug('Saving file in mode %s. Info: transfer_status:%s, scheme:%s', mode, transfer_status.__dict__,
                 scheme.__dict__)

    # Get source and destination
    dest_path = core.convert_virtual_to_actual_using_save_map(transfer_status.virtual_path)
    file_stats = core.get_file_stats_for_symlink(transfer_status.virtual_path)
    logger.debug('Source: %s, Destination: %s', file_stats.actual_path, dest_path)
    if dest_path == file_stats.actual_path:
        logger.debug('Sorce and destination are same')
        transfer_status.completed = True
        scheme.transfer_completed += file_stats.size
        save_save_status()
        return

    # Check size restrictions
    capacity_left = scheme.transfer_size - scheme.transfer_completed
    if not scheme.last and capacity_left < file_stats.size:
        logger.debug('Scheme size available (%d) is not sufficient(%d). Completing scheme',
                     capacity_left, file_stats.size)
        scheme.completed = True
        save_save_status()
        return

    # Create destination directory if ot does not exist
    dest_dir = os.path.dirname(dest_path)
    logger.debug('Trying to create destination directory %s', dest_dir)
    try:
        os.makedirs(dest_dir)
    except OSError as ex:
        if ex.errno == errno.EEXIST and os.path.isdir(dest_dir):
            logger.debug('Destination directory %s already exists', dest_dir)
        else:
            raise

    # Move or copy file and update a2v map according to mode
    # TODO: In case of move within same disc, do not  copy even if a2vmap has pending files because the generated scheme does not
    # consider that a file can be copied to multiple places and such a scenario might cause the disc to run out of memory
    a2v_map = core.get_actual_to_virtual_map()
    move_file = mode == 'move' and file_stats.actual_path in a2v_map and len(a2v_map[file_stats.actual_path]) == 1
    logger.debug('Flag move_file:%s', move_file)
    logger.debug('TEMP DEBUG: Saving file in mode %s. Info: transfer_status:%s, scheme:%s', mode,
                 transfer_status.__dict__,
                 scheme.__dict__)
    logger.debug('TEMP DEBUG: FILE STATS : %s', file_stats.__dict__)
    if move_file:
        if os.path.islink(file_stats.actual_path):
            dest_link = os.readlink(file_stats.actual_path)
            core.create_symlink(dest_link, dest_path)
            core.del_symlink(file_stats.actual_path)
        else:
            shutil.move(file_stats.actual_path, dest_path)
        a2v_map.pop(file_stats.actual_path)
    else:
        if os.path.islink(file_stats.actual_path):
            dest_link = os.readlink(file_stats.actual_path)
            core.create_symlink(dest_link, dest_path)
        else:
            shutil.copy2(file_stats.actual_path, dest_path)
        if mode == 'move':
            if len(a2v_map[file_stats.actual_path]) > 1:
                a2v_map[file_stats.actual_path].pop(a2v_map[file_stats.actual_path].index(transfer_status.virtual_path))
            else:
                a2v_map.pop(file_stats.actual_path)
    a2v_map[dest_path] = [transfer_status.virtual_path]

    # Update and save save status
    transfer_status.completed = True
    scheme.transfer_completed += file_stats.size
    save_save_status()

    # Update link if mode is 'move'
    if mode == 'move':
        core.del_symlink(transfer_status.virtual_path)
        core.create_symlink(dest_path, transfer_status.virtual_path)

    # Delete stats if actual file is moved
    if move_file:
        core.del_file_stats(file_stats.actual_path)

    # Add dest file stats
    file_stats = copy.deepcopy(file_stats)
    file_stats.actual_path = dest_path
    core.add_file_stats(file_stats)

    logger.debug('Saved file  successfully: %s', transfer_status.__dict__)


# mega temp remove start\

# _v2a = None
# def get_v2a(a2v):
#     global _v2a
#     if _v2a is not None:
#         return _v2a
#     v2a = {}
#     for full_actual_path_old in a2v.keys():
#         for full_virtual_path in a2v[full_actual_path_old]:
#             v2a[full_virtual_path] = full_actual_path_old
#     _v2a = v2a
#     return v2a
#
# import sys
# def action(code):
#     if code == 1:
#         raise core.VfsException('Exit Action')
#     elif code == 2:
#         sys.exit(1)
#
# _count = 0
# # Save or copy a virtual file and save the changes
# def do_save_file_mega_temp(transfer_status, scheme):
#     global _count
#     _count += 1
#     if _count % 50 == 0:
#         print 'Saving file %d' % _count
#
#     mode = get_save_mode()
#     logger.debug('Saving file in mode %s. Info: transfer_status:%s, scheme:%s', mode, transfer_status.__dict__,
#                  scheme.__dict__)
#
#     a2v_map = core.get_actual_to_virtual_map()
#     v2a_map = get_v2a(a2v_map)
#
#     # Get source and destination
#     dest_path = core.convert_virtual_to_actual_using_save_map(transfer_status.virtual_path)
#     file_stats = core.get_file_stats_for_symlink(transfer_status.virtual_path)
#     if file_stats is not None:
#         print 'Unhandled. Put break point'
#         x = 1
#         if x == 0:
#             return
#         action(x)
#     if file_stats is None and transfer_status.virtual_path in v2a_map:
#         file_stats = core.get_file_stats_for_actual_path(v2a_map[transfer_status.virtual_path])
#     if file_stats is None:
#         print 'UNHANDLED: Put break point'
#         x = 1
#         if x == 0:
#             return
#         action(x)
#
#     logger.debug('Source: %s, Destination: %s', file_stats.actual_path, dest_path)
#     if dest_path == file_stats.actual_path:
#         logger.debug('Sorce and destination are same')
#         transfer_status.completed = True
#         scheme.transfer_completed += file_stats.size
#         save_save_status()
#         return
#
#     # Check size restrictions
#     capacity_left = scheme.transfer_size - scheme.transfer_completed
#     if not scheme.last and capacity_left < file_stats.size:
#         logger.debug('Scheme size available (%d) is not sufficient(%d). Completing scheme',
#                      capacity_left, file_stats.size)
#         scheme.completed = True
#         save_save_status()
#         return
#
#     # Create destination directory if ot does not exist
#     dest_dir = os.path.dirname(dest_path)
#     logger.debug('Trying to create destination directory %s', dest_dir)
#     try:
#         os.makedirs(dest_dir)
#     except OSError as ex:
#         if ex.errno == errno.EEXIST and os.path.isdir(dest_dir):
#             logger.debug('Destination directory %s already exists', dest_dir)
#         else:
#             raise
#
#
#     move_file = mode == 'move' and file_stats.actual_path in a2v_map and len(a2v_map[file_stats.actual_path]) == 1
#     logger.debug('Flag move_file:%s', move_file)
#     logger.debug('TEMP DEBUG: Saving file in mode %s. Info: transfer_status:%s, scheme:%s', mode,
#                  transfer_status.__dict__,
#                  scheme.__dict__)
#     logger.debug('TEMP DEBUG: FILE STATS : %s', file_stats.__dict__)
#     if move_file:
#         x = 0
#         if x > 0:
#             if os.path.islink(file_stats.actual_path):
#                 dest_link = os.readlink(file_stats.actual_path)
#                 core.create_symlink(dest_link, dest_path)
#                 core.del_symlink(file_stats.actual_path)
#             else:
#                 shutil.move(file_stats.actual_path, dest_path)
#         a2v_map.pop(file_stats.actual_path)
#     else:
#         x = 0
#         if x > 0:
#             if os.path.islink(file_stats.actual_path):
#                 dest_link = os.readlink(file_stats.actual_path)
#                 core.create_symlink(dest_link, dest_path)
#             else:
#                 shutil.copy2(file_stats.actual_path, dest_path)
#         if mode == 'move':
#             if len(a2v_map[file_stats.actual_path]) > 1:
#                 a2v_map[file_stats.actual_path].pop(a2v_map[file_stats.actual_path].index(transfer_status.virtual_path))
#             else:
#                 a2v_map.pop(file_stats.actual_path)
#     a2v_map[dest_path] = [transfer_status.virtual_path]
#
#     # Update and save save status
#     transfer_status.completed = True
#     scheme.transfer_completed += file_stats.size
#     save_save_status()
#
#     # Update link if mode is 'move'
#     if mode == 'move':
#         x = 0
#         if x > 0:
#             core.del_symlink(transfer_status.virtual_path)
#             core.create_symlink(dest_path, transfer_status.virtual_path)
#
#     # Delete stats if actual file is moved
#     if move_file:
#         core.del_file_stats(file_stats.actual_path)
#
#     # Add dest file stats
#     file_stats = copy.deepcopy(file_stats)
#     file_stats.actual_path = dest_path
#     core.add_file_stats(file_stats)
#
#     logger.debug('Saved file  successfully: %s', transfer_status.__dict__)

# mega temp remove end

# Check that a disc is connected. Prompt user to connect and continue
def check_disc(disc_name, prompt_connect=True, loop_forever=True):
    disc = core.get_disc_by_name(disc_name)
    connected = os.path.isdir(disc.disc_base)
    logger.debug('Checked disc %s. Connected:%s', disc_name, connected)
    if connected:
        return True
    elif not prompt_connect:
        return False
    logger.info('Please connect disc "%s" at path "%s" and then press any "Enter" to continue', disc.name,
                disc.disc_base)
    inp = raw_input()
    logger.debug('User input recd: %s', inp)
    if inp == 'quit':
        return False
    return check_disc(disc_name, prompt_connect, True) if loop_forever else os.path.isdir(disc.disc_base)


# Remove unregistered and empty actual directories after saving from collections
def do_clean_up():
    logger.debug('Cleaning up')

    dirs_to_del = []
    dirs_to_del_map = {}

    # Evaluate whether a directory can be deleted
    # It must not contain any files in the tree
    # It must not have a corresponding virtual directory
    def _can_del_dir(dir_path):
        # Check if corresponding virtual directory exists
        virtual_dir_path = core.convert_actual_to_virtual_using_save_map(dir_path)
        can_del = virtual_dir_path is None or not os.path.isdir(virtual_dir_path)
        if not can_del:
            return can_del
        # Check for files and sub dirs
        elems = os.listdir(dir_path)
        for elem in elems:
            elem_path = os.path.join(dir_path, elem)
            if os.path.isdir(elem_path):
                if elem_path not in dirs_to_del_map:
                    can_del = False
                    break
                    # if not _can_del_dir(elem_path):
                    #     logger.debug("Found sub directory %s that cannot be deleted", elem_path)
                    #     can_del = False
                    #     break
            else:
                can_del = False
                break
        return can_del

    # Identify extra directories
    cols = core.get_all_collections()
    for col in cols:
        logger.debug('Identifying dirs to delete in %s', col.actual_base)
        disc = core.get_disc_by_path(col.actual_base)
        if not check_disc(disc.name):
            raise core.VfsException('Failed to cleanup. Disc %s is not connected.' % disc.name)
        for root, dirs, files in os.walk(col.actual_base, topdown=False):
            if root != col.actual_base and _can_del_dir(root):
                dirs_to_del.append(root)
                dirs_to_del_map[root] = 1
    logger.debug('Num dirs to delete: %d', len(dirs_to_del))

    # Delete directories
    for dir in dirs_to_del:
        disc = core.get_disc_by_path(dir)
        logger.debug('Trying to delete directory %s from disc %s', dir, disc.name)
        if not check_disc(disc.name):
            raise core.VfsException('Failed to delete directory %s. Disc %s is not connected. Connect disc and resume.',
                                    dir, disc.name)
        os.rmdir(dir)

    logger.debug('Cleaning up complete')


# CLI target

# Global
_exit_save = False
_print_options = False
_print_progress = False
_print_schemes = False


# Print the save options
def print_save_options():
    logger.info('Following options are available: (Commands will be executed after the current transfer)')
    logger.info('Type "options" for help')
    logger.info('Type "progress" to show the progress of the current step')
    logger.info('Type "schemes" to show the details of all schemes')
    logger.info('Type "exit" to save and exit')


def print_scheme_progress(scheme):
    is_del = isinstance(scheme, DiscDeletion)
    if is_del:
        disc_deletions = get_disc_deletions()
        deletions = disc_deletions[scheme.disc]
        completed = filter(lambda d: d.completed, deletions)
        logger.info('Deleting files from disc %s. Completed: %s of %s', scheme.disc, len(completed), len(deletions))
    else:  # transfer
        disc_transfers = get_disc_transfers()
        transfers = disc_transfers[scheme.disc1][scheme.disc2]
        completed = filter(lambda d: d.completed, transfers)
        logger.info('Transferring files from disc %s to disc %s. Completed: %s of %s',
                    scheme.disc1, scheme.disc2, len(completed), len(transfers))


def print_full_scheme():
    if _save_status is not None:
        print 'Details of all Schemes:'
        for i, scheme in enumerate(_save_status['scheme']):
            is_del = isinstance(scheme, DiscDeletion)
            if is_del:
                print 'Scheme No:%d\tCompleted:%s\tDelete from disc %s' % (i + 1, scheme.completed, scheme.disc)
            else:
                print 'Scheme No:%d\tCompleted:%s\tTransfer from disc %s to disc %s' % (
                    i + 1, scheme.completed, scheme.disc1, scheme.disc2)


def interruptable_save_wrapper(scheme, target, *args):
    global _exit_save, _print_options, _print_progress, _print_schemes
    if _exit_save:
        raise core.VfsException('Save has been paused by the user')
    elif _print_options:
        print_save_options()
        _print_options = False
    elif _print_progress:
        print_scheme_progress(scheme)
        _print_progress = False
    elif _print_schemes:
        print_full_scheme()
        _print_schemes = False
    target(*args)


# To be run in a separate thread for getting user
def start_user_input_thread():
    def target():
        global _exit_save, _print_options, _print_progress, _print_schemes
        _print_options = True
        while True:
            time.sleep(1)
            inp = raw_input()
            if inp == 'exit':
                logger.debug('User typed %s', inp)
                _exit_save = True
            elif inp == 'options':
                logger.debug('User typed %s', inp)
                _print_options = True
            elif inp == 'progress':
                logger.debug('User typed %s', inp)
                _print_progress = True
            elif inp == 'schemes':
                logger.debug('User typed %s', inp)
                _print_schemes = True

    logger.debug('Enabling user input thread for save options')
    thread = threading.Thread(target=target)
    thread.setDaemon(True)
    thread.start()


# CLI TARGET: Save VFS using save map and discs info
def save(restart=False, del_save_file=False):
    logger.debug('Save arguments: restart:%s, del_save_file:%s', restart, del_save_file)

    # Check or generate save status
    save_file_path = compute_save_file_path()
    if restart or not os.path.isfile(save_file_path):
        logger.info('Performing validations before saving')
        # Validations
        validate_filters()
        validate_exhaustive_discs()
        validate_exhaustive_save_maps()
        validate_space_availability()
        logger.info('Evaluating save scheme')
        save_status = generate_save_status()
        save_save_status()
    else:
        logger.info('Loading existing save scheme')
        save_status = load_save_status()

    cleanup_done, deletions, mode, schemes, transfers = [save_status[key] for key in sorted(save_status)]
    logger.debug('Save status is ready')
    logger.debug('cleanup_done: %s', cleanup_done)
    logger.debug('mode: %s', mode)
    logger.debug('deletions: %s', deletions)
    logger.debug('schemes: %s', schemes)
    logger.debug('transfers: %s', transfers)
    set_save_mode(mode)

    # Save each scheme
    logger.info('Performing disc transfers and deletions')
    for scheme_index, scheme in enumerate(schemes):
        logger.debug('Current scheme: %s', scheme)
        if scheme.completed:
            logger.debug('Scheme is completed')
            continue
        logger.info('Executing part %d of %d of the save scheme', scheme_index + 1, len(schemes))
        is_deletion = isinstance(scheme, DiscDeletion)
        if is_deletion:
            logger.info('Deleting files from disc %s', scheme.disc)
            if not check_disc(scheme.disc):
                raise core.VfsException('Disc %s is not available' % scheme.disc)
            for del_status in deletions[scheme.disc]:
                logger.debug('Deletion status: %s', del_status)
                if del_status.completed:
                    continue
                if del_status.completed:
                    logger.debug('File %s has already been deleted', del_status.actual_path)
                    continue
                interruptable_save_wrapper(scheme, do_del_file, del_status)
        else:  # transfer
            logger.info('Transferring files from disc %s to disc %s', scheme.disc1, scheme.disc2)
            if not check_disc(scheme.disc1) or not check_disc(scheme.disc2):
                raise core.VfsException('Discs %s or %s are not available' % (scheme.disc1, scheme.disc2))
            for transfer_status in transfers[scheme.disc1][scheme.disc2]:
                logger.debug('Transfer status: %s', transfer_status)
                if transfer_status.completed:
                    continue
                if scheme.completed:
                    logger.debug('File %s has already been transferred', transfer_status.virtual_path)
                    break
                is_dir = os.path.isdir(transfer_status.virtual_path)
                logger.debug('Dir transfer: %s', is_dir)
                if is_dir:
                    interruptable_save_wrapper(scheme, do_save_dir, transfer_status)
                else:
                    interruptable_save_wrapper(scheme, do_save_file, transfer_status, scheme)
        scheme.completed = True
        save_save_status()
    logger.info('Disc transfers and deletions completed successfully')

    # Perform cleanup
    if not cleanup_done:
        logger.info('Cleaning up discs')
        do_clean_up()
        save_status['cleanup'] = True
        save_save_status()
        logger.info('Disc cleanup complete')

    # Delete save file
    if del_save_file:
        os.unlink(save_file_path)
        logger.info('Deleted save progress file')

    logger.info('Save complete')
