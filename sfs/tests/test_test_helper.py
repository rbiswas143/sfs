import os

import sfs.tests.helper as helper


class HelperTests(helper.TestCaseWithFS):

    def test_create_file(self):
        file_path = os.path.join(self.TESTS_BASE, 'test_file')
        file_size = 100
        helper.dummy_file(file_path, file_size)

        # Creates file of specified size
        self.assertTrue(os.path.isfile(file_path))
        self.assertEqual(os.stat(file_path).st_size, 100)

    def test_count_files(self):
        paths = [os.path.join(self.TESTS_BASE, p) for p in [
            'file_a',
            'file_b',
            os.path.join('dir_a', 'file_aa'),
            os.path.join('dir_a', 'file_ab')
        ]]
        for p in paths:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            helper.dummy_file(p)

        # Returns file count
        self.assertEqual(len(paths), helper.count_files(self.TESTS_BASE))

    def test_count_directories(self):
        paths = [os.path.join(self.TESTS_BASE, p) for p in [
            'file_a',
            'file_b',
            os.path.join('dir_a', 'file_aa'),
            os.path.join('dir_b', 'file_ba'),
            os.path.join('dir_c', 'file_ca')
        ]]
        for p in paths:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            helper.dummy_file(p)

        # Returns directory count
        self.assertEqual(3, helper.count_directories(self.TESTS_BASE))

    def test_count_symlinks(self):
        paths = [os.path.join(self.TESTS_BASE, p) for p in [
            'file_a',
            'link_a',
            os.path.join('dir_a', 'link_aa'),
            os.path.join('dir_a', 'link_ab')
        ]]
        for p in paths:
            if 'link' not in p:
                continue
            os.makedirs(os.path.dirname(p), exist_ok=True)
            helper.dummy_link(p)

        # Returns link count
        self.assertEqual(len(paths)-1, helper.count_symlinks(self.TESTS_BASE))


class CreateFSTreeTests(helper.TestCaseWithFS):

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
        self.assertEqual(len(file_paths), helper.count_files(self.TESTS_BASE))
        self.assertEqual(len(dir_paths), helper.count_directories(self.TESTS_BASE))
        self.assertEqual(len(link_paths), helper.count_symlinks(self.TESTS_BASE))
