# The core provides access to the VFS data and meta data
# Other utilities, that are used across, are also defined here

import copy
import errno
import inspect
import os
import pickle
import shutil
import tempfile
import time
import uuid

import config
from log_utils import logger


# VFS Exception Class
class VfsException(Exception):
    pass


# Base class for printable objects
class PrintableObject(object):
    def __repr__(self):
        return str(self.__dict__)


# Dictionary utils


# Fetch a dictionary value for a key with the options of
#   Validating the type of the value
#   Applying a custom validation to the value
#   Returning a default value if key is not present
# Raises VfsException for validation failures
def fetch_valid_dict_value(dict_, key, default=None, type_=None, validation=None):
    if key not in dict_:
        return default
    value = dict_[key]
    if type_ is not None:
        try:
            assert type(value) is type_
        except AssertionError:
            raise VfsException('Invalid value for key "%s": "%s". Expected type "%s", got type "%s"' % (key, value,
                                                                                                        type(key),
                                                                                                        type(value)))
    if validation is not None:
        if not validation(value):
            raise VfsException('Invalid value for key "%s": "%s". Validation failed' % (key, value))
    return value


# Directory utils


# Create a directory
# Elements of 'path' are joined to form the final path
# Options are:
#   'ignore_existing': Default False
#   'create_intermediate': Default False
def create_dir(*path, **opts):
    final_path = os.path.join(*path)
    ignore_existing = fetch_valid_dict_value(opts, 'ignore_existing', False, bool)
    create_intermediate = fetch_valid_dict_value(opts, 'create_intermediate', False, bool)
    mk_dir = os.makedirs if create_intermediate else os.mkdir
    try:
        logger.debug('Trying to create directory %s with params: ignore_existing:%s, create_intermediate:%s',
                     final_path, ignore_existing, create_intermediate)
        mk_dir(final_path)
        logger.debug('Directory %s was successfully created', final_path)
    except OSError:
        logger.debug('Error occurred while creating directory %s', final_path, exc_info=True)
        if not ignore_existing:
            raise


# Delete a directory
# Elements of 'path' are joined to form the final path
# Options are:
#   'del_non_empty': Default False
def del_dir(*path, **opts):
    final_path = os.path.join(*path)
    del_non_empty = fetch_valid_dict_value(opts, 'del_non_empty', False, bool)
    logger.debug('Deleting directory %s with params: del_non_empty:%s', final_path, del_non_empty)
    if del_non_empty:
        shutil.rmtree(final_path, False)
    else:
        os.rmdir(final_path)
    logger.debug('Directory %s was deleted successfully', final_path)


# Is dir2 a parent of dir1
def is_parent_dir(dir1, dir2):
    abs_dir1 = os.path.abspath(dir1)
    abs_dir2 = os.path.abspath(dir2)
    is_parent = False
    while abs_dir1 != '/':
        if abs_dir1 == abs_dir2:
            is_parent = True
            break
        abs_dir1 = os.path.dirname(abs_dir1)
    return is_parent


# Meta data utils


# Read meta data from a file and unpickle into a class
# Elements of 'path' are joined to form the final path
# Options are:VFS_HOME_ENV_VAR
#   'valid_class': Class to validate the unpickled meta data against
# Raises VfsException for validation failures
def read_meta_data(*path, **opts):
    final_path = os.path.join(*path)
    valid_class = fetch_valid_dict_value(opts, 'valid_class', None, None, lambda cls: inspect.isclass(cls))
    logger.debug('Reading meta data file %s with params: valid_class:%s', final_path, valid_class)
    with open(final_path, 'r') as mfile:
        meta_data = pickle.load(mfile)
    if valid_class is not None and not isinstance(meta_data, valid_class):
        raise VfsException('Pickled meta data is not an instance of the class: %s' % valid_class)
    logger.debug('Meta data file %s was successfully read', final_path)
    return meta_data


_pending_meta_writes = {}


# Pickle an object and store at the specified path
# Elements of 'path' are joined to form the final path
# Options are:
#   'valid_class': Class to validate the meta data against
#   'delay_save_meta': Override the delayed write property in config
# Raises VfsException in case of failures
def write_meta_data(meta_data, *path, **opts):
    final_path = os.path.join(*path)
    valid_class = fetch_valid_dict_value(opts, 'valid_class', None, None, lambda cls: inspect.isclass(cls))
    delay_save_meta = fetch_valid_dict_value(opts, 'delay_save_meta', False, bool)
    logger.debug('Writing meta data file %s with params: valid_class:%s. Delay Save Meta = %s', final_path, valid_class,
                 delay_save_meta)
    if valid_class is not None and not isinstance(meta_data, valid_class):
        raise VfsException('Meta data is not an instance of the class: %s' % valid_class)
    if delay_save_meta:
        logger.debug('Adding to queue')
        _pending_meta_writes[final_path] = (meta_data, opts)
    else:
        with open(final_path, 'w') as mfile:
            pickle.dump(meta_data, mfile)
        logger.debug('Meta data file %s was successfully written', final_path)


# Pending meta writes
def do_pending_meta_writes():
    logger.debug('Writing to meta data files before quitting...')
    for file_path in _pending_meta_writes.keys():
        meta_data, opts = _pending_meta_writes.pop(file_path)
        opts['delay_save_meta'] = False
        write_meta_data(meta_data, file_path, **opts)


# Symbolic link utils

