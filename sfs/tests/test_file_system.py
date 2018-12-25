import os
import json
import unittest

import sfs.file_system as fs
import sfs.tests.helper as helper


class SymbolicLinkUtilsTests(helper.TestCaseWithFS):

    def setUp(self):
        super(type(self), self).setUp()
        self.file_path = os.path.join(self.TESTS_BASE, 'test_file')
        helper.dummy_file(self.file_path)
        self.link_name = 'test_link'
        self.link_path = os.path.join(self.TESTS_BASE, self.link_name)

    def _validate_symlink(self, src, dest):
        # link should exist and point to destination
        self.assertTrue(os.path.islink(dest))
        self.assertEqual(os.path.realpath(dest), os.path.abspath(src))

    def test_create_symlink(self):
        # Creates a valid link
        fs.create_symlink(self.file_path, self.link_path)
        self._validate_symlink(self.file_path, self.link_path)

    def test_overwrite_symlink(self):
        fs.create_symlink(self.file_path, self.link_path)

        # Cannot override an existing link
        with self.assertRaises(fs.AlreadyExists):
            fs.create_symlink(self.file_path, self.link_path)

        # Can override a link explicitly
        fs.create_symlink(self.file_path, self.link_path, override=True)
        self._validate_symlink(self.file_path, self.link_path)

    def test_create_broken_symlink(self):
        # Creates a broken link
        file_path_nonexistant = os.path.join(self.TESTS_BASE, 'nonexistant_file_path')
        fs.create_symlink(file_path_nonexistant, self.link_path)
        self._validate_symlink(file_path_nonexistant, self.link_path)

    def test_delete_symlink(self):
        # Deletes a link
        fs.create_symlink(self.file_path, self.link_path)
        fs.del_symlink(self.link_path)
        self.assertFalse(os.path.islink(self.link_path))

    def test_delete_symlink_ignore_errors(self):
        fs.create_symlink(self.file_path, self.link_path)
        fs.del_symlink(self.link_path)

        # Raise exception of link is not found
        with self.assertRaises(fs.DoesNotExist):
            fs.del_symlink(self.link_path)

        # Ignores errors for missing links
        fs.del_symlink(self.link_path, ignore_already_del=True)

    def test_copy_symlink(self):
        fs.create_symlink(self.file_path, self.link_path)
        link_copy_path = os.path.join(self.TESTS_BASE, 'link_copy')
        fs.copy_symlink(self.link_path, link_copy_path)

        # Copies symlink to path
        self._validate_symlink(self.file_path, link_copy_path)


class ScanDirTests(helper.TestCaseWithFS):

    def test_file(self):
        file_name = 'test_file'
        file_path = os.path.join(self.TESTS_BASE, file_name)
        helper.dummy_file(file_path)
        nodes = fs.scan_dir(self.TESTS_BASE)
        file_node = list(nodes)[0]
        exp = [
            [file_node.name, file_name],
            [file_node.path, file_path],
            [file_node.is_dir, False],
            [file_node.is_file, True],
            [file_node.is_symlink, False],
            [isinstance(file_node.stat, fs.FSNode.NodeStats), True],
        ]

        # Iterates over valid file nodes
        for a, b in exp:
            self.assertEqual(a, b)

    def test_directory(self):
        dir_name = 'test_dir'
        dir_path = os.path.join(self.TESTS_BASE, dir_name)
        os.mkdir(dir_path)
        nodes = fs.scan_dir(self.TESTS_BASE)
        dir_node = list(nodes)[0]
        exp = [
            [dir_node.name, dir_name],
            [dir_node.path, dir_path],
            [dir_node.is_dir, True],
            [dir_node.is_file, False],
            [dir_node.is_symlink, False],
            [isinstance(dir_node.stat, fs.FSNode.NodeStats), True],
        ]

        # Iterates over valid directory nodes
        for a, b in exp:
            self.assertEqual(a, b)

    def test_symlink(self):
        link_name = 'test_symlink'
        link_path = os.path.join(self.TESTS_BASE, link_name)
        file_path = os.path.join(self.TESTS_BASE, 'test_file')
        fs.create_symlink(file_path, link_path)
        nodes = filter(lambda n: n.name == link_name, fs.scan_dir(self.TESTS_BASE))
        link_node = list(nodes)[0]
        exp = [
            [link_node.name, link_name],
            [link_node.path, link_path],
            [link_node.is_dir, False],
            [link_node.is_file, False],
            [link_node.is_symlink, True],
            [isinstance(link_node.stat, fs.FSNode.NodeStats), True],
        ]

        # Iterates over valid symlink nodes
        for a, b in exp:
            self.assertEqual(a, b)

    def test_scan_nested_dir(self):
        tree = {
            'files': ['file_a'],
            'links': ['link_a'],
            'dirs': {
                'dir_a': {
                    'files': ['file_aa', 'file_ab'],
                    'links': ['link_aa'],
                    'dirs': {'dir_aa': {}}
                },
                'dir_b': {
                    'files': ['file_ba', 'file_bb'],
                    'dirs': {'dir_ba': {}}
                }
            }
        }
        self.create_fs_tree(tree)
        nodes = fs.scan_dir(self.TESTS_BASE)
        node_dict = {n.name: n for n in nodes}

        # Iterates over the children nodes
        self.assertEqual(4, len(node_dict))
        for name in ['file_a', 'link_a', 'dir_a', 'dir_b']:
            self.assertTrue(name in node_dict)

        # Children nodes are valid
        self.assertTrue(node_dict['file_a'].is_file)
        self.assertTrue(node_dict['link_a'].is_symlink)
        self.assertTrue(node_dict['dir_a'].is_dir)
        self.assertTrue(node_dict['dir_b'].is_dir)

    def test_separate_nodes(self):
        tree = {
            'files': ['file_a', 'file_b'],
            'links': ['link_a', 'link_b'],
            'dirs': {
                'dir_a': {},
                'dir_b': {}
            }
        }
        self.create_fs_tree(tree)
        nodes = fs.scan_dir(self.TESTS_BASE)
        separated = fs.separate_nodes(nodes)

        # Returns a valid SeparatedNoded namedtuple
        self.assertIs(type(separated), fs.SeparatedNodes)
        files, dirs, links = separated
        self.assertEqual(['file_a', 'file_b'], list(sorted(map(lambda n: n.name, files))))
        self.assertEqual(['dir_a', 'dir_b'], list(sorted(map(lambda n: n.name, dirs))))
        self.assertEqual(['link_a', 'link_b'], list(sorted(map(lambda n: n.name, links))))


