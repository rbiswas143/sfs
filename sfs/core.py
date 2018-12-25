import os
import collections
import itertools
import shutil

import sfs.file_system as fs
import sfs.log_utils as log

# Constants

constants = {
    'SFS_DIR': 'sfs',
    'SFS_META_FILE': 'meta',
    'COLLECTION_DIR': 'cols',
    'COLLECTION_STATS_DIR': 'stats',
    'SFS_FILE_EXTENSION': '.sfs',
}

# Tuple of altered file system nodes

SfsUpdates = collections.namedtuple('SFSUpdates', 'added deleted updated')


class SFS:
    """
    SFS - Symbolic  File System

    - This class encapsulates all operations and queries related to a single SFS
    - An SFS is a managed directory which can contain symbolic links to various other directories, discs and removable
    media
    - A directory can be added to an SFS as a named collection which involves addition of symbolic links to each file
    (and symbolic link) in the added directory to the SFS instead of adding the actual files
    - SFS maintains the metadata of all files such that they can queried even when the actual disc or removable media
    is unavailable. This is especially useful while organizing data or in situations where immediate access to files is
    not important or relevant
    - A created SFS instance can be obtained by specifying any path within the SFS using the method 'SFS.get_by_path'
    - An SFS cannot be nested within another SFS
    """

    def __init__(self, root):
        self.root = root
        self.collections = {}

    @staticmethod
    def init_sfs(path):
        """
        Initialize an SFS in an empty directory
        - Creates a hidden directory for all SFS metadata
        - Persists an SFS metadata file
        """
        fs.create_hidden_directory(constants['SFS_DIR'], path)
        sfs = SFS(path)
        sfs._save()

    @staticmethod
    def get_by_path(path):
        """
        Check whether 'path' lies within an SFS, ie, if any ancestor is a valid SFS root directory
        :return: SFS instance if found or None
        """
        while path != '/':
            if SFS._is_sfs_root(path):
                # Create an instance and load persisted metadata
                sfs = SFS(path)
                sfs._load()
                return sfs
            path = os.path.dirname(path)
        return None

    @staticmethod
    def get_sfs_dir(root):
        """Compute SFS directory given the path of an SFS root directory"""
        return fs.get_hidden_directory_path(constants['SFS_DIR'], root)

    @staticmethod
    def get_collections_dir(root):
        """Compute path of collections metadata directory given the path of an SFS root directory"""
        return os.path.join(SFS.get_sfs_dir(root), constants['COLLECTION_DIR'])

    def _save(self):
        """Persist the metadata of the current SFS"""
        # fs.save_pickled(self.meta, SFS.get_sfs_dir(self.root), constants['SFS_META_FILE'])
        save_dict = {
            'collections': self.collections
        }
        fs.save_pickled(save_dict, SFS.get_sfs_dir(self.root), constants['SFS_META_FILE'])

    def _load(self):
        """Load the metadata of the current SFS"""
        save_dict = fs.load_unpickled(SFS.get_sfs_dir(self.root), constants['SFS_META_FILE'])
        if type(save_dict) is dict and 'collections' in save_dict:
            self.collections = save_dict['collections']
        else:
            log.logger.warn('Invalid metadata for SFS with root at "%s"', self.root)

    @staticmethod
    def _is_sfs_root(sfs_root):
        """Check if a directory is a valid SFS root. It must contain an SFS directory and within it metadata"""
        meta_path = os.path.join(SFS.get_sfs_dir(sfs_root), constants['SFS_META_FILE'])
        return os.path.exists(meta_path)

    def add_collection(self, name, base):
        """
        Add a directory located at 'base' as a collection named 'name' to the current SFS
        - Updates SFS metadata with new collection details
        - Creates a collection metadata directory
        - Adds links to to all files in the directory
        :return: A named tuple of type SfsUpdates indicating the number of files added
        """
        col_dir = os.path.join(SFS.get_collections_dir(self.root), name)
        col = Collection(name, base, self.root, col_dir)
        os.makedirs(col_dir)

        self.collections[name] = col.get_save_dict()
        self._save()

        return col.add_or_update()

    def get_collection_by_name(self, name):
        """
        Look up the SFS metadata for a collection with the specified name
        :param name: Collection Name
        :return: Instance of Collection if found else None
        """
        return Collection.form_save_dict(
            self.collections[name],
            self.root,
            os.path.join(SFS.get_collections_dir(self.root), name)
        ) if name in self.collections else None

    def get_collection_by_path(self, path):
        """
        Look up the SFS metadata for a collection whose source directory contains the specified path
        :param path: A path within the source directory of a collection
        :return: Instance of Collection if found else None
        """
        path = fs.expand_path(path)
        cols = self.get_all_collections()
        while path != '/':
            for col in cols.values():
                if path == col.base:
                    return col
            path = os.path.dirname(path)
        return None

    def get_all_collections(self):
        """Return all collections as a map of Collection Name to the corresponding Collection instance"""
        return {name: self.get_collection_by_name(name) for name in self.collections.keys()}

    def del_collection(self, name):
        """
        Delete the metadata associated with a collection
        - Removes collection details from SFS metadata
        - Deletes the collection metadata directory
        - Does NOT delete links corresponding to the deleted collection and any such links become orphan links
        """
        col = self.get_collection_by_name(name)
        self.collections.pop(name)
        shutil.rmtree(col.col_dir)
        self._save()

    def del_orphans(self, col_root=None):
        """
        Deletes orphan and foreign links from the current SFS
        An orphan link is part of an existing collection but does not have associated metadata, for example, when a
        collection is synced, metadata of deleted files is removed and associated links may become orphans
        A foreign link is one that is not part of any collection in the current SFS
        :param col_root: If not None, the deletion is restricted to links that point within the specified path
        :return: A named tuple of type SfsUpdates indicating the number of links deleted
        """

        def _del_cond_all(path):
            """Return True for a foreign or orphan link given its source path"""
            col = self.get_collection_by_path(path)
            return col is None or col.get_stats(path) is None

        def _del_cond_by_root(path):
            """Return True for foreign or orphan links within the psecified collection root given the source path"""
            return fs.is_parent_dir(path, col_root) and _del_cond_all(path)

        _del_cond = _del_cond_all if col_root is None else _del_cond_by_root

        deleted = 0
        for root, dirs, files, links in SFS.walk(fs.walk_dfs, self.root):
            # Check for foreign or orphan links and delete them
            for lnk in links:
                if _del_cond(os.readlink(lnk.path)):
                    deleted += 1
                    os.unlink(lnk.path)

        return SfsUpdates(added=0, deleted=deleted, updated=0)

    @staticmethod
    def walk(walk_gen, start_dir):
        """
        Enumerate paths inside an SFS by excluding SFS specific files and directories
        Exclusions: SFS directory, Files with SFS specific extensions
        :param walk_gen: A path generator, for example, fs.walk_bfs
        :param start_dir: Directory within an SFS whose contents are to be enumerated
        """
        sfs = SFS.get_by_path(start_dir)
        _filter_dirs = {
            fs.get_hidden_directory_path(constants['SFS_DIR'], sfs.root)
        }
        _filter_extensions = {
            constants['SFS_FILE_EXTENSION']
        }
        for root, files, dirs, links in walk_gen(start_dir):
            dirs[:] = list(filter(lambda n: n.path not in _filter_dirs, dirs))
            files[:] = list(filter(lambda n: os.path.splitext(n.name)[1] not in _filter_extensions, files))
            yield root, files, dirs, links