# Create a symbolic link from 'src' to 'dest'
# Optionally override existing file at 'dest' with 'override':True'
# Raises VfsException in case of validation failures
def create_symlink(src, dest, override=False):
    abs_src_path = os.path.abspath(src)
    abs_dest_path = os.path.abspath(dest)
    logger.debug('Trying to create symlink from path %s to path %s with params override:%s',
                 abs_src_path, abs_dest_path, override)
    if os.path.islink(abs_dest_path):
        if override:
            logger.debug('Symlink already exists. It will be overriden')
            os.unlink(abs_dest_path)
        else:
            raise VfsException("Destination path %s already exists" % abs_dest_path)
    os.symlink(abs_src_path, abs_dest_path)
    logger.debug('Created symlink successfully')


# Delete the symbolic link at 'path'
# Optionally avoid throwing an error if the file is already deleted with 'ignore_already_del':True
# Raises VfsException in case of failures
def del_symlink(path, ignore_already_del=False):
    logger.debug('Trying to delete symlink from path %s with params ignore_already_del:%s',
                 path, ignore_already_del)
    if os.path.islink(path):
        os.unlink(path)
        logger.debug('Deleted symlink successfully')
    elif not ignore_already_del:
        raise VfsException("Symbolic link does not exist at path %s" % path)
    else:
        logger.debug('Symlink was already deleted')


# Copy a symlink to another location
def copy_symlink(source_path, dest_path):
    logger.debug('Trying to copy symlink from path %s to path %s', source_path, dest_path)
    actual_path = os.readlink(source_path)
    os.symlink(actual_path, dest_path)
    logger.debug('Copied symlink successfully')


# VFS Home utils

# Cached data
_vfs_home = None


# Fetch VFS home directory
# Stored in cache
def get_vfs_home():
    global _vfs_home
    if _vfs_home is not None:
        return _vfs_home
    try:
        path = os.environ[config.VFS_HOME_ENV_VAR]
        logger.debug('VFS home obtained from environment: %s', path)
    except KeyError:
        path = config.VFS_HOME_DEFAULT
        logger.debug('VFS home missing in environment. Default VFS home will be used: %s', path)
    _vfs_home = path
    return path


# Directories to create while setting up VFS home
def _get_vfs_home_setup_dirs():
    vfs_home = get_vfs_home()
    return [
        vfs_home,
        os.path.join(vfs_home, config.VFS_DATA_DIR),
        os.path.join(vfs_home, config.VFS_BACKUP_DIR)
    ]


# Set up VFS home, optionally overriding existing data
def setup_vfs_home(override=False):
    logger.debug('Setting up VFS home with params: override:%s', override)
    vfs_home = get_vfs_home()
    # Delete home
    if os.path.isdir(vfs_home):
        if override:
            shutil.rmtree(vfs_home)
        else:
            raise VfsException('A directory already exists at VFS home path %s' % vfs_home)
    elif os.path.lexists(vfs_home):
        raise VfsException('Path for VFS home %s exists and is not a directory' % vfs_home)

    # Create directories
    for dir_path in _get_vfs_home_setup_dirs():
        os.makedirs(dir_path)

    logger.debug('VFS home has been setup successfully')


# Validate VFS home setup
def validate_vfs_home():
    valid = True
    for dir_path in _get_vfs_home_setup_dirs():
        if not os.path.isdir(dir_path):
            valid = False
            break
    return valid


# VFS utils


# Cached data
_current_vfs = None
_all_vfs = None
_vfs_by_name = None


# Meta data class for a VFS
class VfsMeta(PrintableObject):
    def __init__(self, name, virtual_base):
        self.name = name
        self.virtual_base = virtual_base


# Directories to create for a new VFS
def _get_vfs_setup_dirs(vfs_name):
    path = compute_vfs_path(vfs_name)
    return [
        path,
        os.path.join(path, config.VFS_COLLECTIONS_DIR),
        os.path.join(path, config.VFS_FILTERS_DIR)
    ]


# Compute VFS directory path
def compute_vfs_path(name=None):
    if name is None:
        vfs = get_current_vfs()
        name = vfs.name
        logger.debug('VFS name was not specified. Current VFS %s will be used to compute VFS path', name)
    vfs_home = get_vfs_home()
    vfs_path = os.path.join(vfs_home, config.VFS_DATA_DIR, name)
    logger.debug('VFS path for VFS named %s was computed as %s', name, vfs_path)
    return vfs_path


# Reset VFS cached variables
def _invalidate_vfs_cache():
    logger.debug('Invalidating VFS cache')
    global _all_vfs, _vfs_by_name
    _all_vfs = _vfs_by_name = None


# Set the VFS for the current session (cached)
def set_current_vfs(vfs):
    global _current_vfs
    if not isinstance(vfs, VfsMeta):
        raise VfsException('Invalid VFS')
    _current_vfs = vfs
    logger.debug('VFS %s has been set as current VFS', vfs.name)


# Get the current session's VFS (cached)
def get_current_vfs():
    if _current_vfs is None:
        raise VfsException('Current VFS has not been set')
    return _current_vfs