class WalkTests(helper.TestCaseWithFS):

    def setUp(self):
        super(type(self), self).setUp()
        self.tree = {
            'files': ['01_file'],
            'links': ['02_link'],
            'dirs': {
                '03_dir': {
                    'files': ['04_file', '05_file'],
                    'links': ['06_link'],
                    'dirs': {'07_dir': {
                        'files': ['08_file'],
                        'dirs': {'09_dir': {}}
                    }}
                },
                '10_dir': {
                    'files': ['11_file'],
                    'dirs': {'12_dir': {}}
                }
            }
        }
        self.create_fs_tree(self.tree)

    @staticmethod
    def _gen_traversal(gen, skip_dirs=()):
        # generates separated and sorted lists of files, directories and links encountered in a given traversal
        traversals = fs.SeparatedNodes([], [], [])
        for root, files, dirs, links in gen:
            dirs[:] = list(filter(lambda n: n.path not in skip_dirs, dirs))
            for i, nodes in enumerate([files, dirs, links]):
                traversals[i].extend(sorted(map(lambda n: n.name, nodes)))
        return traversals

    def test_walk_bfs(self):
        walk = fs.walk_bfs(self.TESTS_BASE)
        traversals = self._gen_traversal(walk)

        # Returns the bfs of the tree
        self.assertEqual(traversals, fs.SeparatedNodes(
            ['01_file', '04_file', '05_file', '11_file', '08_file'],
            ['03_dir', '10_dir', '07_dir', '12_dir', '09_dir'],
            ['02_link', '06_link']
        ))

    def test_walk_bfs_skip_directory(self):
        walk = fs.walk_bfs(self.TESTS_BASE)
        skip_dir = os.path.join(self.TESTS_BASE, '03_dir', '07_dir')
        traversals = self._gen_traversal(walk, skip_dirs=[skip_dir])

        # Returns the bfs of the tree
        self.assertEqual(traversals, fs.SeparatedNodes(
            ['01_file', '04_file', '05_file', '11_file'],
            ['03_dir', '10_dir', '12_dir'],
            ['02_link', '06_link']
        ))

    def test_walk_dfs_preorder(self):
        walk = fs.walk_dfs(self.TESTS_BASE)
        traversals = self._gen_traversal(walk)

        # Returns the pre-order dfs of the tree
        self.assertEqual(traversals, fs.SeparatedNodes(
            ['01_file', '04_file', '05_file', '08_file', '11_file'],
            ['03_dir', '10_dir', '07_dir', '09_dir', '12_dir'],
            ['02_link', '06_link']
        ))

    def test_walk_dfs_postorder(self):
        walk = fs.walk_dfs(self.TESTS_BASE, mode='post-order')
        traversals = self._gen_traversal(walk)

        # Returns the post-order dfs of the tree
        self.assertEqual(traversals, fs.SeparatedNodes(
            ['08_file', '04_file', '05_file', '11_file', '01_file'],
            ['09_dir', '07_dir', '12_dir', '03_dir', '10_dir'],
            ['06_link', '02_link']
        ))


