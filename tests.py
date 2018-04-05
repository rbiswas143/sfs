# All VFS Tests

import os
import shutil
import time
import unittest

import config
import core
import dedup_ops
import filter_ops
import freeze_ops
import merge_ops
import save_ops

# Constants
_TEST_DIR = config.TEST_DIR
_HOME_DIR = os.path.join(_TEST_DIR, 'vfs_home')
_VIRTUAL_DIR = os.path.join(_TEST_DIR, 'virtual_dir')
_ACTUAL_DIR = os.path.join(_TEST_DIR, 'actual_dir')


# Test classes


class TestClassA(object):
    pass


class TestClassB(object):
    pass


# Test utils


def create_dummy_file(path, size):
    with open(path, 'wb') as out:
        out.seek(size - 1)
        out.write('\0')


def setup_test_env():
    os.mkdir(_TEST_DIR)
    os.mkdir(_VIRTUAL_DIR)
    os.mkdir(_ACTUAL_DIR)
    os.environ[config.VFS_HOME_ENV_VAR] = os.path.join(_HOME_DIR)
    core.setup_vfs_home()


def cleanup_test_env():
    shutil.rmtree(_TEST_DIR)
    core._invalidate_vfs_cache()
    core._invalidate_collections_cache()
    core._invalidate_discs_cache()
    core._invalidate_save_maps_cache()
    core._vfs_home = None


def create_dir_tree(path, tree):
    for node in tree:
        node_path = os.path.join(path, node['path'])
        if node['type'] == 'dir':
            os.mkdir(node_path)
        else:
            create_dummy_file(node_path, node['size'] if 'size' in node else 10)


def disconnect_path(path):
    dname = '%s_renamed' % os.path.basename(os.path.abspath(path))
    dpath = os.path.join(os.path.dirname(os.path.abspath(path)), dname)
    shutil.move(path, dpath)


def reconnect_path(path):
    dname = '%s_renamed' % os.path.basename(os.path.abspath(path))
    dpath = os.path.join(os.path.dirname(os.path.abspath(path)), dname)
    shutil.move(dpath, path)


# Test Cases


class DictUtilsTests(unittest.TestCase):
    def test_fetch_valid_dict_value(self):
        # Valid value
        dict_ = {'key': 10}
        val = core.fetch_valid_dict_value(dict_, 'key')
        self.assertEqual(val, 10)

        # Default value
        dict_ = {}
        val = core.fetch_valid_dict_value(dict_, 'key', default=20)
        self.assertEqual(val, 20)

        # Valid type
        dict_ = {'key': 'test_string'}
        val = core.fetch_valid_dict_value(dict_, 'key', type_=str)
        self.assertIs(type(val), str)

        # Invalid type
        dict_ = {'key': 'test_string'}
        with self.assertRaises(core.VfsException):
            core.fetch_valid_dict_value(dict_, 'key', type_=int)

        # Validation success
        dict_ = {'key': 10}
        val = core.fetch_valid_dict_value(dict_, 'key', validation=lambda x: x == 10)
        self.assertEqual(val, 10)

        # Validation failure
        dict_ = {'key': 10}
        with self.assertRaises(core.VfsException):
            core.fetch_valid_dict_value(dict_, 'key', validation=lambda x: x == 20)


class DirectoryUtilsTests(unittest.TestCase):
    def setUp(self):
        os.mkdir(_TEST_DIR)

    def tearDown(self):
        shutil.rmtree(_TEST_DIR)

    def test_create_dir(self):
        # Valid
        dir_name = 'valid'
        core.create_dir(_TEST_DIR, dir_name)
        self.assertTrue(os.path.isdir(os.path.join(_TEST_DIR, dir_name)))
        # ignore existing
        with self.assertRaises(OSError):
            core.create_dir(_TEST_DIR, dir_name)
        core.create_dir(_TEST_DIR, dir_name, ignore_existing=True)
        # Create intermediate
        nested_dir = 'nested/dir'
        with self.assertRaises(OSError):
            core.create_dir(_TEST_DIR, nested_dir)
        core.create_dir(_TEST_DIR, nested_dir, create_intermediate=True)
        self.assertTrue(os.path.isdir(os.path.join(_TEST_DIR, nested_dir)))

    def test_del_dir(self):
        # Empty
        dir_name = 'dir1'
        core.create_dir(_TEST_DIR, dir_name)
        core.del_dir(_TEST_DIR, dir_name)
        self.assertFalse(os.path.exists(os.path.join(_TEST_DIR, dir_name)))

        # Not empty
        nested_dir = 'nested_dir'
        nested_path = (_TEST_DIR, dir_name, nested_dir)
        core.create_dir(*nested_path, create_intermediate=True)
        with self.assertRaises(OSError):
            core.del_dir(_TEST_DIR, dir_name)
        self.assertTrue(os.path.exists(os.path.join(*nested_path)))
        core.del_dir(_TEST_DIR, dir_name, del_non_empty=True)
        self.assertFalse(os.path.exists(os.path.join(_TEST_DIR, dir_name)))

        # Invalid path
        invalid_path = (_TEST_DIR, 'invalid_dir')
        with self.assertRaises(OSError):
            core.del_dir(*invalid_path)

    def test_is_parent_dir(self):
        dir1 = os.path.join(_TEST_DIR, 'dir1')
        dir2 = os.path.join(_TEST_DIR, 'dir1_')
        dir2_nested = os.path.join(dir2, 'dir1_nested')
        for dirs in [dir1, dir2, dir2_nested]:
            core.create_dir(dirs)
        self.assertTrue(core.is_parent_dir(dir1, dir1))
        self.assertTrue(core.is_parent_dir(dir2, dir2))
        self.assertTrue(core.is_parent_dir(dir2_nested, dir2_nested))
        self.assertFalse(core.is_parent_dir(dir1, dir2))
        self.assertFalse(core.is_parent_dir(dir2, dir1))
        self.assertFalse(core.is_parent_dir(dir1, dir2_nested))
        self.assertFalse(core.is_parent_dir(dir2_nested, dir1))
        self.assertFalse(core.is_parent_dir(dir2, dir2_nested))
        self.assertTrue(core.is_parent_dir(dir2_nested, dir2))


class MetaDataUtilsTests(unittest.TestCase):
    def setUp(self):
        os.mkdir(_TEST_DIR)

    def tearDown(self):
        shutil.rmtree(_TEST_DIR)

    def test_write_meta_data(self):
        meta_data = TestClassA()
        path = os.path.join(_TEST_DIR, 'meta')
        core.write_meta_data(meta_data, path)
        core.write_meta_data(meta_data, path, valid_class=TestClassA)

    def test_read_meta_data(self):
        path = os.path.join(_TEST_DIR, 'meta')
        # Valid class
        meta_data = TestClassA()
        core.write_meta_data(meta_data, path, valid_class=TestClassA)
        read_data = core.read_meta_data(path, valid_class=TestClassA)
        self.assertIsInstance(read_data, TestClassA)
        # Invalid class
        meta_data = TestClassB()
        core.write_meta_data(meta_data, path, valid_class=TestClassB)
        with self.assertRaises(core.VfsException):
            core.read_meta_data(path, valid_class=TestClassA)


class SymbolicLinkUtilsTests(unittest.TestCase):
    def setUp(self):
        os.mkdir(_TEST_DIR)
        self.actual_file = os.path.join(_TEST_DIR, 'actual_file')
        create_dummy_file(self.actual_file, 100)
        self.assertTrue(os.path.isfile(self.actual_file))

    def tearDown(self):
        shutil.rmtree(_TEST_DIR)

    def test_create_symlink(self):
        link_path = os.path.join(_TEST_DIR, 'link')
        core.create_symlink(self.actual_file, link_path)
        self.assertTrue(os.path.islink(link_path))
        self.assertEqual(os.path.realpath(link_path), os.path.abspath(self.actual_file))
        # override
        with self.assertRaises(core.VfsException):
            core.create_symlink(self.actual_file, link_path)
        core.create_symlink(self.actual_file, link_path, override=True)

    def test_del_symlink(self):
        link_path = os.path.join(_TEST_DIR, 'link')
        core.create_symlink(self.actual_file, link_path)
        core.del_symlink(link_path)
        self.assertFalse(os.path.islink(link_path))
        with self.assertRaises(core.VfsException):
            core.del_symlink(link_path)
        core.del_symlink(link_path, ignore_already_del=True)

    def test_copy_symlink(self):
        link_path = os.path.join(_TEST_DIR, 'link')
        core.create_symlink(self.actual_file, link_path)
        copy_path = os.path.join(_TEST_DIR, 'link-copy')
        core.copy_symlink(link_path, copy_path)
        self.assertTrue(os.path.islink(copy_path))
        self.assertEqual(os.readlink(copy_path), os.path.abspath(self.actual_file))


class VfsHomeUtils(unittest.TestCase):
    def setUp(self):
        os.makedirs(_HOME_DIR)

    def tearDown(self):
        shutil.rmtree(_TEST_DIR)
        core._vfs_home = None

    def test_get_vfs_home(self):
        # Env var
        self.assertIsNone(core._vfs_home)
        os.environ[config.VFS_HOME_ENV_VAR] = _HOME_DIR
        fetched = core.get_vfs_home()
        self.assertEqual(fetched, _HOME_DIR)
        # Cached
        fetched_cache = core.get_vfs_home()
        self.assertIs(fetched, fetched_cache)
        # Default
        core._vfs_home = None
        if config.VFS_HOME_ENV_VAR in os.environ:
            os.environ.pop(config.VFS_HOME_ENV_VAR)
        fetched = core.get_vfs_home()
        self.assertEqual(fetched, config.VFS_HOME_DEFAULT)

    def test_setup_vfs_home(self):
        os.environ[config.VFS_HOME_ENV_VAR] = os.path.join(_TEST_DIR, 'home_path')
        core.setup_vfs_home()
        dirs_to_test = core._get_vfs_home_setup_dirs()
        for dir_path in dirs_to_test:
            self.assertTrue(os.path.isdir(dir_path))
        # Override
        with self.assertRaises(core.VfsException):
            core.setup_vfs_home()
        core.setup_vfs_home(override=True)

    def test_validate_vfs_home(self):
        self.assertFalse(core.validate_vfs_home())
        os.environ[config.VFS_HOME_ENV_VAR] = os.path.join(_TEST_DIR, 'home_path')
        core.setup_vfs_home()
        self.assertTrue(core.validate_vfs_home())


