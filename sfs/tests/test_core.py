import datetime
import os
import shutil
import time

import sfs.core as core
import sfs.file_system as fs
import sfs.tests.helper as helper


class SFSCoreTests(helper.TestCaseWithFS):

    def test_init_sfs(self):
        root = self.TESTS_BASE
        core.SFS.init_sfs(root)

        # Creates hidden SFS directory
        sfs_dir_path = fs.get_hidden_directory_path(core.constants['SFS_DIR'], root)
        self.assertTrue(os.path.isdir(sfs_dir_path))

        # Writes SFS meta data to file
        sfs_meta_path = os.path.join(sfs_dir_path, core.constants['SFS_META_FILE'])
        self.assertTrue(os.path.isfile(sfs_meta_path))
        loaded = fs.load_unpickled(sfs_meta_path)
        self.assertEqual({
            'collections': {}
        }, loaded)

    def test_get_sfs_by_path(self):
        tree = {
            'dirs': {
                'dir_a': {
                    'dirs': {
                        'dir_aa': {}
                    }
                },
                'dir_b': {}
            }
        }
        self.create_fs_tree(tree)
        path_a = os.path.join(self.TESTS_BASE, 'dir_a')
        path_aa = os.path.join(path_a, 'dir_aa')
        path_b = os.path.join(self.TESTS_BASE, 'dir_b')
        core.SFS.init_sfs(path_a)

        # Returns SFS object for SFS root or any child path
        sfs = core.SFS.get_by_path(path_a)
        self.assertEqual(path_a, sfs.root)
        sfs = core.SFS.get_by_path(path_aa)
        self.assertEqual(path_a, sfs.root)

        # Returns None for paths not inside an SFS
        sfs = core.SFS.get_by_path(path_b)
        self.assertIsNone(sfs)

    def test_get_sfs_dir(self):
        root = self.TESTS_BASE

        # Returns SFS directory for a given SFS root directory
        self.assertEqual(fs.get_hidden_directory_path(core.constants['SFS_DIR'], root),
                         core.SFS.get_sfs_dir(root))

    def test_get_collections_dir(self):
        root = self.TESTS_BASE

        # Returns collection meta directory for all collections given an SFS root directory
        self.assertEqual(
            os.path.join(
                fs.get_hidden_directory_path(core.constants['SFS_DIR'], root),
                core.constants['COLLECTION_DIR']
            ),
            core.SFS.get_collections_dir(root)
        )


