import os

import sfs.file_system as fs
import sfs.tests.helper as test_helper


class HelperTests(test_helper.TestCaseWithFS):

    def test_create_file(self):
        file_path = os.path.join(self.TESTS_BASE, 'test_file')
        file_size = 100
        test_helper.dummy_file(file_path, file_size)

        # Creates file of specified size
        self.assertTrue(os.path.isfile(file_path))
        self.assertEqual(os.stat(file_path).st_size, 100)

    def test_create_symlink(self):
        link_path = os.path.join(self.TESTS_BASE, 'test_link')
        source_path = os.path.join(self.TESTS_BASE, 'source', 'path')
        test_helper.dummy_link(link_path, source_path)

        # Creates link to specified source
        self.assertTrue(os.path.islink(link_path))
        self.assertEqual(os.readlink(link_path), source_path)


class CreateFSTreeTests(test_helper.TestCaseWithFS):

    def test_create_a_file(self):
        tree = {
            'files': ['file_a']
        }
        self.create_fs_tree(tree)

        # Creates files
        exp_file = os.path.join(self.TESTS_BASE, 'file_a')
        self.assertTrue(os.path.isfile(exp_file))

    def test_create_a_directory(self):
        tree = {
            'dirs': {'dir_a': {}}
        }
        self.create_fs_tree(tree)

        # Creates directories
        exp_dir = os.path.join(self.TESTS_BASE, 'dir_a')
        self.assertTrue(os.path.isdir(exp_dir))

    def test_create_a_symlink(self):
        tree = {
            'links': ['link_a']
        }
        self.create_fs_tree(tree)

        # Creates links
        exp_link = os.path.join(self.TESTS_BASE, 'link_a')
        self.assertTrue(os.path.islink(exp_link))

    def test_create_nested_tree(self):
        tree = {
            'files': ['file_a', 'file_b'],
            'links': ['link_a', 'link_b'],
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

        file_paths = [os.path.join(self.TESTS_BASE, x) for x in [
            'file_a',
            'file_b',
            os.path.join('dir_a', 'file_aa'),
            os.path.join('dir_a', 'file_aa'),
            os.path.join('dir_b', 'file_ba'),
            os.path.join('dir_b', 'file_ba'),
        ]]
        for path in file_paths:
            self.assertTrue(os.path.isfile(path))

        dir_paths = [os.path.join(self.TESTS_BASE, x) for x in [
            'dir_a',
            'dir_b',
            os.path.join('dir_a', 'dir_aa'),
            os.path.join('dir_b', 'dir_ba'),
        ]]
        for path in dir_paths:
            self.assertTrue(os.path.isdir(path))

        link_paths = [os.path.join(self.TESTS_BASE, x) for x in [
            'link_a',
            'link_b',
            os.path.join('dir_a', 'link_aa')
        ]]
        for path in link_paths:
            self.assertTrue(os.path.islink(path))

        # Creates files, links and directories in a nested hierarchy
        counts = fs.count_nodes(self.TESTS_BASE)
        self.assertEqual(len(file_paths), counts['files'])
        self.assertEqual(len(dir_paths), counts['dirs'])
        self.assertEqual(len(link_paths), counts['links'])