# Create directories and meta data for a new VFS
# Raises VfsException for validation failures
def setup_vfs(name, path):
    logger.debug('Trying to setup new VFS %s at path %s', name, path)

    # Validations
    if get_vfs_by_name(name) is not None:
        raise VfsException('VFS already exists with name %s' % name)
    vfs_by_path = get_vfs_by_path(path)
    if vfs_by_path is not None:
        raise VfsException('Specified path %s is already part of VFS %s with virtual base at %s' % (
            path, vfs_by_path.name, vfs_by_path.virtual_base))
    if name is None:
        raise VfsException('VFS name cannot be None')
    if type(path) is not str or not os.path.isdir(path):
        raise VfsException('Valid path to an existing directory must be specified')

    # Virtual base
    virtual_base = os.path.abspath(os.path.join(path, name))
    os.mkdir(virtual_base)

    # Create directories
    vfs_path = compute_vfs_path(name)
    for dir_path in _get_vfs_setup_dirs(name):
        os.mkdir(dir_path)

    # Create meta data
    vfs = VfsMeta(name, virtual_base)
    write_meta_data(vfs, vfs_path, config.VFS_META_FILE, valid_class=VfsMeta)

    _invalidate_vfs_cache()
    logger.debug('VFS %s has been setup successfully', name)


# Delete a VFS
def del_vfs(name):
    logger.debug('Deleting VFS %s', name)
    # Delete virtual base
    vfs = get_vfs_by_name(name)
    if vfs is None:
        raise VfsException('VFS with name %s does not exist' % name)
    logger.debug('Deleting virtual directory')
    shutil.rmtree(vfs.virtual_base)

    # Delete VFS
    logger.debug('Deleting meta data')
    vfs_dir_path = compute_vfs_path(name)
    shutil.rmtree(vfs_dir_path)

    _invalidate_vfs_cache()

    logger.debug('Deleted VFS %s successfully', name)


# Get all VFS (cached)
def get_all_vfs():
    global _all_vfs
    if _all_vfs is not None:
        return _all_vfs
    logger.debug('List is not cached. Fetching all VFS')
    vfs_home = get_vfs_home()
    data_dir_path = os.path.join(vfs_home, config.VFS_DATA_DIR)
    dirs = os.listdir(data_dir_path)
    _list = []
    for vfs_dir in dirs:
        vfs = read_meta_data(data_dir_path, vfs_dir, config.VFS_META_FILE, valid_class=VfsMeta)
        _list.append(vfs)
    _all_vfs = _list
    return _list


# Get VFS name to VFS mapping (cached)
def get_all_vfs_by_name():
    global _vfs_by_name
    if _vfs_by_name is not None:
        return _vfs_by_name
    logger.debug('Map is not cachced. Fetching all VFS by name')
    all_vfs = get_all_vfs()
    _vfs_by_name = {vfs.name: vfs for vfs in all_vfs}
    return _vfs_by_name


# Get VFS meta for a VFS by name
def get_vfs_by_name(name):
    all_by_name = get_all_vfs_by_name()
    return all_by_name[name] if name in all_by_name else None


# Get VFS meta for a VFS by specifying any path within the VFS
def get_vfs_by_path(path):
    abs_path = os.path.abspath(path)
    all_vfs = get_all_vfs()
    match = None
    for vfs in all_vfs:
        abs_base = os.path.abspath(vfs.virtual_base)
        if abs_path.startswith(abs_base):
            match = vfs
            break
    return match


# Collection utils


# Cached data
_all_collections = None
_collections_by_name = None
_actual_file_stats = None
_actual_to_virtual_map = None


# Meta data class for a single Collection
class CollectionMeta(PrintableObject):
    def __init__(self, name, actual_base, virtual_base_original):
        self.name = name
        self.actual_base = actual_base
        self.virtual_base_original = virtual_base_original


# Stats of an actual file
class FileStat(PrintableObject):
    def __init__(self, actual_path, ctime, mtime, size=0):
        self.actual_path = actual_path
        self.ctime = ctime
        self.mtime = mtime
        self.size = size


# Stats of an actual directory
class DirStat(PrintableObject):
    def __init__(self, actual_path):
        self.actual_path = actual_path


# Compute collection directory path
def compute_collection_path(col_name):
    col_dir_path = os.path.join(compute_vfs_path(), config.VFS_COLLECTIONS_DIR, col_name)
    logger.debug('Collection directory path for collection %s has been computed as %s', col_name, col_dir_path)
    return col_dir_path


# Reset VFS cached variables
def _invalidate_collections_cache(skip_stats=False):
    logger.debug('Invalidating collections cache (skip_stats:%s)', skip_stats)
    global _all_collections, _collections_by_name, _actual_file_stats, _actual_to_virtual_map
    _all_collections = None
    _collections_by_name = None
    if not skip_stats:
        _actual_file_stats = None
        _actual_to_virtual_map = None