class Collection:
    """
   SFS Collection

   - This class encapsulates all operations and queries related to a single SFS collection
   - A collection is a directory that has been added to an SFS and it comprises of links to the contents of the
   directory as well as their metadata
   - Collection instances are associated to and accessible through an SFS instance
   """

    def __init__(self, name, base, sfs_root, col_dir):
        self.name = name
        self.base = base
        self.sfs_root = sfs_root
        self.col_dir = col_dir
        self.stats_base = os.path.join(self.col_dir, constants['COLLECTION_STATS_DIR'])

    @staticmethod
    def form_save_dict(col_dict, sfs_root, col_dir):
        """Initialize an instance from a persisted metadata dictionary"""
        return Collection(col_dict['name'], col_dict['base'], sfs_root, col_dir)

    def get_save_dict(self):
        """Return a dictionary representing the collection state to tbe persisted"""
        return {
            'name': self.name,
            'base': self.base
        }

    def add_or_update(self, curr_stats=None):
        """
        Adds or updates collection metadata and adds links to new collection files
        :param curr_stats: A set of all paths to files that were previously added to the collection. Any path not in
        this set is treated as a new collection file. If None, all files are treated as new
        :return: A named tuple of type SfsUpdates indicating the number of files added or updated
        """
        added = updated = 0
        sfs_base = os.path.join(self.sfs_root, self.name)
        for root, files, dirs, links in fs.walk_bfs(self.base):

            # Compute metadata directory and SFS directory for current directory
            root_rel = os.path.relpath(root, self.base)
            stats_root = os.path.abspath(os.path.join(self.stats_base, root_rel))
            sfs_root = os.path.abspath(os.path.join(sfs_base, root_rel))
            os.makedirs(stats_root, exist_ok=True)

            for node in itertools.chain(files, links):
                col_file = node.path
                if curr_stats is None or col_file not in curr_stats:
                    # Create links for new collection files that are not in curr_stats
                    added += 1
                    os.makedirs(sfs_root, exist_ok=True)
                    sfs_file = os.path.join(sfs_root, node.name)
                    fs.create_symlink(col_file, sfs_file)
                else:
                    updated += 1

                # Save metadata
                stats_file = os.path.join(stats_root, node.name)
                fs.save_pickled(node.stat, stats_file)

        return SfsUpdates(added=added, deleted=0, updated=updated)

    def update(self):
        """
        Updates the metadata of an existing collection specified by the given Collection Name
        - Adds, deletes and updates collection metadata to synchronize with actual source directory
        - For new files in collections (ones without pre-existing metadata) links are alos added to the SFS
        :return: A named tuple of type SfsUpdates indicating the number of files added and updated
        """
        # Create a set of all existing source files in the collection
        curr_stats = set(
            [os.path.join(self.base, os.path.relpath(f.path, self.stats_base))
             for root, files, dirs, links in fs.walk_bfs(self.stats_base) for f in files]
        )

        # Delete all collections metadata
        shutil.rmtree(self.stats_base)

        # Update metadata and links
        sfs_updates = self.add_or_update(curr_stats=curr_stats)
        return sfs_updates

    def get_stats(self, col_path):
        """
        Fetch the metadata of source file located at 'col_path' in the current SFS collection
        :param col_path: Path of source file or link
        :return: Instance of fs.FSNode.NodeStats if found else None
        """
        rel_path = os.path.relpath(col_path, self.base)
        meta_path = os.path.join(self.stats_base, rel_path)
        return fs.load_unpickled(meta_path) if os.path.isfile(meta_path) else None