class CollectionTests(helper.TestCaseWithFS):

    def __init__(self, *args, **kwargs):
        super(CollectionTests, self).__init__(*args, **kwargs)
        self.tree = {
            'dirs': {
                'col1': {
                    'files': ['file_1a', 'file_1b'],
                    'links': ['link_1a'],
                    'dirs': {
                        'dir_1a': {
                            'files': ['file_1aa'],
                            'dirs': {
                                'dir_1aa': {
                                    'files': ['file_1aaa']
                                }
                            }
                        }
                    }
                },
                'col2': {
                    'files': ['file_2a']
                },
                'sfs_test': {}
            }
        }
        self.col1_base = os.path.join(self.TESTS_BASE, 'col1')
        self.col2_base = os.path.join(self.TESTS_BASE, 'col2')
        self.sfs_base = os.path.join(self.TESTS_BASE, 'sfs_test')
        self.sfs_dir = fs.get_hidden_directory_path(core.constants['SFS_DIR'], self.sfs_base)

    def setUp(self):
        super(CollectionTests, self).setUp()
        self.create_fs_tree(self.tree)
        core.SFS.init_sfs(self.sfs_base)
        self.sfs = core.SFS.get_by_path(self.sfs_base)

    def _validate_collection_meta(self, meta, name, base):
        # Validates type and properties of a collection meta object
        self.assertEqual({
            'name': name,
            'base': base
        }, meta)

    def test_add_collection_directories(self):
        self.sfs.add_collection('col1', self.col1_base)

        # Creates meta directory for all collections
        cols_dir = os.path.join(self.sfs_dir, core.constants['COLLECTION_DIR'])
        self.assertTrue(os.path.isdir(cols_dir))

        # Creates meta directory for a specific collections
        col_dir = os.path.join(cols_dir, 'col1')
        self.assertTrue(os.path.isdir(cols_dir))

        # Creates stats directory for a specific collections
        stats_dir = os.path.join(col_dir, core.constants['COLLECTION_STATS_DIR'])
        self.assertTrue(os.path.isdir(stats_dir))

    def test_add_collection_meta(self):
        self.sfs.add_collection('col1', self.col1_base)

        # Adds collection meta to sfs
        self.assertIn('col1', self.sfs.collections)
        self._validate_collection_meta(self.sfs.collections['col1'], 'col1', self.col1_base)

        # Persists collection meta
        sfs = core.SFS.get_by_path(self.sfs_base)
        self.assertIn('col1', sfs.collections)
        self._validate_collection_meta(self.sfs.collections['col1'], 'col1', self.col1_base)

    def test_add_collection_links_and_stats(self):
        self.sfs.add_collection('col1', self.col1_base)
        col = self.sfs.get_collection_by_name('col1')

        exp_links = [
            'file_1a',
            'file_1b',
            'link_1a',
            os.path.join('dir_1a', 'file_1aa'),
            os.path.join('dir_1a', 'dir_1aa', 'file_1aaa')
        ]

        # Adds valid links for each collection file with stats
        for lnk in exp_links:
            col_path = os.path.join(self.col1_base, lnk)
            sfs_path = os.path.join(self.sfs_base, 'col1', lnk)
            self.assertTrue(os.path.lexists(sfs_path))
            self.assertTrue(os.path.islink(sfs_path))
            self.assertEqual(col_path, os.readlink(sfs_path))
            self.assertIsNotNone(col.get_stats(col_path))

        # Adds correct number of files and directories
        col_sfs_root = os.path.join(self.sfs.root, 'col1')
        self.assertEqual(0, helper.count_files(col_sfs_root))
        self.assertEqual(2, helper.count_directories(col_sfs_root))
        self.assertEqual(5, helper.count_symlinks(col_sfs_root))

    def test_add_multiple_collections(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)

        # Adds meta for both collections
        for name, base in [('col1', self.col1_base), ('col2', self.col2_base)]:
            self.assertIn(name, self.sfs.collections)
            self._validate_collection_meta(self.sfs.collections[name], name, base)

        # Adds link and stats for both collections
        checks = [
            [
                os.path.join(self.col1_base, 'file_1a'),
                os.path.join(self.sfs_base, 'col1', 'file_1a')
            ],
            [
                os.path.join(self.col2_base, 'file_2a'),
                os.path.join(self.sfs_base, 'col2', 'file_2a')
            ]
        ]
        for col_path, sfs_path in checks:
            self.assertTrue(os.path.exists(sfs_path))
            self.assertTrue(os.path.islink(sfs_path))
            self.assertEqual(col_path, os.readlink(sfs_path))

    def test_get_collection_by_name(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)

        # Returns a valid collection object
        for name, base in [('col1', self.col1_base), ('col2', self.col2_base)]:
            col = self.sfs.get_collection_by_name(name)
            self.assertEqual(
                os.path.join(self.sfs.get_collections_dir(self.sfs.root), name),
                col.col_dir
            )
            self._validate_collection_meta(col.get_save_dict(), name, base)

        # Returns None for unregistered collections
        col3 = self.sfs.get_collection_by_name('col3')
        self.assertIsNone(col3)

    def test_get_collection_by_path(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)

        # Returns a valid collection object
        for name, base, path in [
            ('col1', self.col1_base, os.path.join(self.col1_base, 'dir_1a', 'dir_1aa')),
            ('col2', self.col2_base, os.path.join(self.col2_base, 'dir_2a', 'file_2a'))
        ]:
            col = self.sfs.get_collection_by_path(path)
            self.assertEqual(
                os.path.join(self.sfs.get_collections_dir(self.sfs.root), name),
                col.col_dir
            )
            self._validate_collection_meta(col.get_save_dict(), name, base)

        # Returns None for unregistered paths
        col3 = self.sfs.get_collection_by_path(os.path.join(self.TESTS_BASE, 'col3'))
        self.assertIsNone(col3)
        col11 = self.sfs.get_collection_by_path(os.path.join(self.TESTS_BASE, 'col11'))
        self.assertIsNone(col11)

    def test_get_all_collections(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)
        cols = self.sfs.get_all_collections()

        # Returns a dictionary mapping collection names to collection objects
        exp = {
            name: core.Collection(
                name,
                base,
                self.sfs.root,
                os.path.join(core.SFS.get_collections_dir(self.sfs.root), name),
            ) for name, base in [('col1', self.col1_base), ('col2', self.col2_base)]
        }
        self.assertEqual(len(exp), len(cols))
        for name, col in cols.items():
            self.assertIn(name, exp)
            exp_col = exp[name]
            self.assertEqual(exp_col.col_dir, col.col_dir)
            self.assertEqual(exp_col.__dict__, col.__dict__)

    def test_del_collection(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)

        col1 = self.sfs.get_collection_by_name('col1')
        col2 = self.sfs.get_collection_by_name('col2')
        self.sfs.del_collection('col1')

        # Deletes meta data of only deleted collection
        self.assertFalse(os.path.isdir(col1.col_dir))
        self.assertEqual(1, len(self.sfs.collections))

        # Keeps meta data for other collections
        self.assertTrue(os.path.isdir(col2.col_dir))
        self.assertIn('col2', self.sfs.collections)
        self._validate_collection_meta(self.sfs.collections['col2'], 'col2', self.col2_base)

        # Persists meta changes
        sfs = core.SFS.get_by_path(self.sfs_base)
        self.assertEqual(1, len(sfs.collections))
        self.assertIn('col2', sfs.collections)
        self._validate_collection_meta(sfs.collections['col2'], 'col2', self.col2_base)

        # Deleting orphans of deleted collection by name deletes orphan links only of the specified collection
        sfs.del_collection('col2')
        sfs_updates = sfs.del_orphans(col_root=col1.base)
        self.assertEqual(5, sfs_updates.deleted)

    def test_delete_orphans_col(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)
        col11_base = os.path.join(self.TESTS_BASE, 'col11')
        os.mkdir(col11_base)
        helper.dummy_file(os.path.join(col11_base, 'test_file'))
        self.sfs.add_collection('col11', col11_base)
        col1 = self.sfs.get_collection_by_name('col1')
        col2 = self.sfs.get_collection_by_name('col2')

        # Returns a named tuple - SfsUpdates
        sfs_updates = self.sfs.del_orphans(col_root=col1.base)
        self.assertIsInstance(sfs_updates, core.SfsUpdates)

        # Does not delete links when there are no orphans
        self.assertEqual(0, sfs_updates.added)
        self.assertEqual(0, sfs_updates.deleted)
        self.assertEqual(0, sfs_updates.updated)

        # Making links orphans by deleting the collection
        self.sfs.del_collection('col1')

        # Making links orphans by deleting all stats
        shutil.rmtree(col2.stats_base)

        # Returns the number of deleted links deleting only
        sfs_updates = self.sfs.del_orphans(col_root=col1.base)
        self.assertIsInstance(sfs_updates, core.SfsUpdates)
        self.assertEqual(5, sfs_updates.deleted)

        # Deletes links only for the specified collection root
        sfs_updates = self.sfs.del_orphans(col_root=col2.base)
        self.assertEqual(1, sfs_updates.deleted)

        # Deletes only orphaned links
        self.assertEqual(0, helper.count_symlinks(os.path.join(self.sfs.root, col1.name)))
        self.assertEqual(1, helper.count_symlinks(self.sfs.root))

    def test_delete_orphans_all(self):
        self.sfs.add_collection('col1', self.col1_base)
        self.sfs.add_collection('col2', self.col2_base)

        # Making links orphans by deleting a collection
        col1 = self.sfs.get_collection_by_name('col1')
        self.sfs.del_collection(col1.name)

        sfs_updates = self.sfs.del_orphans()

        # Returns an SfsUpdate named tuple with the number of deleted links set
        self.assertIsInstance(sfs_updates, core.SfsUpdates)
        self.assertEqual(5, sfs_updates.deleted)

        # Deletes only orphaned links
        self.assertEqual(0, helper.count_symlinks(os.path.join(self.sfs.root, col1.name)))
        self.assertEqual(1, helper.count_symlinks(self.sfs.root))

    def test_update_collection(self):
        self.sfs.add_collection('col1', self.col1_base)
        col = self.sfs.get_collection_by_name('col1')
        col_sfs_root = os.path.join(self.sfs.root, 'col1')

        # Stats of a file before update
        col_path_updated = os.path.join(self.col1_base, 'file_1a')
        old_stats = col.get_stats(col_path_updated)

        # Counting nodes before update
        dirs_count = helper.count_directories(col_sfs_root)
        files_count = helper.count_files(col_sfs_root)
        symlinks_count = helper.count_symlinks(col_sfs_root)

        # Replacing collection tree with new tree
        shutil.rmtree(self.col1_base)
        os.mkdir(self.col1_base)
        new_tree = {
            'links': ['link_1b'],
            'dirs': {
                'dir_1a': {
                    'files': ['file_1aa', 'file_1ab'],
                }
            }
        }
        helper.dummy_file(col_path_updated, old_stats.size + 100)
        self.create_fs_tree(new_tree, self.col1_base)

        sfs_updates = col.update()

        # Returns an SfsUpdates object
        self.assertIsInstance(sfs_updates, core.SfsUpdates)
        self.assertEqual(2, sfs_updates.added)
        self.assertEqual(0, sfs_updates.deleted)
        self.assertEqual(2, sfs_updates.updated)

        # Only adds additional links to SFS
        self.assertEqual(dirs_count, helper.count_directories(col_sfs_root))
        self.assertEqual(files_count, helper.count_files(col_sfs_root))
        self.assertEqual(symlinks_count + 2, helper.count_symlinks(col_sfs_root))

        # Adds a valid link to a new collection file
        new_link = os.path.join(col_sfs_root, 'dir_1a', 'file_1ab')
        col_path_new = os.path.join(self.col1_base, 'dir_1a', 'file_1ab')
        self.assertTrue(os.path.islink(new_link))
        self.assertEqual(col_path_new, os.readlink(new_link))

        # Adds meta for new links
        new_stats = col.get_stats(col_path_new)
        self.assertIsNotNone(new_stats)

        # Updates meta for existing links
        updated_stats = col.get_stats(col_path_updated)
        self.assertIsNotNone(new_stats)
        self.assertNotEqual(old_stats.size, updated_stats.size)

        # Deleting orphan links for the updated collection works correctly
        deletions = self.sfs.del_orphans(col_root=col.base)
        self.assertEqual(0, deletions.added)
        self.assertEqual(3, deletions.deleted)
        self.assertEqual(0, deletions.updated)

    def test_get_stats(self):
        # Adding a file to a collection and recording the time before and after
        before = datetime.datetime.now()
        time.sleep(0.1)  # Delay to compensate for low refresh rate of python time
        col_path = os.path.join(self.col1_base, 'dir_1a', 'file_1ab')
        helper.dummy_file(col_path, 20)
        time.sleep(0.1)
        after = datetime.datetime.now()

        self.sfs.add_collection('col1', self.col1_base)
        col1 = self.sfs.get_collection_by_name('col1')

        # Returns a valid NodeStats object
        stats = col1.get_stats(col_path)
        self.assertIsInstance(stats, fs.FSNode.NodeStats)
        dt = datetime.datetime.fromtimestamp(stats.ctime)
        self.assertLess(before, dt)
        self.assertGreater(after, dt)
        self.assertEqual(20, stats.size)

        # Returns None if stats not found
        col_path_invalid = os.path.join(self.col1_base, 'dir_1a', 'file_1ac')
        stats = col1.get_stats(col_path_invalid)
        self.assertIsNone(stats)

    def test_sfs_walk(self):
        self.sfs.add_collection('col1', self.col1_base)

        # Creating dummy files with SFS extension
        sfs_files = [
            os.path.join(self.sfs_base, 'sfs_file1' + core.constants['SFS_FILE_EXTENSION']),
            os.path.join(self.sfs_base, 'col1', 'sfs_file2' + core.constants['SFS_FILE_EXTENSION'])
        ]
        sfs_dir = self.sfs.get_sfs_dir(self.sfs.root)
        for f in sfs_files:
            helper.dummy_file(f)

        # Skips SFS specific files and directories
        for root, *all_nodes in core.SFS.walk(fs.walk_bfs, self.sfs.root):
            for nodes in all_nodes:
                for node in nodes:
                    self.assertFalse(node.path.startswith(sfs_dir))
                    self.assertNotIn(node.path, sfs_files)