# Add a new collection to a VFS
def setup_collection(col_name, col_base):
    vfs = get_current_vfs()
    logger.debug('Trying to setup new collection %s at path %s in VFS %s', col_name, col_base, vfs.name)

    # Validations
    if get_collection_by_name(col_name) is not None:
        raise VfsException('Collection with name %s already exists in VFS %s' % (col_name, vfs.name))
    col_by_path = get_collection_by_path(col_base)
    if col_by_path is not None:
        raise VfsException(
            'New collection %s with base path %s is already part of another collection %s with base at %s' % (
                col_name, col_base, col_by_path.name, col_by_path.actual_base))
    if col_name is None:
        raise VfsException('VFS name cannot be None')
    if type(col_base) is not str or not os.path.isdir(col_base):
        raise VfsException('Actual path %s does not correspond to an existing directory')

    # Create meta data
    col_dir_path = compute_collection_path(col_name)
    os.mkdir(col_dir_path)
    vfs = get_vfs_by_name(vfs.name)
    col_virtual_base = os.path.join(vfs.virtual_base, col_name)
    col = CollectionMeta(col_name, os.path.abspath(col_base), col_virtual_base)
    write_meta_data(col, col_dir_path, config.COLLECTION_META_FILE, valid_class=CollectionMeta)

    # Create virtual dirs, symlinks and cache actual data
    cache_dict = {}
    for root, dirs, files in os.walk(col_base):
        # Create directory
        root_rel_path = os.path.relpath(root, col_base)
        virtual_root_path = os.path.relpath(os.path.join(col_virtual_base, root_rel_path))
        os.mkdir(virtual_root_path)

        for file_ in files:
            # Create symlink
            actual_file_path = os.path.abspath(os.path.join(root, file_))
            symlink_path = os.path.join(virtual_root_path, file_)
            if os.path.islink(actual_file_path):
                logger.debug('Symlink identified: %s', actual_file_path)
                copy_symlink(actual_file_path, symlink_path)
            else:
                create_symlink(actual_file_path, symlink_path)
            # Save file stat
            raw_stat = os.lstat(actual_file_path)
            file_stat = FileStat(actual_file_path, raw_stat.st_ctime, raw_stat.st_mtime, raw_stat.st_size)
            cache_dict[actual_file_path] = file_stat
            logger.debug('Added actual file %s of size %d Bytes', actual_file_path, file_stat.size)

    # Save stats
    col_stats_meta_path = os.path.join(col_dir_path, config.COLLECTION_STATS_FILE)
    write_meta_data(cache_dict, col_stats_meta_path)

    _invalidate_collections_cache(skip_stats=True)

    logger.debug('Collection %s has ben successfully setup in VFS %s', col_name, vfs.name)


# Sync meta data and virtual directories from actual path of collection
def sync_collection(col_name):
    vfs = get_current_vfs()
    col = get_collection_by_name(col_name)
    if col is None:
        raise VfsException('Collection %s is not available in VFS %s' % (col_name, vfs.name))
    if not os.path.isdir(col.actual_base):
        raise VfsException('Collection base %s is not available' % col.actual_base)
    col_stats = copy.deepcopy(get_file_stats_for_collection(col_name))
    a2v_map = get_actual_to_virtual_map()
    # Deleted files
    for actual_path in col_stats:
        if os.path.isfile(actual_path) or os.path.islink(actual_path):
            continue
        # Delete links
        if actual_path in a2v_map:
            links = a2v_map[actual_path]
            for link in links:
                os.unlink(link)
        # Delete stats
        del_file_stats(actual_path)
    # Added files
    for root, dirs, files in os.walk(col.actual_base):
        for file_ in files:
            file_path = os.path.join(root, file_)
            if file_path in col_stats:
                continue
            # Add stats
            raw_stats = os.stat(file_path)
            file_stats = FileStat(file_path, raw_stats.st_ctime, raw_stats.st_mtime, raw_stats.st_size)
            add_file_stats(file_stats)
            # Create link
            rel_path = os.path.relpath(file_path, col.actual_base)
            dest_path = os.path.join(col.virtual_base_original, rel_path)
            try:
                os.makedirs(os.path.dirname(dest_path))
            except OSError as ex:
                if ex.errno != errno.EEXIST:
                    raise
            create_symlink(file_path, dest_path)


# List all collections (cached)
def get_all_collections():
    global _all_collections
    if _all_collections is not None:
        return _all_collections
    vfs_path = compute_vfs_path()
    logger.debug('List is not cached. Fetching all collections under VFS path %s', vfs_path)
    collection_dir_path = os.path.join(vfs_path, config.VFS_COLLECTIONS_DIR)
    dirs = os.listdir(collection_dir_path)
    _list = []
    for col_dir in dirs:
        col = read_meta_data(collection_dir_path, col_dir, config.COLLECTION_META_FILE, valid_class=CollectionMeta)
        _list.append(col)
        _all_collections = _list
    return _list


# Get map of collection name to collection meta (cached)
def get_all_collections_by_name():
    global _collections_by_name
    if _collections_by_name is not None:
        return _collections_by_name
    logger.debug('Map is not cached. Fetching all collections by name')
    cols = get_all_collections()
    _collections_by_name = {col.name: col for col in cols}
    return _collections_by_name


# Get meta for a collection by name
def get_collection_by_name(col_name):
    cols_by_name = get_all_collections_by_name()
    return cols_by_name[col_name] if col_name in cols_by_name else None


# Get meta for a collection by specifying any path within the collection
def get_collection_by_path(actual_path):
    abs_actual_path = os.path.abspath(actual_path)
    all_cols = get_all_collections()
    match = None
    for col in all_cols:
        abs_actual_base = os.path.abspath(col.actual_base)
        if abs_actual_path.startswith(abs_actual_base):
            match = col
            break
    return match


# Get stats for all actual files and dirs in a collection as a map of absolute file path to stats meta (cached)
def get_file_stats_for_collection(col_name):
    global _actual_file_stats
    if _actual_file_stats is not None and col_name in _actual_file_stats:
        return _actual_file_stats[col_name]
    logger.debug('Stats are not cached for collection %s. Fetching stats.', col_name)
    col_dir_path = compute_collection_path(col_name)
    stats = read_meta_data(col_dir_path, config.COLLECTION_STATS_FILE)
    if _actual_file_stats is None:
        _actual_file_stats = {}
    _actual_file_stats[col_name] = stats
    return stats