class DirectoryUtilsTests(helper.TestCaseWithFS):

    def test_get_hidden_directory_path(self):
        name = 'hidden_directory'
        path = self.TESTS_BASE

        # Computes hidden directory path
        exp_path = os.path.join(path, ".{}".format(name))
        self.assertEqual(exp_path, fs.get_hidden_directory_path(name, path))

    def test_create_hidden_directory(self):
        name = 'hidden_directory'
        path = self.TESTS_BASE

        # Creates a hidden directory
        exp_path = os.path.join(path, ".{}".format(name))
        created_path = fs.create_hidden_directory(name, path)
        self.assertEqual(exp_path, created_path)
        self.assertTrue(os.path.isdir(exp_path))

    def test_is_empty_directory(self):
        tree = {
            'dirs': {
                'dir_a': {
                    'files': ['file_aa']
                },
                'dir_b': {}
            }
        }
        self.create_fs_tree(tree)

        # Returns True if directory is empty
        self.assertFalse(fs.is_empty_dir(os.path.join(self.TESTS_BASE, 'dir_a')))
        self.assertTrue(fs.is_empty_dir(os.path.join(self.TESTS_BASE, 'dir_b')))

    def test_is_parent_directory(self):
        for child, parent, result in [
            ('/some/path', '/some', True),
            ('/some/path', '/other/path', False),
            ('path11', 'path1', False),
            ('any/relative/path', '/', True),
            ('/same/path', '/same/path', True)
        ]:
            self.assertEqual(fs.is_parent_dir(child, parent), result)


class PickleUtilsTests(helper.TestCaseWithFS):

    def test_save_pickled(self):
        test_dict = {
            'a': 1,
            'x': 'q'
        }
        file_name = 'pickle_test'

        # Pickles and persists data
        fs.save_pickled(test_dict, self.TESTS_BASE, file_name)
        self.assertTrue(os.path.isfile(os.path.join(self.TESTS_BASE, file_name)))

    def test_load_unpickled(self):
        test_dict = {
            'a': 1,
            'x': 'q'
        }
        file_name = 'pickle_test'
        fs.save_pickled(test_dict, self.TESTS_BASE, file_name)

        # Un-pickles and reloads data
        unpickled = fs.load_unpickled(self.TESTS_BASE, file_name)
        self.assertEqual(test_dict, unpickled)


class JSONUtilTests(helper.TestCaseWithFS):

    def test_save_json(self):
        path = os.path.join(self.TESTS_BASE, 'test.json')

        # Saves a builtin type without a serializer
        data = [1, 2, 3]
        fs.save_json(data, path)
        with open(path, 'r') as jf:
            saved = json.load(jf)
        self.assertEqual(data, saved)

        # Saves a custom type with a serializer
        class TestClass:
            def __init__(self):
                self.x = 10
                self.y = 20

        data = [TestClass(), TestClass()]
        fs.save_json(data, path, serializer=lambda x: x.__dict__)
        with open(path, 'r') as jf:
            saved = json.load(jf)
        self.assertEqual(list(map(lambda x: x.__dict__, data)), saved)

    def test_load_json(self):
        path = os.path.join(self.TESTS_BASE, 'test.json')

        # Loads a saved builtin type
        data = [1, 2, 3]
        fs.save_json(data, path)
        saved = fs.load_json(path)
        self.assertEqual(data, saved)

        # Loads a saved custom type with a deserializer
        class TestClass:
            def __init__(self):
                self.x = 10
                self.y = 20

        def deserializer(json_data):
            d = TestClass()
            d.__dict__.update(json_data)
            return d

        data = [TestClass(), TestClass()]
        fs.save_json(data, path, serializer=lambda x: x.__dict__)
        saved = fs.load_json(path, deserializer=deserializer)
        self.assertEqual(len(data), len(saved))
        self.assertIs(TestClass, type(saved[0]))
        self.assertEqual(list(map(lambda x: x.__dict__, data)), list(map(lambda x: x.__dict__, saved)))


class PathUtilsTests(unittest.TestCase):

    def test_expand_path(self):
        # Expands user and returns absolute path
        for exp, actual in [
            (os.path.expanduser('~'), fs.expand_path('~')),
            (os.getcwd(), fs.expand_path('.')),
            (os.path.abspath(os.path.join(os.getcwd(), '../..')), fs.expand_path('../..')),
        ]:
            self.assertEqual(exp, actual)