class VfsUtils(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs1 = core.VfsMeta('vfs1', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'vfs1')))
        self.vfs2 = core.VfsMeta('vfs2', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'vfs2')))

    def tearDown(self):
        cleanup_test_env()

    def test_setup_vfs(self):
        core.setup_vfs(self.vfs1.name, _VIRTUAL_DIR)
        dirs_to_test = core._get_vfs_setup_dirs(self.vfs1.name)
        dirs_to_test.append(self.vfs1.virtual_base)
        for dir_path in dirs_to_test:
            self.assertTrue(os.path.isdir(dir_path))
        meta = core.read_meta_data(core.compute_vfs_path(self.vfs1.name), config.VFS_META_FILE,
                                   valid_class=core.VfsMeta)
        self.assertEqual(meta.__dict__, self.vfs1.__dict__)
        # Validations
        cases = [
            (self.vfs1.name, _VIRTUAL_DIR),
            (self.vfs2.name, self.vfs1.virtual_base),
            (None, _VIRTUAL_DIR),
            (self.vfs2.name, self.vfs2.virtual_base),
        ]
        for case in cases:
            with self.assertRaises(core.VfsException):
                core.setup_vfs(*case)

    def test_del_vfs(self):
        core.setup_vfs(self.vfs1.name, _VIRTUAL_DIR)
        core.del_vfs(self.vfs1.name)
        dirs_to_test = core._get_vfs_setup_dirs(self.vfs1.name)
        dirs_to_test.append(self.vfs1.virtual_base)
        for dir_path in dirs_to_test:
            self.assertFalse(os.path.isdir(dir_path))
        self.assertIsNone(core.get_vfs_by_name(self.vfs1.name))
        # Already deleted
        with self.assertRaises(core.VfsException):
            core.del_vfs(self.vfs1.name)

    def test_get_all_vfs(self):
        core.setup_vfs(self.vfs1.name, _VIRTUAL_DIR)
        core.setup_vfs(self.vfs2.name, _VIRTUAL_DIR)
        all_vfs = core.get_all_vfs()
        self.assertEqual(len(all_vfs), 2)
        all_vfs.sort(key=lambda vfs: vfs.name)
        self.assertEqual(map(lambda vfs: vfs.__dict__, all_vfs), [self.vfs1.__dict__, self.vfs2.__dict__])
        cached = core.get_all_vfs()
        self.assertIs(all_vfs, cached)

    def test_get_all_vfs_by_name(self):
        core.setup_vfs(self.vfs1.name, _VIRTUAL_DIR)
        core.setup_vfs(self.vfs2.name, _VIRTUAL_DIR)
        vfs_by_name = core.get_all_vfs_by_name()
        self.assertEqual(len(vfs_by_name), 2)
        self.assertEqual(vfs_by_name[self.vfs1.name].__dict__, self.vfs1.__dict__)
        self.assertEqual(vfs_by_name[self.vfs2.name].__dict__, self.vfs2.__dict__)

    def test_get_vfs_by_name(self):
        core.setup_vfs(self.vfs1.name, _VIRTUAL_DIR)
        vfs = core.get_vfs_by_name(self.vfs1.name)
        self.assertEqual(vfs.__dict__, self.vfs1.__dict__)
        # Invalid
        vfs = core.get_vfs_by_name('invalid_name')
        self.assertIsNone(vfs)

    def test_get_vfs_by_path(self):
        core.setup_vfs(self.vfs1.name, _VIRTUAL_DIR)
        vfs = core.get_vfs_by_path(self.vfs1.virtual_base)
        self.assertEqual(vfs.__dict__, self.vfs1.__dict__)
        sub_path = 'sub/path'
        vfs = core.get_vfs_by_path(os.path.join(self.vfs1.virtual_base, sub_path))
        self.assertEqual(vfs.__dict__, self.vfs1.__dict__)
        vfs = core.get_vfs_by_path(os.path.join(_VIRTUAL_DIR, sub_path))
        self.assertIsNone(vfs)