# Get stats for all collections as a map of path to stats
def get_file_stats_for_all_collections():
    all_cols = get_all_collections()
    all_stats = {}
    for col in all_cols:
        num_all_stats = len(all_stats)
        col_stats = get_file_stats_for_collection(col.name)
        all_stats.update(col_stats)
        overlap_count = num_all_stats + len(col_stats) - len(all_stats)
        if overlap_count > 0:
            logger.warn('Overlapping stats found in collection %s: %d', overlap_count)
    return all_stats


# Get stats for an actual file path
def get_file_stats_for_actual_path(actual_path):
    col = get_collection_by_path(actual_path)
    if col is None:
        return None
    all_stats = get_file_stats_for_collection(col.name)
    return all_stats[actual_path] if actual_path in all_stats else None


# Get stats for an actual file corresponding to the specified symlink
def get_file_stats_for_symlink(link_path):
    logger.debug('Fetching stats for symlink %s', link_path)
    abs_link_path = os.path.abspath(link_path)
    actual_path = os.readlink(abs_link_path)
    logger.debug('Actual path for the symlink: %s', actual_path)
    return get_file_stats_for_actual_path(actual_path)


# Delete stats for an actual file
def del_file_stats(actual_path):
    logger.debug('Trying to delete file stats for actual path %s', actual_path)
    col = get_collection_by_path(actual_path)
    if col is None:
        raise VfsException('Actual path %s is not part of any available collection in the current VFS', actual_path)
    logger.debug('Collection for actual path is %s', col.name)
    col_stats = get_file_stats_for_collection(col.name)
    col_stats.pop(actual_path)
    col_dir_path = compute_collection_path(col.name)
    write_meta_data(col_stats, col_dir_path, config.COLLECTION_STATS_FILE, delay_save_meta=True)
    logger.debug('Deleted stats successfully')


# Delete stats for an actual file
def add_file_stats(stats):
    logger.debug('Trying to add stats for actual path %s', stats.actual_path)
    col = get_collection_by_path(stats.actual_path)
    if col is None:
        raise VfsException('Actual path %s is not part of any available collection in the current VFS',
                           stats.actual_path)
    logger.debug('Collection for actual path is %s', col.name)
    col_stats = get_file_stats_for_collection(col.name)
    col_stats[stats.actual_path] = stats
    col_dir_path = compute_collection_path(col.name)
    write_meta_data(col_stats, col_dir_path, config.COLLECTION_STATS_FILE, delay_save_meta=True)
    logger.debug('Added stats successfully')


# Get a mapping of actual files to a list of their virtual links (cached)
def get_actual_to_virtual_map():
    global _actual_to_virtual_map
    if _actual_to_virtual_map is not None:
        return _actual_to_virtual_map

    logger.debug('Not cached. Creating actual to virtual files map')
    vfs = get_current_vfs()
    actual_to_virtual_map = {}

    files_mapped = 0

    for root, dirs, files in vfs_walk(vfs.virtual_base):

        # Mapped files
        for file_ in files:
            abs_file = os.path.abspath(os.path.join(root, file_))
            if os.path.islink(abs_file):
                file_stat = get_file_stats_for_symlink(abs_file)
                if file_stat is not None:
                    if file_stat.actual_path not in actual_to_virtual_map:
                        actual_to_virtual_map[file_stat.actual_path] = []
                    actual_to_virtual_map[file_stat.actual_path].append(abs_file)
                    logger.debug('Added mapping of actual file %s to symlink %s', file_stat.actual_path, abs_file)
                    files_mapped += 1

    _actual_to_virtual_map = actual_to_virtual_map
    logger.debug('Actual to virtual files map created successfully. Num files mapped: %d', files_mapped)
    return _actual_to_virtual_map


# Disc utils


# Cached data
_all_discs = None
_discs_by_name = None


# Meta data for discs
class DiscMeta(PrintableObject):
    def __init__(self, name, disc_base, capacity=None):
        self.name = name
        self.disc_base = disc_base
        self.capacity = capacity


# Compute meta file path
def compute_discs_path():
    path = os.path.join(compute_vfs_path(), config.VFS_DISCS_FILE)
    logger.debug('Discs meta data file computed: %s', path)
    return path


# Reset cached variables
def _invalidate_discs_cache():
    logger.debug('Invalidating discs cache')
    global _all_discs, _discs_by_name
    _all_discs = _discs_by_name = None


# Add a new disc
def add_disc(disc_name, disc_base, capacity=None):
    logger.debug('Trying to add disc %s at base %s and capacity %s', disc_name, disc_base, capacity)
    vfs = get_current_vfs()

    # Validations
    if type(disc_name) is not str or len(disc_name) == 0:
        raise VfsException('Invalid disc name %s' % disc_name)
    if not os.path.isdir(disc_base):
        raise VfsException('Invalid directory %s specified as disc base' % disc_base)
    if capacity is not None and (type(capacity) is not int or capacity < 0):
        raise VfsException('Invalid disc capacity %s' % capacity)
    if get_disc_by_name(disc_name) is not None:
        raise VfsException('Disc named %s already exists in VFS %s', (disc_name, vfs.name))
    disc_by_path = get_disc_by_path(disc_base)
    if disc_by_path is not None:
        raise VfsException('Path %s is already part of an existing disc %s with base at %s',
                           (disc_base, disc_by_path.name, disc_by_path.disc_base))

    # Add new disc meta to existing list
    all_discs = get_all_discs()
    meta = DiscMeta(disc_name, os.path.abspath(disc_base), capacity)
    all_discs.append(meta)
    write_meta_data(all_discs, compute_discs_path())
    _invalidate_discs_cache()

    logger.debug('Disc %s added successfully', disc_name)


# Delete an existing disc
def del_disc(disc_name):
    logger.debug('Trying to delete disc %s', disc_name)
    vfs = get_current_vfs()

    # Validations
    disc = get_disc_by_name(disc_name)
    if disc is None:
        raise VfsException('Disc named %s is not available in VFS %s' % (disc_name, vfs.name))

    # Find disc index in list and delete it
    all_discs = get_all_discs()
    disc_index = None
    for i, disc_candy in enumerate(all_discs):
        if disc_candy.name == disc_name:
            disc_index = i
    if disc_index is None:
        raise VfsException('Disc meta for disc named %s was not found' % disc_name)
    all_discs.pop(disc_index)
    write_meta_data(all_discs, compute_discs_path())
    _invalidate_discs_cache()

    logger.debug('Disc %s deleted successfully', disc_name)


# Get all discs (cached)
def get_all_discs():
    global _all_discs
    if _all_discs is not None:
        return _all_discs
    logger.debug('List is not cached. Fetching all discs')
    try:
        _all_discs = read_meta_data(compute_discs_path())
    except IOError:
        logger.debug('Failed to read discs meta file')
        _all_discs = []
    return _all_discs


# Discs by name
def get_all_discs_by_name():
    global _discs_by_name
    if _discs_by_name is not None:
        return _discs_by_name
    logger.debug('Map is not cached. Fetching all discs by name')
    discs = get_all_discs()
    _discs_by_name = {disc.name: disc for disc in discs}
    return _discs_by_name


# Get disc meta for a disc by name
def get_disc_by_name(disc_name):
    discs_by_name = get_all_discs_by_name()
    return discs_by_name[disc_name] if disc_name in discs_by_name else None


# Get disc meta for a disc containing the specified path
def get_disc_by_path(actual_path):
    abs_actual_path = os.path.abspath(actual_path)
    all_discs = get_all_discs()
    match = None
    for disc in all_discs:
        abs_disc_base = os.path.abspath(disc.disc_base)
        if abs_actual_path.startswith(abs_disc_base):
            match = disc
            break
    return match


# Save map utils


# Cached data
_all_save_maps = None


# Meta data for save maps
class SaveMapMeta(PrintableObject):
    def __init__(self, virtual_dir, actual_dir):
        self.virtual_dir = virtual_dir
        self.actual_dir = actual_dir


# Compute meta file path
def compute_save_maps_path():
    path = os.path.join(compute_vfs_path(), config.VFS_SAVE_MAPS_FILE)
    logger.debug('Save maps meta data file path computed: %s', path)
    return path


# Reset cached variables
def _invalidate_save_maps_cache():
    logger.debug('Invalidating save maps cache')
    global _all_save_maps
    _all_save_maps = None


# Add a new save map
def add_save_map(virtual_dir, actual_dir):
    logger.debug('Trying to add a new save map of Virtual dir %s to Actual dir %s', virtual_dir, actual_dir)
    curr_vfs = get_current_vfs()
    vfs = get_vfs_by_path(virtual_dir)

    # Validations
    if not vfs:
        raise VfsException('VFS not found for virtual directory %s' % virtual_dir)
    if vfs.name != curr_vfs.name:
        raise VfsException('Virtual directory is part of another VFS %s' % vfs.name)
    col = get_collection_by_path(actual_dir)
    if col is None:
        raise VfsException('Actual directory %s is not part oif any available collections' % actual_dir)
    if get_save_map_by_virtual_path(virtual_dir) is not None:
        raise VfsException('Virtual directory %s is already mapped' % virtual_dir)
    if get_save_map_by_actual_path(actual_dir) is not None:
        raise VfsException('Actual directory %s is already mapped' % actual_dir)

    # Add new meta to the existing list
    save_maps = get_all_save_maps()
    meta = SaveMapMeta(os.path.abspath(virtual_dir), os.path.abspath(actual_dir))
    save_maps.append(meta)
    write_meta_data(save_maps, compute_save_maps_path())
    _invalidate_save_maps_cache()

    logger.debug('Save map added successfully')


# Deleted all save maps
def del_all_save_maps():
    logger.debug('Trying to delete all save maps')
    write_meta_data([], compute_save_maps_path())
    _invalidate_save_maps_cache()
    logger.debug('All save maps deleted successfully')


# Get all save maps (cached)
def get_all_save_maps():
    global _all_save_maps
    if _all_save_maps is not None:
        return _all_save_maps
    logger.debug('List is not cached. Fetching all save maps')
    try:
        _all_save_maps = read_meta_data(compute_save_maps_path())
    except IOError:
        logger.debug('Failed to read save maps meta file')
        _all_save_maps = []
    return _all_save_maps


# Get save map for a virtual path
def get_save_map_by_virtual_path(virtual_path):
    abs_virtual_path = os.path.abspath(virtual_path)
    all_save_maps = get_all_save_maps()
    match = None
    for save_map in all_save_maps:
        abs_virtual_base = os.path.abspath(save_map.virtual_dir)
        if abs_virtual_path.startswith(abs_virtual_base):
            match = save_map
            break
    return match


# Get save map for an actual path
def get_save_map_by_actual_path(actual_path):
    abs_actual_path = os.path.abspath(actual_path)
    all_save_maps = get_all_save_maps()
    match = None
    for save_map in all_save_maps:
        abs_actual_base = os.path.abspath(save_map.actual_dir)
        if abs_actual_path.startswith(abs_actual_base):
            match = save_map
            break
    return match