class CollectionUtils(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        # Collections
        self.col1 = core.CollectionMeta('col1', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col1')),
                                        os.path.abspath(os.path.join(self.vfs.virtual_base, 'col1')))
        os.mkdir(self.col1.actual_base)
        self.col1_file = os.path.join(self.col1.actual_base, 'file1')
        create_dummy_file(self.col1_file, 100)
        self.col1_dir = os.path.join(self.col1.actual_base, 'dir1')
        os.mkdir(self.col1_dir)
        self.col2 = core.CollectionMeta('col2', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col2')),
                                        os.path.abspath(os.path.join(self.vfs.virtual_base, 'col2')))
        os.mkdir(self.col2.actual_base)
        self.col2_file = os.path.join(self.col2.actual_base, 'file2')
        create_dummy_file(self.col2_file, 100)
        self.col2_dir = os.path.join(self.col2.actual_base, 'dir2')
        os.mkdir(self.col2_dir)

    def tearDown(self):
        cleanup_test_env()

    def _check_file_stats(self, stats, col, col_file):
        self.assertEqual(len(stats), 1)
        file_stat = stats[col_file]
        self.assertIs(file_stat.__class__, core.FileStat)
        self.assertEqual(col_file, file_stat.actual_path)
        reconnect_path(col.actual_base)
        test_stat = os.stat(col_file)
        disconnect_path(col.actual_base)
        self.assertEqual(test_stat.st_size, file_stat.size)

    def test_setup_collection(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        # Meta
        col_dir_path = core.compute_collection_path(self.col1.name)
        meta = core.read_meta_data(col_dir_path, config.COLLECTION_META_FILE, valid_class=core.CollectionMeta)
        self.assertEqual(meta.__dict__, self.col1.__dict__)
        # Virtual dirs and files
        virtual_dir1 = os.path.join(self.vfs.virtual_base, self.col1.name, os.path.basename(self.col1_dir))
        self.assertTrue(os.path.isdir(virtual_dir1))
        virtual_file1 = os.path.join(self.vfs.virtual_base, self.col1.name, os.path.basename(self.col1_file))
        self.assertTrue(os.path.islink(virtual_file1))
        self.assertEqual(self.col1_file, os.readlink(virtual_file1))
        # Validations
        cases = [
            (self.col1.name, self.col2.actual_base),
            (self.col2.name, self.col1_dir),
            (None, self.col2.actual_base),
            (self.col2.name, os.path.join(self.col2.actual_base, 'invalid/dir')),
        ]
        for case in cases:
            with self.assertRaises(core.VfsException):
                core.setup_collection(*case)
        # File stats
        stats = core.read_meta_data(col_dir_path, config.COLLECTION_STATS_FILE)
        self._check_file_stats(stats, self.col1, self.col1_file)

    def test_sync_collection(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        # Add files
        col1_file_new_1 = os.path.join(self.col1.actual_base, 'col1_file_new_1')
        create_dummy_file(col1_file_new_1, 10)
        col1_file_new_1_virtual = os.path.join(self.col1.virtual_base_original, 'col1_file_new_1')
        col1_dir_new = os.path.join(self.col1.actual_base, 'col1_dir_new')
        os.mkdir(col1_dir_new)
        col1_file_new_2 = os.path.join(col1_dir_new, 'col1_file_new_2')
        create_dummy_file(col1_file_new_2, 10)
        col1_file_new_2_virtual = os.path.join(self.col1.virtual_base_original, 'col1_dir_new/col1_file_new_2')
        core.sync_collection(self.col1.name)
        self.assertTrue(os.path.islink(col1_file_new_1_virtual))
        self.assertTrue(os.path.islink(col1_file_new_2_virtual))
        stats = core.get_file_stats_for_collection(self.col1.name)
        self.assertIn(col1_file_new_1, stats)
        self.assertIn(col1_file_new_2, stats)
        core._invalidate_collections_cache()
        core.do_pending_meta_writes()
        # Delete files
        os.unlink(col1_file_new_1)
        os.unlink(col1_file_new_2)
        core.sync_collection(self.col1.name)
        self.assertFalse(os.path.islink(col1_file_new_1_virtual))
        self.assertFalse(os.path.islink(col1_file_new_2_virtual))
        stats = core.get_file_stats_for_collection(self.col1.name)
        self.assertNotIn(col1_file_new_1, stats)
        self.assertNotIn(col1_file_new_2, stats)

    def test_get_all_collections(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        core.setup_collection(self.col2.name, self.col2.actual_base)
        disconnect_path(self.col2.actual_base)
        all_cols = core.get_all_collections()
        self.assertEqual(len(all_cols), 2)
        all_cols.sort(key=lambda col: col.name)
        self.assertEqual(map(lambda col: col.__dict__, all_cols), [self.col1.__dict__, self.col2.__dict__])
        cached = core.get_all_collections()
        self.assertIs(all_cols, cached)

    def test_get_all_collections_by_name(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        core.setup_collection(self.col2.name, self.col2.actual_base)
        disconnect_path(self.col2.actual_base)
        cols_by_name = core.get_all_collections_by_name()
        self.assertEqual(len(cols_by_name), 2)
        self.assertEqual(cols_by_name[self.col1.name].__dict__, self.col1.__dict__)
        self.assertEqual(cols_by_name[self.col2.name].__dict__, self.col2.__dict__)

    def test_get_collection_by_name(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        col = core.get_collection_by_name(self.col1.name)
        self.assertEqual(col.__dict__, self.col1.__dict__)

    def test_get_collection_by_path(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        col = core.get_collection_by_path(self.col1.actual_base)
        self.assertEqual(col.__dict__, self.col1.__dict__)
        # Sub path
        col = core.get_collection_by_path(self.col1_file)
        self.assertEqual(col.__dict__, self.col1.__dict__)
        # Invalid Path
        col = core.get_collection_by_path(os.path.join(_ACTUAL_DIR))
        self.assertIsNone(col)

    def test_get_file_stats_for_collection(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        stats = core.get_file_stats_for_collection(self.col1.name)
        self._check_file_stats(stats, self.col1, self.col1_file)
        # Cache
        cached_stats = core.get_file_stats_for_collection(self.col1.name)
        self.assertIs(stats, cached_stats)

    def test_get_file_stats_for_all_collections(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        core.setup_collection(self.col2.name, self.col2.actual_base)
        disconnect_path(self.col2.actual_base)
        stats = core.get_file_stats_for_all_collections()
        self.assertEqual(len(stats), 2)
        test_files = [self.col1_file, self.col2_file]
        for file_ in test_files:
            self.assertIn(file_, stats)

    def test_get_file_stats_for_actual_path(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        test_files = [self.col1_file]
        stats = {}
        for file_ in test_files:
            stat = core.get_file_stats_for_actual_path(file_)
            stats[file_] = stat
        self._check_file_stats(stats, self.col1, self.col1_file)

    def test_get_file_stats_for_symlink(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        stats = {}
        for root, dirs, files in os.walk(self.col1.virtual_base_original):
            # dir_stat = core.get_file_stats_for_virtual_dir(root)
            # stats[dir_stat.actual_path] = dir_stat
            for file_ in files:
                file_stat = core.get_file_stats_for_symlink(os.path.join(root, file_))
                stats[file_stat.actual_path] = file_stat
        self._check_file_stats(stats, self.col1, self.col1_file)

    def test_del_file_stats(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        stats = core.get_file_stats_for_all_collections()
        self.assertIn(self.col1_file, stats)
        core.del_file_stats(self.col1_file)
        stats = core.get_file_stats_for_all_collections()
        self.assertNotIn(self.col1_file, stats)
        core._invalidate_collections_cache()
        core.do_pending_meta_writes()
        stats = core.get_file_stats_for_all_collections()
        self.assertNotIn(self.col1_file, stats)

    def test_add_file_stats(self):
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        stats = core.get_file_stats_for_all_collections()
        new_file = os.path.join(self.col1.actual_base, 'new/file')
        self.assertNotIn(new_file, stats)
        new_stats = core.FileStat(new_file, None, None)
        core.add_file_stats(new_stats)
        stats = core.get_file_stats_for_all_collections()
        self.assertIn(new_file, stats)
        core._invalidate_collections_cache()
        core.do_pending_meta_writes()
        stats = core.get_file_stats_for_all_collections()
        self.assertIn(new_file, stats)


class DiscUtils(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        self.disc1 = core.DiscMeta('disc1', os.path.abspath(os.path.join(_ACTUAL_DIR, 'disc1')))
        os.mkdir(self.disc1.disc_base)
        self.disc2 = core.DiscMeta('disc2', os.path.abspath(os.path.join(_ACTUAL_DIR, 'disc2')), 1024)
        os.mkdir(self.disc2.disc_base)

    def tearDown(self):
        cleanup_test_env()

    def test_add_disc(self):
        # Default size
        core.add_disc(self.disc1.name, self.disc1.disc_base)
        disc1 = core.get_disc_by_name(self.disc1.name)
        self.assertEqual(disc1.__dict__, self.disc1.__dict__)
        # Capacity
        core.add_disc(self.disc2.name, self.disc2.disc_base, self.disc2.capacity)
        disc2 = core.get_disc_by_name(self.disc2.name)
        self.assertEqual(disc2.__dict__, self.disc2.__dict__)
        # Invalid
        cases = [
            [self.disc1.name, self.disc1.disc_base],  # Existing name
            ['new_disc_name', self.disc1.disc_base],  # Existing path
            [None, self.disc1.disc_base],  # Invalid name
            ['new_disc_name', 'invalid/path'],  # Invalid path
            ['new_disc_name', _VIRTUAL_DIR, -20],  # Invalid capacity
        ]
        for case in cases:
            with self.assertRaises(core.VfsException):
                core.add_disc(*case)

    def test_del_disc(self):
        core.add_disc(self.disc1.name, self.disc1.disc_base)
        discs = core.get_all_discs()
        self.assertEqual(len(discs), 1)
        self.assertEqual(discs[0].__dict__, self.disc1.__dict__)
        core.del_disc(self.disc1.name)
        discs = core.get_all_discs()
        self.assertEqual(len(discs), 0)
        with self.assertRaises(core.VfsException):
            core.del_disc(self.disc1.name)

    def test_get_all_discs(self):
        discs = core.get_all_discs()
        self.assertEqual(len(discs), 0)
        core.add_disc(self.disc1.name, self.disc1.disc_base, self.disc1.capacity)
        core.add_disc(self.disc2.name, self.disc2.disc_base, self.disc2.capacity)
        discs = core.get_all_discs()
        self.assertEqual(len(discs), 2)
        for disc in discs:
            matched = False
            if disc.__dict__ == self.disc1.__dict__ or disc.__dict__ == self.disc2.__dict__:
                matched = True
            self.assertTrue(matched)

    def test_get_all_discs_by_name(self):
        discs = core.get_all_discs_by_name()
        self.assertEqual(len(discs), 0)
        core.add_disc(self.disc1.name, self.disc1.disc_base, self.disc1.capacity)
        core.add_disc(self.disc2.name, self.disc2.disc_base, self.disc2.capacity)
        discs = core.get_all_discs_by_name()
        self.assertEqual(len(discs), 2)
        self.assertEqual(discs[self.disc1.name].__dict__, self.disc1.__dict__)
        self.assertEqual(discs[self.disc2.name].__dict__, self.disc2.__dict__)

    def test_get_disc_by_name(self):
        disc = core.get_disc_by_name(self.disc1.name)
        self.assertIsNone(disc)
        core.add_disc(self.disc1.name, self.disc1.disc_base, self.disc1.capacity)
        disc = core.get_disc_by_name(self.disc1.name)
        self.assertEqual(disc.__dict__, self.disc1.__dict__)

    def test_get_disc_by_path(self):
        disc = core.get_disc_by_path(self.disc1.disc_base)
        self.assertIsNone(disc)
        core.add_disc(self.disc1.name, self.disc1.disc_base, self.disc1.capacity)
        disc = core.get_disc_by_path(self.disc1.disc_base)
        self.assertEqual(disc.__dict__, self.disc1.__dict__)


class SaveMapUtils(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        # Collections
        self.col1 = core.CollectionMeta('col1', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col1')),
                                        os.path.abspath(os.path.join(self.vfs.virtual_base, 'col1')))
        os.mkdir(self.col1.actual_base)
        self.col1_file = os.path.join(self.col1.actual_base, 'col1_file')
        create_dummy_file(self.col1_file, 10)
        core.setup_collection(self.col1.name, self.col1.actual_base)
        disconnect_path(self.col1.actual_base)
        self.col2 = core.CollectionMeta('col2', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col2')),
                                        os.path.abspath(os.path.join(self.vfs.virtual_base, 'col2')))
        os.mkdir(self.col2.actual_base)
        core.setup_collection(self.col2.name, self.col2.actual_base)
        disconnect_path(self.col2.actual_base)
        self.save_map1 = core.SaveMapMeta(self.col1.virtual_base_original, self.col2.actual_base)
        self.save_map2 = core.SaveMapMeta(self.col2.virtual_base_original, self.col1.actual_base)

    def tearDown(self):
        cleanup_test_env()

    def test_add_save_map(self):
        # Valid map
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        core.get_all_save_maps()
        save_maps = core.get_all_save_maps()
        self.assertEqual(len(save_maps), 1)
        self.assertEqual(save_maps[0].__dict__, self.save_map1.__dict__)
        # invalid
        cases = [
            [_VIRTUAL_DIR, self.save_map2.actual_dir],  # Invalid collection
            [self.save_map1.virtual_dir, self.save_map2.actual_dir],  # Repeated virtual
            [self.save_map2.virtual_dir, self.save_map1.actual_dir],  # Repeated actual
        ]
        for case in cases:
            with self.assertRaises(core.VfsException):
                core.add_save_map(*case)

    def test_del_all_save_maps(self):
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        core.add_save_map(self.save_map2.virtual_dir, self.save_map2.actual_dir)
        core.get_all_save_maps()
        save_maps = core.get_all_save_maps()
        self.assertEqual(len(save_maps), 2)
        core.del_all_save_maps()
        save_maps = core.get_all_save_maps()
        self.assertEqual(len(save_maps), 0)

    def test_get_all_save_maps(self):
        save_maps = core.get_all_save_maps()
        self.assertEqual(len(save_maps), 0)
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        core.add_save_map(self.save_map2.virtual_dir, self.save_map2.actual_dir)
        core.get_all_save_maps()
        save_maps = core.get_all_save_maps()
        self.assertEqual(len(save_maps), 2)
        for save_map in save_maps:
            matched = False
            if save_map.__dict__ == self.save_map1.__dict__ or save_map.__dict__ == self.save_map2.__dict__:
                matched = True
            self.assertTrue(matched)

    def test_get_save_map_by_virtual_path(self):
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        save_map = core.get_save_map_by_virtual_path(self.save_map1.virtual_dir)
        self.assertEqual(save_map.__dict__, self.save_map1.__dict__)

    def test_get_save_map_by_actual_path(self):
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        save_map = core.get_save_map_by_actual_path(self.save_map1.actual_dir)
        self.assertEqual(save_map.__dict__, self.save_map1.__dict__)

    def test_convert_virtual_to_actual_using_save_map(self):
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        core.add_save_map(self.save_map2.virtual_dir, self.save_map2.actual_dir)
        virtual_path = os.path.join(self.vfs.virtual_base, 'col1', 'col1_file')
        expected_dest_path = os.path.join(self.col2.actual_base, 'col1_file')
        self.assertEqual(expected_dest_path, core.convert_virtual_to_actual_using_save_map(virtual_path))

    def test_convert_actual_to_virtual_using_save_map(self):
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        core.add_save_map(self.save_map2.virtual_dir, self.save_map2.actual_dir)
        actual_path = os.path.join(self.col2.actual_base, 'col1_file')
        expected_virtual_path = os.path.join(self.vfs.virtual_base, 'col1', 'col1_file')
        self.assertEqual(expected_virtual_path, core.convert_actual_to_virtual_using_save_map(actual_path))


class BackupUtilsTests(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        self.col = core.CollectionMeta('col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col')),
                                       os.path.abspath(os.path.join(self.vfs.virtual_base, 'col')))
        os.mkdir(self.col.actual_base)
        self.col_file = os.path.join(self.col.actual_base, 'col_file')
        create_dummy_file(self.col_file, 10)
        self.col_dir = os.path.join(self.col.actual_base, 'col_dir')
        os.mkdir(self.col_dir)
        core.setup_collection(self.col.name, self.col.actual_base)
        disconnect_path(self.col.actual_base)

    def tearDown(self):
        cleanup_test_env()
        core._invalidate_backup_cache()

    def test_create_backup(self):
        backup_name = core.create_backup(self.vfs.name, 'Test Message')
        all_backups = core.list_backups()
        self.assertEqual(len(all_backups), 1)
        backup_meta = all_backups[0]
        self.assertEqual(backup_meta.vfs, self.vfs.name)
        self.assertEqual(backup_meta.virtual_path, self.vfs.virtual_base)
        self.assertEqual(backup_meta.name, backup_name)
        self.assertEqual(backup_meta.comment, 'Test Message')
        time_now = time.time()
        self.assertTrue(time_now - 100 < backup_meta.created < time_now + 100)
        backup_dir = core.compute_backup_path(backup_meta.name)
        self.assertTrue(os.path.isdir(backup_dir))
        meta_path = os.path.join(backup_dir, config.BACKUP_META_FILE)
        self.assertTrue(os.path.isfile(meta_path))
        vfs_path_backup = os.path.join(backup_dir, config.BACKUP_VFS_DIR)
        self.assertTrue(os.path.isdir(vfs_path_backup))
        virtual_path_backup = os.path.join(backup_dir, config.BACKUP_VIRTUAL_DIR)
        self.assertTrue(os.path.isdir(virtual_path_backup))

    def test_del_backup(self):
        core.create_backup(self.vfs.name, None)
        all_backups = core.list_backups()
        self.assertEqual(len(all_backups), 1)
        core.create_backup(self.vfs.name, 'Test Message')
        all_backups = core.list_backups()
        self.assertEqual(len(all_backups), 2)
        core.del_backup(all_backups[0].name)
        all_backups_del = core.list_backups()
        self.assertEqual(len(all_backups_del), 1)
        self.assertEqual(all_backups_del[0].name, all_backups[1].name)
        core.del_backup(all_backups_del[0].name)
        all_backups_del = core.list_backups()
        self.assertEqual(len(all_backups_del), 0)

    def test_list_backups(self):
        vfs2 = core.VfsMeta('vfs2', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'vfs2')))
        core.setup_vfs(vfs2.name, _VIRTUAL_DIR)
        core.create_backup(self.vfs.name, None)
        core.create_backup(vfs2.name, None)
        core.create_backup(self.vfs.name, 'Test Message')
        all_backups = core.list_backups()
        self.assertEqual(len(all_backups), 3)
        all_backups.sort(key=lambda x: x.name)
        self.assertIn(self.vfs.name, all_backups[0].name)
        self.assertIn(self.vfs.name, all_backups[1].name)
        self.assertIn(vfs2.name, all_backups[2].name)
        self.assertTrue(all_backups[0].vfs == all_backups[1].vfs == self.vfs.name)

    def test_restore_backup_vfs_modified(self):
        core.create_backup(self.vfs.name, 'Test Message')
        col_dir_virtual = os.path.join(self.col.virtual_base_original, 'col_dir')
        os.rmdir(col_dir_virtual)
        col_file_virtual = os.path.join(self.col.virtual_base_original, 'col_file')
        col_file_copy_virtual = os.path.join(self.col.virtual_base_original, 'col_file_copy')
        core.copy_symlink(col_file_virtual, col_file_copy_virtual)
        backup = core.list_backups()[0]
        core.restore_backup(backup.name)
        self.assertTrue(os.path.isdir(col_dir_virtual))
        self.assertFalse(os.path.islink(col_file_copy_virtual))
        # Restore backup again
        core.restore_backup(backup.name)
        self.assertTrue(os.path.isdir(col_dir_virtual))
        self.assertFalse(os.path.islink(col_file_copy_virtual))

    def test_restore_backup_vfs_deleted(self):
        core.create_backup(self.vfs.name, None)
        backup = core.list_backups()[0]
        shutil.rmtree(self.vfs.virtual_base)
        vfs_path = core.compute_vfs_path(self.vfs.name)
        shutil.rmtree(vfs_path)
        core.restore_backup(backup.name)
        self.assertTrue(os.path.isdir(vfs_path))
        self.assertTrue(os.path.isdir(self.vfs.virtual_base))
        self.assertTrue(os.path.islink(os.path.join(self.col.virtual_base_original, 'col_file')))
        self.assertTrue(os.path.isdir(os.path.join(self.col.virtual_base_original, 'col_dir')))


class VirtualPathPropsUtils(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        self.col = core.CollectionMeta('col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col')),
                                       os.path.abspath(os.path.join(self.vfs.virtual_base, 'col')))
        os.mkdir(self.col.actual_base)
        self.col_file = os.path.join(self.col.actual_base, 'col_file')
        create_dummy_file(self.col_file, 10)
        self.col_dir = os.path.join(self.col.actual_base, 'col_dir')
        os.mkdir(self.col_dir)
        core.setup_collection(self.col.name, self.col.actual_base)
        disconnect_path(self.col.actual_base)
        self.col_dir_virtual = os.path.join(self.col.virtual_base_original, 'col_dir')
        self.col_file_virtual = os.path.join(self.col.virtual_base_original, 'col_file')
        self.prop = 'test_prop'
        self.value = 'test_value'

    def tearDown(self):
        cleanup_test_env()

    def test_virtual_path_prop_file(self):
        self.assertIsNone(core.get_virtual_path_prop(self.prop, self.col_file_virtual))
        core.set_virtual_path_prop(self.prop, self.value, self.col_file_virtual)
        self.assertTrue(os.path.isfile(core.compute_virtual_file_prop_path(self.col_file_virtual)))
        self.assertEqual(core.get_virtual_path_prop(self.prop, self.col_file_virtual), self.value)

    def test_virtual_path_prop_dir(self):
        self.assertIsNone(core.get_virtual_path_prop(self.prop, self.col_dir_virtual))
        core.set_virtual_path_prop(self.prop, self.value, self.col_dir_virtual)
        self.assertTrue(os.path.isfile(core.compute_virtual_dir_prop_path(self.col_dir_virtual)))
        self.assertEqual(core.get_virtual_path_prop(self.prop, self.col_dir_virtual), self.value)

    def test_virtual_path_prop_validations(self):
        # invalid file
        with self.assertRaises(core.VfsException):
            core.set_virtual_path_prop('prop', 'value', 'invalid/path')
        with self.assertRaises(core.VfsException):
            core.get_virtual_path_prop('prop', 'invalid/path')
        # Override
        core.set_virtual_path_prop(self.prop, self.value, self.col_dir_virtual)
        core.set_virtual_path_prop(self.prop, self.value, self.col_dir_virtual)
        with self.assertRaises(core.VfsException):
            core.set_virtual_path_prop(self.prop, self.value, self.col_dir_virtual, override=False)


class GenericUtilsTests(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)

    def tearDown(self):
        cleanup_test_env()

    def test_get_readable_size(self):
        tests = [
            (10, '10.00 Bytes'),
            (10 * 1024, '10.00 kB'),
            (10 * (1024 ** 2), '10.00 MB'),
            (10 * (1024 ** 3), '10.00 GB'),
            ((10 * (1024 ** 3) + (1000 ** 3)), '10.93 GB'),
            (10 * (1024 ** 4), '10240.00 GB')
        ]
        for test, res in tests:
            self.assertEqual(core.get_readable_size(test), res)

    def test_get_virtual_dir_size(self):
        col = core.CollectionMeta('test_col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'test_col')),
                                  os.path.abspath(os.path.join(self.vfs.virtual_base, 'test_col')))
        os.mkdir(col.actual_base)
        col_dir = os.path.join(col.actual_base, 'dir')
        os.mkdir(col_dir)
        col_file1 = os.path.join(col_dir, 'file1')
        col_file1_size = 10240
        create_dummy_file(col_file1, col_file1_size)
        col_file2 = os.path.join(col_dir, 'file2')
        col_file2_size = (1024 ** 2) + 100000
        create_dummy_file(col_file2, col_file2_size)
        core.setup_collection(col.name, col.actual_base)
        disconnect_path(col.actual_base)
        self.assertEqual(core.get_virtual_dir_size(self.vfs.virtual_base), col_file1_size + col_file2_size)

    def test_get_actual_dir_size(self):
        col = core.CollectionMeta('test_col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'test_col')),
                                  os.path.abspath(os.path.join(self.vfs.virtual_base, 'test_col')))
        os.mkdir(col.actual_base)
        col_dir = os.path.join(col.actual_base, 'dir')
        os.mkdir(col_dir)
        col_file1 = os.path.join(col_dir, 'file1')
        col_file1_size = 10240
        create_dummy_file(col_file1, col_file1_size)
        col_file2 = os.path.join(col_dir, 'file2')
        col_file2_size = (1024 ** 2) + 100000
        create_dummy_file(col_file2, col_file2_size)
        self.assertEqual(core.get_actual_dir_size(col.actual_base), col_file1_size + col_file2_size)

    def test_vfs_walk(self):
        col = core.CollectionMeta('test_col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'test_col')),
                                  os.path.abspath(os.path.join(self.vfs.virtual_base, 'test_col')))
        os.mkdir(col.actual_base)
        col_dir = os.path.join(col.actual_base, 'dir')
        os.mkdir(col_dir)
        col_file = os.path.join(col_dir, 'file1')
        create_dummy_file(col_file, 10)
        core.setup_collection(col.name, col.actual_base)
        disconnect_path(col.actual_base)
        vfs_file = os.path.join(col.virtual_base_original, 'dir', 'test.json.vfs')
        create_dummy_file(vfs_file, 10)
        virtual_files = []
        for root, dirs, files in core.vfs_walk(self.vfs.virtual_base):
            virtual_files += [os.path.join(root, file_) for file_ in files]
        self.assertTrue(vfs_file not in virtual_files)


class FreezeUtilsTests(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        self.col = core.CollectionMeta('col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col')),
                                       os.path.abspath(os.path.join(self.vfs.virtual_base, 'col')))
        os.mkdir(self.col.actual_base)
        self.col_dir_parent = os.path.join(self.col.actual_base, 'col_dir_parent')
        os.mkdir(self.col_dir_parent)
        self.col_dir_child = os.path.join(self.col_dir_parent, 'col_dir_child')
        os.mkdir(self.col_dir_child)
        core.setup_collection(self.col.name, self.col.actual_base)
        disconnect_path(self.col.actual_base)
        self.col_dir_parent_virtual = os.path.join(self.col.virtual_base_original, 'col_dir_parent')
        self.col_dir_child_virtual = os.path.join(self.col_dir_parent_virtual, 'col_dir_child')

    def tearDown(self):
        cleanup_test_env()

    def test_is_frozen(self):
        self.assertFalse(freeze_ops.is_frozen(self.col_dir_parent_virtual))
        self.assertFalse(freeze_ops.is_frozen(self.col_dir_child_virtual))
        freeze_ops.freeze_dir(self.col_dir_parent_virtual)
        self.assertTrue(freeze_ops.is_frozen(self.col_dir_parent_virtual))
        self.assertFalse(freeze_ops.is_frozen(self.col_dir_child_virtual))
        freeze_ops.unfreeze_dir(self.col_dir_parent_virtual)
        freeze_ops.freeze_dir(self.col_dir_child_virtual)
        self.assertFalse(freeze_ops.is_frozen(self.col_dir_parent_virtual))
        self.assertTrue(freeze_ops.is_frozen(self.col_dir_child_virtual))

    def test_get_frozen_parent(self):
        self.assertIsNone(freeze_ops.get_frozen_parent(self.col_dir_parent_virtual))
        self.assertIsNone(freeze_ops.get_frozen_parent(self.col_dir_child_virtual))
        freeze_ops.freeze_dir(self.col_dir_parent_virtual)
        self.assertEqual(freeze_ops.get_frozen_parent(self.col_dir_parent_virtual), self.col_dir_parent_virtual)
        self.assertEqual(freeze_ops.get_frozen_parent(self.col_dir_child_virtual), self.col_dir_parent_virtual)
        freeze_ops.unfreeze_dir(self.col_dir_parent_virtual)
        freeze_ops.freeze_dir(self.col_dir_child_virtual)
        self.assertIsNone(freeze_ops.get_frozen_parent(self.col_dir_parent_virtual))
        self.assertEqual(freeze_ops.get_frozen_parent(self.col_dir_child_virtual), self.col_dir_child_virtual)


class DedupUtilsTest(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        # VFS
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        # Collection
        self.col = core.CollectionMeta('col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col')),
                                       os.path.abspath(os.path.join(self.vfs.virtual_base, 'col')))
        os.mkdir(self.col.actual_base)
        self.col_file1 = os.path.join(self.col.actual_base, 'file1')
        create_dummy_file(self.col_file1, 100)
        self.col_dir1 = os.path.join(self.col.actual_base, 'dir1')
        os.mkdir(self.col_dir1)
        self.col_file1_dup = os.path.join(self.col_dir1, 'file1')
        create_dummy_file(self.col_file1_dup, 100)
        core.setup_collection(self.col.name, self.col.actual_base)
        # Duplicates
        self.duplicates = [
            [
                {
                    "path": os.path.relpath(self.col_file1, self.col.actual_base),
                    "created": time.ctime(os.stat(self.col_file1).st_ctime),
                    "modified": time.ctime(os.stat(self.col_file1).st_mtime),
                    "keep": 1
                },
                {
                    "path": os.path.relpath(self.col_file1_dup, self.col.actual_base),
                    "created": time.ctime(os.stat(self.col_file1_dup).st_ctime),
                    "modified": time.ctime(os.stat(self.col_file1_dup).st_mtime),
                    "keep": 1
                }
            ]
        ]
        disconnect_path(self.col.actual_base)

    def tearDown(self):
        cleanup_test_env()

    def test_get_duplicates(self):
        duplicates = dedup_ops.get_duplicates(self.col.virtual_base_original)
        self.assertEqual(duplicates, self.duplicates)

    def test_get_duplicates_frozen(self):
        col_dir1_virtual = os.path.join(self.col.virtual_base_original, 'dir1')
        freeze_ops.freeze_dir(col_dir1_virtual)
        duplicates = dedup_ops.get_duplicates(self.col.virtual_base_original)
        self.assertEqual(duplicates, [])

    def test_del_duplicates(self):
        duplicates = dedup_ops.get_duplicates(self.col.virtual_base_original)
        duplicates[0][1]['keep'] = 0
        del_count = dedup_ops.del_duplicates(self.col.virtual_base_original, duplicates)
        self.assertEqual(del_count, 1)
        left_dirs = []
        left_files = []
        for root, dirs, files in os.walk(self.col.virtual_base_original):
            left_dirs.append(root)
            left_files += [os.path.join(root, file_) for file_ in files]
        self.assertEqual(left_dirs,
                         [self.col.virtual_base_original, os.path.join(self.col.virtual_base_original, 'dir1')])
        self.assertEqual(left_files, [os.path.join(self.col.virtual_base_original, 'file1')])


class MergeUtilsTests(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        # VFS
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        # Collection
        self.col = core.CollectionMeta('col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col')),
                                       os.path.abspath(os.path.join(self.vfs.virtual_base, 'col')))
        os.mkdir(self.col.actual_base)
        create_dir_tree(self.col.actual_base, [
            {
                'type': 'dir',
                'path': 'dir_src'
            },
            {
                'type': 'dir',
                'path': 'dir_dest'
            },
            {
                'type': 'dir',
                'path': 'dir_src/dir_common'
            },
            {
                'type': 'dir',
                'path': 'dir_dest/dir_common'
            },
            {
                'type': 'dir',
                'path': 'dir_src/dir_unique'
            },
            {
                'type': 'file',
                'path': 'dir_src/file_common',
                'size': 100
            },
            {
                'type': 'file',
                'path': 'dir_dest/file_common',
                'size': 200
            },
            {
                'type': 'file',
                'path': 'dir_src/file_unique_src',
                'size': 100
            },
            {
                'type': 'file',
                'path': 'dir_dest/file_unique_dest',
                'size': 100
            }
        ])
        core.setup_collection(self.col.name, self.col.actual_base)
        src_common_file = os.path.abspath(os.path.join(self.col.actual_base, 'dir_src', 'file_common'))
        dest_common_file = os.path.abspath(os.path.join(self.col.actual_base, 'dir_dest', 'file_common'))
        self.conflicts = [
            {
                "rel_path": 'file_common',
                "source": {
                    "actual_path": src_common_file,
                    "size": '100.00 Bytes',
                    "is_symlink": True,
                    "created": time.ctime(os.stat(src_common_file).st_ctime),
                    "modified": time.ctime(os.stat(src_common_file).st_mtime),
                    "keep": 1,
                },
                "dest": {
                    "actual_path": dest_common_file,
                    "size": '200.00 Bytes',
                    "is_symlink": True,
                    "created": time.ctime(os.stat(dest_common_file).st_ctime),
                    "modified": time.ctime(os.stat(dest_common_file).st_mtime),
                    "keep": 1
                },
                "equal_size": False
            }
        ]
        disconnect_path(self.col.actual_base)

    def tearDown(self):
        cleanup_test_env()

    def test_get_merge_conflicts(self):
        conflicts = merge_ops.get_merge_conflicts(os.path.join(self.col.virtual_base_original, 'dir_src'),
                                                  os.path.join(self.col.virtual_base_original, 'dir_dest'))
        self.assertEqual(len(conflicts), 1)
        conflicts[0]['source'].pop('rename')
        self.assertEqual(conflicts, self.conflicts)

    def test_get_merge_conflicts_invalid(self):
        source_path = os.path.join(self.col.virtual_base_original, 'dir_src')
        dest_path = os.path.join(self.col.virtual_base_original, 'dir_dest')
        invalid_file = os.path.join(self.col.virtual_base_original, 'dir_dest/dir_unique')
        create_dummy_file(invalid_file, 10)
        with self.assertRaises(core.VfsException):
            merge_ops.get_merge_conflicts(source_path, dest_path)

    def test_get_merge_conflicts_frozen(self):
        source_path = os.path.join(self.col.virtual_base_original, 'dir_src')
        dest_path = os.path.join(self.col.virtual_base_original, 'dir_dest')
        dir_common_source_virtual = os.path.join(self.col.virtual_base_original, 'dir_src/dir_common')
        freeze_ops.freeze_dir(dir_common_source_virtual)
        with self.assertRaises(core.VfsException):
            merge_ops.get_merge_conflicts(source_path, dest_path)

    def test_resolve_merge_conflicts(self):
        source_path = os.path.join(self.col.virtual_base_original, 'dir_src')
        dest_path = os.path.join(self.col.virtual_base_original, 'dir_dest')
        conflicts = merge_ops.get_merge_conflicts(source_path, dest_path)
        new_dir_count, del_count, move_count, copy_count = merge_ops.resolve_merge_conflicts(
            source_path, dest_path, conflicts)
        self.assertEqual((new_dir_count, del_count, move_count, copy_count), (1, 0, 0, 2))

    def test_resolve_merge_conflicts_del_dest(self):
        source_path = os.path.join(self.col.virtual_base_original, 'dir_src')
        dest_path = os.path.join(self.col.virtual_base_original, 'dir_dest')
        conflicts = merge_ops.get_merge_conflicts(source_path, dest_path)
        conflicts[0]['dest']['keep'] = 0
        new_dir_count, del_count, move_count, copy_count = merge_ops.resolve_merge_conflicts(
            source_path, dest_path, conflicts)
        self.assertEqual((new_dir_count, del_count, move_count, copy_count), (1, 1, 0, 2))

    def test_resolve_merge_conflicts_move_dest(self):
        source_path = os.path.join(self.col.virtual_base_original, 'dir_src')
        dest_path = os.path.join(self.col.virtual_base_original, 'dir_dest')
        conflicts = merge_ops.get_merge_conflicts(source_path, dest_path)
        conflicts[0]['dest']['rename'] = 'file_common_renamed'
        new_dir_count, del_count, move_count, copy_count = merge_ops.resolve_merge_conflicts(
            source_path, dest_path, conflicts)
        self.assertEqual((new_dir_count, del_count, move_count, copy_count), (1, 0, 1, 2))

    def test_resolve_merge_conflicts_skip_source(self):
        source_path = os.path.join(self.col.virtual_base_original, 'dir_src')
        dest_path = os.path.join(self.col.virtual_base_original, 'dir_dest')
        conflicts = merge_ops.get_merge_conflicts(source_path, dest_path)
        conflicts[0]['source']['keep'] = 0
        new_dir_count, del_count, move_count, copy_count = merge_ops.resolve_merge_conflicts(
            source_path, dest_path, conflicts)
        self.assertEqual((new_dir_count, del_count, move_count, copy_count), (1, 0, 0, 1))


class FilterUtilsTests(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        # VFS
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        # Collection
        self.col = core.CollectionMeta('col', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col')),
                                       os.path.abspath(os.path.join(self.vfs.virtual_base, 'col')))
        os.mkdir(self.col.actual_base)
        self.col_dir = os.path.join(self.col.actual_base, 'dir')
        self.col_dir_virtual = os.path.join(self.col.virtual_base_original, 'dir')
        os.mkdir(self.col_dir)
        self.col_file_mp3 = os.path.join(self.col.actual_base, 'file.mp3')
        self.col_file_mp3_virtual = os.path.join(self.col.virtual_base_original, 'file.mp3')
        self.col_file_mp3_size = 200
        create_dummy_file(self.col_file_mp3, self.col_file_mp3_size)
        self.col_file_exe = os.path.join(self.col.actual_base, 'file.exe')
        self.col_file_exe_virtual = os.path.join(self.col.virtual_base_original, 'file.exe')
        self.col_file_exe_size = 900
        create_dummy_file(self.col_file_exe, self.col_file_exe_size)
        self.col_file_unknown = os.path.join(self.col_dir, 'file.unknown')
        self.col_file_unknown_virtual = os.path.join(self.col_dir_virtual, 'file.unknown')
        self.col_file_unknown_size = 800
        create_dummy_file(self.col_file_unknown, self.col_file_unknown_size)
        self.col_file_txt = os.path.join(self.col_dir, 'file.txt')
        self.col_file_txt_virtual = os.path.join(self.col_dir_virtual, 'file.txt')
        self.col_file_txt_size = 100
        create_dummy_file(self.col_file_txt, self.col_file_txt_size)
        core.setup_collection(self.col.name, self.col.actual_base)
        disconnect_path(self.col.actual_base)

    def tearDown(self):
        cleanup_test_env()

    def test_filter_test_mimetype(self):
        # Pass
        self.assertTrue(filter_ops.filter_test_mimetype(self.col_file_mp3_virtual, ['audio']))
        self.assertTrue(filter_ops.filter_test_mimetype(self.col_file_exe_virtual, ['application']))
        self.assertTrue(filter_ops.filter_test_mimetype(self.col_file_txt_virtual, ['text']))
        self.assertTrue(filter_ops.filter_test_mimetype(self.col_file_unknown_virtual, ['unknown']))
        self.assertTrue(filter_ops.filter_test_mimetype(self.col_file_mp3_virtual, ['text', 'audio']))
        self.assertTrue(filter_ops.filter_test_mimetype(self.col_file_exe_virtual, ['unknown', 'application']))
        # Fail
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_mp3_virtual, ['video']))
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_exe_virtual, ['text']))
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_txt_virtual, ['unknown']))
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_unknown_virtual, ['audio']))
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_mp3_virtual, ['text', 'unknown']))
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_exe_virtual, ['audio', 'video']))
        self.assertFalse(filter_ops.filter_test_mimetype(self.col_file_exe_virtual, []))

    def test_filter_test_size(self):
        # Pass
        self.assertTrue(filter_ops.filter_test_size(self.col_file_mp3_virtual, self.col_file_mp3_size - 10,
                                                    self.col_file_mp3_size + 10))
        self.assertTrue(filter_ops.filter_test_size(self.col_file_exe_virtual, self.col_file_exe_size - 10,
                                                    self.col_file_exe_size + 10))
        self.assertTrue(filter_ops.filter_test_size(self.col_file_unknown_virtual, -1, self.col_file_unknown_size + 10))
        self.assertTrue(filter_ops.filter_test_size(self.col_file_txt_virtual, self.col_file_txt_size - 10, -1))
        self.assertTrue(filter_ops.filter_test_size(self.col_file_txt_virtual, -1, -1))
        # Fail
        self.assertFalse(filter_ops.filter_test_size(self.col_file_mp3_virtual, self.col_file_mp3_size + 10,
                                                     self.col_file_mp3_size + 20))
        self.assertFalse(filter_ops.filter_test_size(self.col_file_exe_virtual, self.col_file_exe_size - 20,
                                                     self.col_file_exe_size - 10))
        self.assertFalse(
            filter_ops.filter_test_size(self.col_file_unknown_virtual, -1, self.col_file_unknown_size - 10))
        self.assertFalse(filter_ops.filter_test_size(self.col_file_txt_virtual, self.col_file_txt_size + 10, -1))

    def test_filter_test_prop(self):
        core.set_virtual_path_prop('test_prop_1', True, self.col_file_unknown_virtual)
        core.set_virtual_path_prop('test_prop_2', 'test_val', self.col_dir_virtual)
        core.set_virtual_path_prop('test_prop_3', True, self.col_dir_virtual)
        # Pass
        self.assertTrue(filter_ops.filter_test_prop(self.col_file_unknown_virtual, [['test_prop_1']]))
        self.assertTrue(filter_ops.filter_test_prop(self.col_dir_virtual, [['test_prop_2', 'test_val']]))
        self.assertTrue(
            filter_ops.filter_test_prop(self.col_dir_virtual, [['test_prop_2', 'test_val'], ['test_prop_3']]))
        # Fail
        self.assertFalse(filter_ops.filter_test_prop(self.col_file_mp3_virtual, [['test_prop_1']]))
        self.assertFalse(filter_ops.filter_test_prop(self.col_file_unknown_virtual, [['test_prop_1', 'test_val']]))
        self.assertFalse(filter_ops.filter_test_prop(self.col_dir_virtual, [['test_prop_2', True]]))
        self.assertTrue(filter_ops.filter_test_prop(self.col_file_unknown_virtual, [['test_prop_1'], ['test_prop_3']]))

    def test_apply_filter_mimetype(self):
        mimes = ['audio', 'application']
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        # Virtual files
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertTrue(os.path.islink(self.col_file_exe_virtual))
        self.assertFalse(os.path.isdir(self.col_dir_virtual))
        # Filter directory
        filter_path = filter_ops.compute_filter_path(config.FILTER_NAME_MIMETYPE)
        self.assertFalse(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_mp3_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_unknown_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_txt_virtual, self.vfs.virtual_base))))

    def test_apply_filter_mimetype_freeze(self):
        mimes = ['audio', 'application']
        freeze_ops.freeze_dir(self.col_dir_virtual)
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        # Virtual files
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertTrue(os.path.islink(self.col_file_exe_virtual))
        self.assertTrue(os.path.islink(self.col_file_unknown_virtual))
        self.assertTrue(os.path.islink(self.col_file_txt_virtual))
        # Filter directory
        filter_path = filter_ops.compute_filter_path(config.FILTER_NAME_MIMETYPE)
        self.assertFalse(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_mp3_virtual, self.vfs.virtual_base))))
        self.assertFalse(os.path.isdir(
            os.path.join(filter_path, os.path.relpath(self.col_dir_virtual, self.vfs.virtual_base))))

    def test_apply_filter_size(self):
        lower = 150
        upper = 850
        filter_ops.apply_filter(config.FILTER_NAME_SIZE, filter_ops.filter_test_size, lower, upper)
        # Virtual files
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertTrue(os.path.islink(self.col_file_unknown_virtual))
        self.assertFalse(os.path.islink(self.col_file_exe_virtual))
        self.assertFalse(os.path.islink(self.col_file_txt_virtual))
        # Filter directory
        filter_path = filter_ops.compute_filter_path(config.FILTER_NAME_SIZE)
        self.assertFalse(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_mp3_virtual, self.vfs.virtual_base))))
        self.assertFalse(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_unknown_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_exe_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_txt_virtual, self.vfs.virtual_base))))

    def test_apply_filter_prop(self):
        prop = 'test_prop'
        value = True
        core.set_virtual_path_prop(prop, value, self.col_dir_virtual)
        filter_ops.apply_filter(config.FILTER_NAME_PROP, filter_ops.filter_test_prop, [[prop, value]])
        # Virtual files
        self.assertFalse(os.path.islink(self.col_file_mp3_virtual))
        self.assertFalse(os.path.islink(self.col_file_exe_virtual))
        self.assertTrue(os.path.islink(self.col_file_unknown_virtual))
        self.assertTrue(os.path.islink(self.col_file_txt_virtual))
        # Filter directory
        filter_path = filter_ops.compute_filter_path(config.FILTER_NAME_PROP)
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_mp3_virtual, self.vfs.virtual_base))))
        self.assertFalse(os.path.isdir(
            os.path.join(filter_path, os.path.relpath(self.col_dir_virtual, self.vfs.virtual_base))))

    def test_apply_filter_multi(self):
        mimes = ['audio', 'application']
        lower = 150
        upper = 850
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        filter_ops.apply_filter(config.FILTER_NAME_SIZE, filter_ops.filter_test_size, lower, upper)
        # Virtual files
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertFalse(os.path.islink(self.col_file_exe_virtual))
        self.assertFalse(os.path.isdir(self.col_dir_virtual))
        # Filter directory mimetype
        filter_path = filter_ops.compute_filter_path(config.FILTER_NAME_MIMETYPE)
        self.assertFalse(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_mp3_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_unknown_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_txt_virtual, self.vfs.virtual_base))))
        # Filter directory size
        filter_path = filter_ops.compute_filter_path(config.FILTER_NAME_SIZE)
        self.assertFalse(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_mp3_virtual, self.vfs.virtual_base))))
        self.assertTrue(os.path.islink(
            os.path.join(filter_path, os.path.relpath(self.col_file_exe_virtual, self.vfs.virtual_base))))
        self.assertFalse(os.path.isdir(
            os.path.join(filter_path, os.path.relpath(self.col_dir_virtual, self.vfs.virtual_base))))

    def test_get_all_filter_names(self):
        mimes = ['audio', 'application']
        lower = 150
        upper = 850
        self.assertEqual(filter_ops.get_all_filter_names(), [])
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        self.assertEqual(filter_ops.get_all_filter_names(), [config.FILTER_NAME_MIMETYPE])
        filter_ops.apply_filter(config.FILTER_NAME_SIZE, filter_ops.filter_test_size, lower, upper)
        self.assertEqual(filter_ops.get_all_filter_names(), [config.FILTER_NAME_SIZE, config.FILTER_NAME_MIMETYPE])
        filter_ops.clear_filters()
        self.assertEqual(filter_ops.get_all_filter_names(), [])

    def test_clear_filters_single(self):
        mimes = ['audio', 'application']
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        filter_ops.clear_filters()
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertTrue(os.path.islink(self.col_file_exe_virtual))
        self.assertTrue(os.path.islink(self.col_file_unknown_virtual))
        self.assertTrue(os.path.islink(self.col_file_txt_virtual))
        # Merge dir
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        os.mkdir(self.col_dir_virtual)
        filter_ops.clear_filters()
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertTrue(os.path.islink(self.col_file_exe_virtual))
        self.assertTrue(os.path.islink(self.col_file_unknown_virtual))
        self.assertTrue(os.path.islink(self.col_file_txt_virtual))

    def test_clear_filters_single_invalid(self):
        mimes = ['audio', 'application']
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        # Add a frozen directory
        os.mkdir(self.col_dir_virtual)
        freeze_ops.freeze_dir(self.col_dir_virtual)
        with self.assertRaises(core.VfsException):
            filter_ops.clear_filters()
        shutil.rmtree(self.col_dir_virtual)
        filter_ops.clear_filters()
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        # Add a conflicting file
        os.mkdir(self.col_dir_virtual)
        create_dummy_file(self.col_file_unknown_virtual, self.col_file_unknown_size)
        with self.assertRaises(core.VfsException):
            filter_ops.clear_filters()
        shutil.rmtree(self.col_dir_virtual)
        filter_ops.clear_filters()
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        # Add file confilicting with directory
        create_dummy_file(self.col_dir_virtual, 10)
        with self.assertRaises(core.VfsException):
            filter_ops.clear_filters()

    def test_clear_filters_multi(self):
        mimes = ['audio', 'application']
        lower = 150
        upper = 850
        filter_ops.apply_filter(config.FILTER_NAME_MIMETYPE, filter_ops.filter_test_mimetype, mimes)
        filter_ops.apply_filter(config.FILTER_NAME_SIZE, filter_ops.filter_test_size, lower, upper)
        filter_ops.clear_filters()
        self.assertTrue(os.path.islink(self.col_file_mp3_virtual))
        self.assertTrue(os.path.islink(self.col_file_exe_virtual))
        self.assertTrue(os.path.islink(self.col_file_unknown_virtual))
        self.assertTrue(os.path.islink(self.col_file_txt_virtual))