# Convert a virtual path to its mapped actual path using the save maps
def convert_virtual_to_actual_using_save_map(virtual_path):
    abs_virtual_path = os.path.abspath(virtual_path)
    save_map = get_save_map_by_virtual_path(abs_virtual_path)
    return abs_virtual_path.replace(save_map.virtual_dir, save_map.actual_dir)


# Convert a actual path to its mapped virtual path using the save maps
def convert_actual_to_virtual_using_save_map(actual_path):
    abs_actual_path = os.path.abspath(actual_path)
    save_map = get_save_map_by_actual_path(abs_actual_path)
    return abs_actual_path.replace(save_map.actual_dir, save_map.virtual_dir) if save_map is not None else None


# Backup utils


# Cached data
_all_backups = None


# Meta data for a backup
class BackupMeta(PrintableObject):
    def __init__(self, name, comment, vfs, virtual_path, created):
        self.name = name
        self.comment = comment
        self.vfs = vfs
        self.virtual_path = virtual_path
        self.created = created


# Compute backup path
def compute_backup_path(name):
    path = os.path.join(get_vfs_home(), config.VFS_BACKUP_DIR, name)
    logger.debug('Path computed for backup named %s: %s', name, path)
    return path


# Reset cached variables
def _invalidate_backup_cache():
    logger.debug('Invalidating backup cache')
    global _all_backups
    _all_backups = None


# Create a new backup
def create_backup(vfs_name, comment):
    vfs = get_vfs_by_name(vfs_name)
    if vfs is None:
        VfsException('VFS named %s has not yet bee created' % vfs_name)

    # Generate backup name
    backup_name = "%s_%d" % (vfs.name, uuid.uuid4())
    logger.debug('Generated backup name: %s', backup_name)

    # Create backup dir
    backup_dir = compute_backup_path(backup_name)
    logger.debug('Creating backup dir %s', backup_dir)
    os.mkdir(backup_dir)

    # Backup VFS and Virtual
    vfs_path = compute_vfs_path()
    vfs_path_backup = os.path.join(backup_dir, config.BACKUP_VFS_DIR)
    logger.debug('Backing up vfs path %s to backup path %s', vfs_path, vfs_path_backup)
    shutil.copytree(vfs_path, vfs_path_backup, symlinks=True)
    virtual_path = vfs.virtual_base
    virtual_path_backup = os.path.join(backup_dir, config.BACKUP_VIRTUAL_DIR)
    logger.debug('Backing up virtual path %s to backup path %s', virtual_path, vfs_path_backup)
    shutil.copytree(virtual_path, virtual_path_backup, symlinks=True)

    # Save meta data
    created = time.time()
    meta = BackupMeta(backup_name, comment, vfs.name, virtual_path, created)
    logger.debug('Backup meta: %s', meta)
    write_meta_data(meta, backup_dir, config.BACKUP_META_FILE, valid_class=BackupMeta)

    _invalidate_backup_cache()
    return backup_name


# Delete a backup by name
def del_backup(backup_name):
    backup_path = compute_backup_path(backup_name)
    logger.debug('Deleting backup named %s from path %s', backup_name, backup_path)
    if not os.path.isdir(backup_path):
        raise VfsException('No backup named %s' % backup_name)
    shutil.rmtree(backup_path)
    _invalidate_backup_cache()


# List all backups
def list_backups():
    global _all_backups
    if _all_backups is not None:
        return _all_backups
    backup_dir = os.path.join(get_vfs_home(), config.VFS_BACKUP_DIR)
    all_backup_dirs = os.listdir(backup_dir)
    all_backups = []
    for dir in all_backup_dirs:
        full_path = os.path.join(backup_dir, dir)
        meta = read_meta_data(full_path, config.BACKUP_META_FILE, valid_class=BackupMeta)
        all_backups.append(meta)
    _all_backups = all_backups
    return all_backups


# Restore a backup
def restore_backup(backup_name):
    backup_path = compute_backup_path(backup_name)
    logger.debug('Restoring backup named %s from path %s', backup_name, backup_path)
    if not os.path.isdir(backup_path):
        raise VfsException('No backup named %s' % backup_name)

    # Read meta
    meta = read_meta_data(backup_path, config.BACKUP_META_FILE)
    logger.debug('Backup meta: %s', meta)

    # Copy current dirs to temp dirs
    vfs_path = compute_vfs_path(meta.vfs)
    virtual_path = meta.virtual_path
    temp_curr_backup = tempfile.mkdtemp()
    logger.debug('Backing up VFS path %s and Virtual path %s to temp dir %s', vfs_path, virtual_path, temp_curr_backup)
    try:
        shutil.move(virtual_path, os.path.join(temp_curr_backup, config.BACKUP_VIRTUAL_DIR))
    except IOError as ex:
        if ex.errno == errno.ENOENT:
            logger.debug('Current virtual path could not be backed up as it does not exist')
        else:
            raise
    try:
        shutil.move(vfs_path, os.path.join(temp_curr_backup, config.BACKUP_VFS_DIR))
    except IOError as ex:
        if ex.errno == errno.ENOENT:
            logger.debug('Current VFS path could not be backed up as it does not exist')
        else:
            raise

    # Restore backup
    logger.debug('Restoring from backup')
    try:
        vfs_path_backup = os.path.join(backup_path, config.BACKUP_VFS_DIR)
        shutil.copytree(vfs_path_backup, vfs_path, symlinks=True)
        virtual_path_backup = os.path.join(backup_path, config.BACKUP_VIRTUAL_DIR)
        shutil.copytree(virtual_path_backup, virtual_path, symlinks=True)
    except IOError:
        logger.debug('Restore failed. Trying to restore current directories')
        try:
            shutil.rmtree(virtual_path, ignore_errors=True)
            shutil.move(os.path.join(temp_curr_backup, config.BACKUP_VIRTUAL_DIR), virtual_path)
        except IOError:
            logger.debug('Current virtual path could not be restored', exc_info=True)
        try:
            shutil.rmtree(vfs_path, ignore_errors=True)
            shutil.move(os.path.join(temp_curr_backup, config.BACKUP_VFS_DIR), vfs_path)
        except IOError:
            logger.debug('Current VFS path could not be restored', exc_info=True)
        raise

    # Remove temp dirs
    logger.debug('Removing temp dir')
    shutil.rmtree(temp_curr_backup)


# Virtual path props utils


# Path of property file of a virtual directory
def compute_virtual_dir_prop_path(dir_path):
    return "%s/.%s%s" % (dir_path, os.path.basename(os.path.abspath(dir_path)), config.PROP_FILE_EXT)


# Path of property file of a virtual file
def compute_virtual_file_prop_path(file_path):
    return os.path.join(os.path.dirname(file_path),
                        ".%s%s" % (os.path.basename(os.path.abspath(file_path)), config.PROP_FILE_EXT))


# Set a prop
def set_virtual_path_prop(prop, value, virtual_path, override=True):
    logger.debug('Trying to set Property:"%s", Value:"%s" for virtual path %s. (Override=%s)',
                 prop, value, virtual_path, override)
    if os.path.isdir(virtual_path):
        prop_path = compute_virtual_dir_prop_path(virtual_path)
    else:
        if os.path.islink(virtual_path):
            prop_path = compute_virtual_file_prop_path(virtual_path)
        else:
            raise VfsException('Path %s is neither directory nor symlink', virtual_path)
    logger.debug('Prop path: %s', prop_path)
    try:
        meta = read_meta_data(prop_path)
        logger.debug('Prop file read: %s', meta)
    except IOError as ex:
        if ex.errno == errno.ENOENT:
            meta = {}
            logger.debug('Prop file does not already exist')
        else:
            raise
    if prop in meta and not override:
        raise VfsException('Property %s already exists for virtual directory %s', prop, virtual_path)
    meta[prop] = value
    logger.debug('Updated meta: %s', meta)
    write_meta_data(meta, prop_path)
    logger.debug('Property has been set successfully')


def get_virtual_path_props(virtual_path):
    logger.debug('Trying to get properties for virtual path %s', virtual_path)
    if os.path.isdir(virtual_path):
        prop_path = compute_virtual_dir_prop_path(virtual_path)
    else:
        if os.path.islink(virtual_path):
            prop_path = compute_virtual_file_prop_path(virtual_path)
        else:
            raise VfsException('Path %s is neither directory nor symlink', virtual_path)
    logger.debug('Prop path: %s', prop_path)
    try:
        meta = read_meta_data(prop_path)
        logger.debug('Prop file read: %s', meta)
    except IOError as ex:
        if ex.errno == errno.ENOENT:
            meta = {}
            logger.debug('Prop file does not already exist')
        else:
            raise
    logger.debug('Props fetched: %s', meta)
    return meta


# Read a prop
def get_virtual_path_prop(prop, virtual_path):
    logger.debug('Trying to get Property:"%s" for virtual path %s', prop, virtual_path)
    meta = get_virtual_path_props(virtual_path)
    value = None
    if prop in meta:
        value = meta[prop]
    logger.debug('Value fetched: %s', value)
    return value


# Generic utils


# Convert size in bytes to human readable string
def get_readable_size(size_bytes):
    temp = size_bytes
    units = ['Bytes', 'kB', 'MB', 'GB']
    x = 0
    for x in range(len(units)):
        if temp >= 1024 and x < (len(units) - 1):
            temp = float(temp) / 1024
            continue
        break
    return '%.2f %s' % (temp, units[x])


# Compute directory size, in Bytes, for a virtual directory
def get_virtual_dir_size(dir_path):
    size = 0
    for root, dirs, files in vfs_walk(dir_path):
        for file_ in files:
            link_path = os.path.join(root, file_)
            if not os.path.islink(link_path):
                logger.debug('File %s is not a symlink', link_path)
                continue
            actual_path = os.readlink(link_path)
            file_stat = get_file_stats_for_actual_path(actual_path)
            if file_stat is None:
                logger.debug('Stats missing for symlink %s' % actual_path)
                continue
            size += file_stat.size
    return size


# Compute directory size, in Bytes, for an actual directory
def get_actual_dir_size(dir_path):
    size = 0
    for root, dirs, files in os.walk(dir_path):
        for file_ in files:
            file_path = os.path.join(root, file_)
            size += os.lstat(file_path).st_size
    return size


# os.walk but skipping files with the VFS extention
def vfs_walk(path):
    for root, dirs, files in os.walk(path):
        yield root, dirs, filter(lambda file_: not is_vfs_file(file_), files)


# Check if file is VFS file
def is_vfs_file(file_path):
    return os.path.splitext(file_path)[-1] == config.VFS_FILE_EXT