class SaveUtilsTests(unittest.TestCase):
    def setUp(self):
        setup_test_env()
        self.vfs = core.VfsMeta('test_vfs', os.path.abspath(os.path.join(_VIRTUAL_DIR, 'test_vfs')))
        core.setup_vfs(self.vfs.name, _VIRTUAL_DIR)
        core.set_current_vfs(self.vfs)
        # Discs
        self.disc1 = core.DiscMeta('disc1', os.path.abspath(os.path.join(_ACTUAL_DIR, 'disc1')))
        os.mkdir(self.disc1.disc_base)
        core.add_disc(self.disc1.name, self.disc1.disc_base, self.disc1.capacity)
        self.disc2 = core.DiscMeta('disc2', os.path.abspath(os.path.join(_ACTUAL_DIR, 'disc2')), 300)
        os.mkdir(self.disc2.disc_base)
        core.add_disc(self.disc2.name, self.disc2.disc_base, self.disc2.capacity)
        # Collections
        self.col1 = core.CollectionMeta('col1', os.path.abspath(os.path.join(self.disc1.disc_base, 'col1')),
                                        os.path.abspath(os.path.join(self.vfs.virtual_base, 'col1')))
        os.mkdir(self.col1.actual_base)
        self.col1_dir = os.path.join(self.col1.actual_base, 'col1_dir')
        os.mkdir(self.col1_dir)
        self.col1_file = os.path.join(self.col1.actual_base, 'col1_file')
        self.col1_file_size = 100
        create_dummy_file(self.col1_file, self.col1_file_size)
        core.setup_collection(self.col1.name, self.col1.actual_base)
        self.col2 = core.CollectionMeta('col2', os.path.abspath(os.path.join(self.disc2.disc_base, 'col2')),
                                        os.path.abspath(os.path.join(self.vfs.virtual_base, 'col2')))
        disconnect_path(self.col1.actual_base)
        os.mkdir(self.col2.actual_base)
        self.col2_dir = os.path.join(self.col2.actual_base, 'col2_dir')
        os.mkdir(self.col2_dir)
        self.col2_file = os.path.join(self.col2.actual_base, 'col2_file')
        self.col2_file_size = 200
        create_dummy_file(self.col2_file, self.col2_file_size)
        core.setup_collection(self.col2.name, self.col2.actual_base)
        disconnect_path(self.col2.actual_base)
        # Save maps
        self.save_map1 = core.SaveMapMeta(self.col1.virtual_base_original, self.col2.actual_base)
        core.add_save_map(self.save_map1.virtual_dir, self.save_map1.actual_dir)
        self.save_map2 = core.SaveMapMeta(self.col2.virtual_base_original, self.col1.actual_base)
        core.add_save_map(self.save_map2.virtual_dir, self.save_map2.actual_dir)

    def tearDown(self):
        cleanup_test_env()
        save_ops._invalidate_save_cache()

    def test_get_all_disc_sizes(self):
        disc_sizes = save_ops.get_all_disc_sizes()
        self.assertEqual(disc_sizes, {self.disc1.name: self.col1_file_size, self.disc2.name: self.col2_file_size})
        disc_sizes_cached = save_ops.get_all_disc_sizes()
        self.assertIs(disc_sizes, disc_sizes_cached)

    def test_get_disc_size(self):
        self.assertEqual(self.col1_file_size, save_ops.get_disc_size(self.disc1.name))

    def test_get_disc_transfers(self):
        disc_transfers = save_ops.get_disc_transfers()
        self.assertEqual(len(disc_transfers), 2)
        self.assertEqual(len(disc_transfers[self.disc1.name]), 2)
        self.assertEqual(len(disc_transfers[self.disc1.name][self.disc1.name]), 2)
        self.assertEqual(len(disc_transfers[self.disc1.name][self.disc2.name]), 1)
        self.assertEqual(len(disc_transfers[self.disc2.name][self.disc1.name]), 1)
        self.assertEqual(len(disc_transfers[self.disc2.name][self.disc2.name]), 2)
        # Dir transfers
        self.assertEqual(disc_transfers[self.disc1.name][self.disc1.name][0].__dict__,
                         save_ops.TransferStatus(os.path.join(self.vfs.virtual_base, self.col2.name)).__dict__)
        self.assertEqual(disc_transfers[self.disc1.name][self.disc1.name][1].__dict__,
                         save_ops.TransferStatus(
                             os.path.join(self.col2.virtual_base_original, os.path.basename(self.col2_dir))).__dict__)
        self.assertEqual(disc_transfers[self.disc2.name][self.disc2.name][0].__dict__,
                         save_ops.TransferStatus(os.path.join(self.vfs.virtual_base, self.col1.name)).__dict__)
        self.assertEqual(disc_transfers[self.disc2.name][self.disc2.name][1].__dict__,
                         save_ops.TransferStatus(
                             os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_dir))).__dict__)
        # File transfers
        self.assertEqual(disc_transfers[self.disc1.name][self.disc2.name][0].__dict__,
                         save_ops.TransferStatus(os.path.join(self.vfs.virtual_base, self.col1.name,
                                                              os.path.basename(self.col1_file))).__dict__)
        self.assertEqual(disc_transfers[self.disc2.name][self.disc1.name][0].__dict__,
                         save_ops.TransferStatus(os.path.join(self.vfs.virtual_base, self.col2.name,
                                                              os.path.basename(self.col2_file))).__dict__)
        # cached
        disc_transfers_cached = save_ops.get_disc_transfers()
        self.assertIs(disc_transfers, disc_transfers_cached)

    def test_get_disc_transfer_sizes(self):
        disc_transfer_sizes = save_ops.get_disc_transfer_sizes()
        self.assertEqual(disc_transfer_sizes, {
            self.disc1.name: {
                self.disc1.name: 2,
                self.disc2.name: self.col1_file_size,
            }, self.disc2.name: {
                self.disc1.name: self.col2_file_size,
                self.disc2.name: 2,
            },
        })
        disc_transfer_sizes_cached = save_ops.get_disc_transfer_sizes()
        self.assertIs(disc_transfer_sizes, disc_transfer_sizes_cached)

    def test_get_disc_deletions(self):
        deletions = save_ops.get_disc_deletions()
        self.assertEqual(deletions, {
            self.disc1.name: [],
            self.disc2.name: []
        })
        deletions_cached = save_ops.get_disc_deletions()
        self.assertIs(deletions, deletions_cached)
        save_ops._invalidate_save_cache()
        core._invalidate_collections_cache()
        os.unlink(os.path.join(self.vfs.virtual_base, self.col1.name, os.path.basename(self.col1_file)))
        deletions = save_ops.get_disc_deletions()
        self.assertEqual(len(deletions), 2)
        self.assertEqual(len(deletions[self.disc1.name]), 1)
        self.assertEqual(len(deletions[self.disc2.name]), 0)
        self.assertEqual(deletions[self.disc1.name][0].__dict__, save_ops.DeletionStatus(self.col1_file).__dict__)

    def test_get_disc_deletion_sizes(self):
        disc_deletion_sizes = save_ops.get_disc_deletion_sizes()
        self.assertEqual(disc_deletion_sizes, {
            self.disc1.name: 0,
            self.disc2.name: 0
        })
        disc_deletion_sizes_cached = save_ops.get_disc_deletion_sizes()
        self.assertIs(disc_deletion_sizes, disc_deletion_sizes_cached)
        save_ops._invalidate_save_cache()
        core._invalidate_collections_cache()
        os.unlink(os.path.join(self.vfs.virtual_base, self.col2.name, os.path.basename(self.col2_file)))
        disc_deletion_sizes = save_ops.get_disc_deletion_sizes()
        self.assertEqual(disc_deletion_sizes, {
            self.disc1.name: 0,
            self.disc2.name: self.col2_file_size
        })

    def test_get_actual_to_virtual_map(self):
        # Virtual modifications
        col1_file_virtual = os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_file))
        col2_file_virtual = os.path.join(self.col2.virtual_base_original, os.path.basename(self.col2_file))
        col1_file_copy_1 = os.path.join(self.col2.virtual_base_original, 'col1_file_copy_1')
        col1_file_copy_2 = os.path.join(self.col2.virtual_base_original, 'col1_file_copy_2')
        core.copy_symlink(col1_file_virtual, col1_file_copy_1)
        core.copy_symlink(col1_file_virtual, col1_file_copy_2)
        shutil.rmtree(self.col1.virtual_base_original)
        a2v_map = core.get_actual_to_virtual_map()
        self.assertEqual(a2v_map, {
            self.col1_file: [col1_file_copy_2, col1_file_copy_1],
            self.col2_file: [col2_file_virtual]
        })
        a2v_map_cached = core.get_actual_to_virtual_map()
        self.assertIs(a2v_map, a2v_map_cached)

    def test_validate_exhaustive_save_maps(self):
        save_ops.validate_exhaustive_save_maps()
        os.mkdir(os.path.join(self.vfs.virtual_base, 'new_dir'))
        with self.assertRaises(core.VfsException):
            save_ops.validate_exhaustive_save_maps()

    def test_validate_exhaustive_discs(self):
        save_ops.validate_exhaustive_discs()
        col3 = core.CollectionMeta('col3', os.path.abspath(os.path.join(_ACTUAL_DIR, 'col3')),
                                   os.path.abspath(os.path.join(self.vfs.virtual_base, 'col3')))
        os.mkdir(col3.actual_base)
        core.setup_collection(col3.name, col3.actual_base)
        with self.assertRaises(core.VfsException):
            save_ops.validate_exhaustive_discs()

    def test_validate_space_availability_copy(self):
        # Copy valid
        save_ops.set_save_mode('copy')
        save_ops.validate_space_availability()
        # Copy invalid
        save_ops._invalidate_save_cache()
        core._invalidate_collections_cache()
        save_ops.set_save_mode('copy')
        col1_file_virtual = os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_file))
        col1_file_copy_1 = os.path.join(self.col1.virtual_base_original, 'col1_file_copy_1')
        core.copy_symlink(col1_file_virtual, col1_file_copy_1)
        with self.assertRaises(core.VfsException):
            save_ops.validate_space_availability()

    def test_validate_space_availability_move(self):
        # valid
        save_ops.set_save_mode('move')
        save_ops.validate_space_availability()
        # invalid
        save_ops._invalidate_save_cache()
        core._invalidate_collections_cache()
        save_ops.set_save_mode('move')
        col1_file_virtual = os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_file))
        col1_file_copy_1 = os.path.join(self.col1.virtual_base_original, 'col1_file_copy_1')
        col1_file_copy_2 = os.path.join(self.col1.virtual_base_original, 'col1_file_copy_2')
        col1_file_copy_3 = os.path.join(self.col1.virtual_base_original, 'col1_file_copy_3')
        core.copy_symlink(col1_file_virtual, col1_file_copy_1)
        core.copy_symlink(col1_file_virtual, col1_file_copy_2)
        core.copy_symlink(col1_file_virtual, col1_file_copy_3)
        with self.assertRaises(core.VfsException):
            save_ops.validate_space_availability()

    def test_validate_filters(self):
        save_ops.validate_filters()
        filter_ops.apply_filter(config.FILTER_NAME_SIZE, filter_ops.filter_test_size, -1, -1)
        with self.assertRaises(core.VfsException):
            save_ops.validate_filters()

    @staticmethod
    def _scheme_cmp(scheme1, scheme2):
        def _str_cmp(str1, str2):
            return -1 if str1 < str2 else (1 if str1 > str2 else 0)

        is_del1 = isinstance(scheme1, save_ops.DiscDeletion)
        is_del2 = isinstance(scheme2, save_ops.DiscDeletion)
        if is_del1 is not is_del2:
            return -1 if is_del1 else 1
        if is_del1:
            return _str_cmp(scheme1.disc, scheme2.disc)
        else:
            cmp1 = _str_cmp(scheme1.disc1, scheme2.disc1)
            if cmp1 == 0:
                return _str_cmp(scheme1.disc2, scheme2.disc2)
            else:
                return cmp1

    def test_generate_disc_scheme_for_copy(self):
        all_schemes = save_ops.generate_disc_scheme_for_copy()
        all_schemes.sort(cmp=self._scheme_cmp)
        all_schemes_dict = [x.__dict__ for x in all_schemes]
        expected = [
            save_ops.InterDiscTransfer(self.disc1.name, self.disc2.name, self.col1_file_size, True),
            save_ops.InterDiscTransfer(self.disc2.name, self.disc1.name, self.col2_file_size, True),
            save_ops.InterDiscTransfer(self.disc1.name, self.disc1.name, 2, True),
            save_ops.InterDiscTransfer(self.disc2.name, self.disc2.name, 2, True)
        ]
        expected.sort(cmp=self._scheme_cmp)
        expected_dict = [x.__dict__ for x in expected]
        self.assertEqual(all_schemes_dict, expected_dict)

    def test_generate_disc_scheme_for_move(self):
        # delete a file
        col2_file_virtual = os.path.join(self.col2.virtual_base_original, os.path.basename(self.col2_file))
        os.unlink(col2_file_virtual)
        all_schemes = save_ops.generate_disc_scheme_for_move()
        all_schemes.sort(cmp=self._scheme_cmp)
        all_schemes_dict = [x.__dict__ for x in all_schemes]
        expected = [
            save_ops.InterDiscTransfer(self.disc1.name, self.disc2.name, self.col1_file_size, True),
            save_ops.DiscDeletion(self.disc2.name),
            save_ops.InterDiscTransfer(self.disc1.name, self.disc1.name, 2, True),
            save_ops.InterDiscTransfer(self.disc2.name, self.disc2.name, 2, True)
        ]
        expected.sort(cmp=self._scheme_cmp)
        expected_dict = [x.__dict__ for x in expected]
        self.assertEqual(all_schemes_dict, expected_dict)

    def test_generate_save_status_for_copy(self):
        save_ops.set_save_mode('copy')
        save_status = save_ops.generate_save_status()
        cleanup_done, deletions, mode, schemes, transfers = [save_status[key] for key in sorted(save_status)]
        self.assertTrue(cleanup_done)
        self.assertEqual(mode, 'copy')
        self.assertEqual(len(deletions), 2)
        self.assertEqual(len(schemes), 4)
        self.assertEqual(len(transfers), 2)

    def test_generate_save_status_for_move(self):
        save_ops.set_save_mode('move')
        save_status = save_ops.generate_save_status()
        cleanup_done, deletions, mode, schemes, transfers = [save_status[key] for key in sorted(save_status)]
        self.assertFalse(cleanup_done)
        self.assertEqual(mode, 'move')
        self.assertEqual(len(deletions), 2)
        self.assertEqual(len(schemes), 4)
        self.assertEqual(len(transfers), 2)

    def test_do_del_file(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        # Before deletiion
        save_ops.set_save_mode('move')
        col1_file_virtual = os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_file))
        os.unlink(col1_file_virtual)
        save_status = save_ops.generate_save_status()
        save_ops.save_save_status()
        stats = core.get_file_stats_for_actual_path(self.col1_file)
        self.assertIsNotNone(stats)
        self.assertTrue(os.path.isfile(self.col1_file))
        del_status = save_status['deletions'][self.disc1.name][0]
        self.assertFalse(del_status.completed)
        # Deletion
        self.assertEqual(del_status.actual_path, self.col1_file)
        save_ops.do_del_file(del_status)
        # Check changes
        self.assertFalse(os.path.isfile(self.col1_file))
        self.assertTrue(del_status.completed)
        stats = core.get_file_stats_for_actual_path(self.col1_file)
        self.assertIsNone(stats)

    def test_do_save_dir_copy(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        # Before copy
        save_ops.set_save_mode('copy')
        save_status = save_ops.generate_save_status()
        save_ops.save_save_status()
        save_status = save_status['transfers'][self.disc2.name][self.disc2.name][1]
        self.assertFalse(save_status.completed)
        self.assertEqual(save_status.virtual_path,
                         os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_dir)))
        # Save
        save_ops.do_save_dir(save_status)
        # Check changes
        self.assertTrue(os.path.isdir(self.col1_dir))
        self.assertTrue(save_status.completed)

        # New dir
        dest_path = os.path.join(self.col2.actual_base, os.path.basename(self.col1_dir))
        self.assertTrue(os.path.isdir(dest_path))

    def test_do_save_dir_move(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        # Before move
        save_ops.set_save_mode('move')
        save_status = save_ops.generate_save_status()
        save_ops.save_save_status()
        save_status = save_status['transfers'][self.disc2.name][self.disc2.name][1]
        self.assertFalse(save_status.completed)
        self.assertEqual(save_status.virtual_path,
                         os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_dir)))
        # Save
        save_ops.do_save_dir(save_status)
        # Check changes
        self.assertTrue(os.path.isdir(self.col1_dir))
        self.assertTrue(save_status.completed)
        # New dir
        dest_path = os.path.join(self.col2.actual_base, os.path.basename(self.col1_dir))
        self.assertTrue(os.path.isdir(dest_path))

    def test_do_save_file_copy(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        # Before copy
        save_ops.set_save_mode('copy')
        save_status = save_ops.generate_save_status()
        save_ops.save_save_status()
        stats = core.get_file_stats_for_actual_path(self.col1_file)
        self.assertIsNotNone(stats)
        a2v_map = core.get_actual_to_virtual_map()
        self.assertEqual(len(a2v_map[self.col1_file]), 1)
        copy_status = save_status['transfers'][self.disc1.name][self.disc2.name][0]
        self.assertFalse(copy_status.completed)
        self.assertEqual(copy_status.virtual_path,
                         os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_file)))
        scheme = [x for x in save_status['scheme'] if x.disc1 == self.disc1.name and x.disc2 == self.disc2.name][0]
        # Save
        save_ops.do_save_file(copy_status, scheme)
        # Check changes
        self.assertTrue(os.path.isfile(self.col1_file))
        self.assertTrue(copy_status.completed)
        stats = core.get_file_stats_for_actual_path(self.col1_file)
        self.assertIsNotNone(stats)
        self.assertIn(self.col1_file, a2v_map)
        # New file
        dest_path = os.path.join(self.col2.actual_base, os.path.basename(self.col1_file))
        self.assertTrue(os.path.isfile(dest_path))
        stats = core.get_file_stats_for_actual_path(dest_path)
        self.assertIsNotNone(stats)
        self.assertIn(dest_path, a2v_map)

    def test_do_save_file_move(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        # Before copy
        save_ops.set_save_mode('move')
        save_status = save_ops.generate_save_status()
        save_ops.save_save_status()
        stats = core.get_file_stats_for_actual_path(self.col1_file)
        self.assertIsNotNone(stats)
        a2v_map = core.get_actual_to_virtual_map()
        self.assertEqual(len(a2v_map[self.col1_file]), 1)
        copy_status = save_status['transfers'][self.disc1.name][self.disc2.name][0]
        self.assertFalse(copy_status.completed)
        self.assertEqual(copy_status.virtual_path,
                         os.path.join(self.col1.virtual_base_original, os.path.basename(self.col1_file)))
        scheme = [x for x in save_status['scheme'] if x.disc1 == self.disc1.name and x.disc2 == self.disc2.name][0]
        # Save
        save_ops.do_save_file(copy_status, scheme)
        # Check changes
        self.assertFalse(os.path.isfile(self.col1_file))
        self.assertTrue(copy_status.completed)
        stats = core.get_file_stats_for_actual_path(self.col1_file)
        self.assertIsNone(stats)
        self.assertNotIn(self.col1_file, a2v_map)
        # New file
        dest_path = os.path.join(self.col2.actual_base, os.path.basename(self.col1_file))
        self.assertTrue(os.path.isfile(dest_path))
        stats = core.get_file_stats_for_actual_path(dest_path)
        self.assertIsNotNone(stats)
        self.assertIn(dest_path, a2v_map)

    def test_save_copy(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        save_ops.set_save_mode('copy')
        save_ops.save()
        saved = []
        for root, dors, files in os.walk(os.path.abspath(_ACTUAL_DIR)):
            saved.append(root)
            saved += [os.path.join(root, file_) for file_ in files]
        saved.sort()
        expected = [
            os.path.abspath(_ACTUAL_DIR),
            self.disc1.disc_base,
            self.disc2.disc_base,
            self.col1.actual_base,
            self.col2.actual_base,
            self.col1_file,
            self.col2_file,
            self.col1_dir,
            self.col2_dir,
            os.path.join(self.col1.actual_base, os.path.basename(self.col2_file)),
            os.path.join(self.col2.actual_base, os.path.basename(self.col1_file)),
            os.path.join(self.col1.actual_base, os.path.basename(self.col2_dir)),
            os.path.join(self.col2.actual_base, os.path.basename(self.col1_dir))
        ]
        expected.sort()
        self.assertEqual(saved, expected)

    def test_save_move(self):
        reconnect_path(self.col1.actual_base)
        reconnect_path(self.col2.actual_base)
        save_ops.set_save_mode('move')
        save_ops.save()
        saved = []
        for root, dors, files in os.walk(os.path.abspath(_ACTUAL_DIR)):
            saved.append(root)
            saved += [os.path.join(root, file_) for file_ in files]
        saved.sort()
        expected = [
            os.path.abspath(_ACTUAL_DIR),
            self.disc1.disc_base,
            self.disc2.disc_base,
            self.col1.actual_base,
            self.col2.actual_base,
            os.path.join(self.col1.actual_base, os.path.basename(self.col2_file)),
            os.path.join(self.col2.actual_base, os.path.basename(self.col1_file)),
            os.path.join(self.col1.actual_base, os.path.basename(self.col2_dir)),
            os.path.join(self.col2.actual_base, os.path.basename(self.col1_dir))
        ]
        expected.sort()
        self.assertEqual(saved, expected)


if __name__ == '__main__':
    unittest.main()
