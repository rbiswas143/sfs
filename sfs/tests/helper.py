import functools
import os
import shutil
import unittest

import sfs.config as config


def dummy_file(path, size=5):
    with open(path, 'w') as out:
        out.seek(size - 1)
        out.write('\0')


def dummy_link(link_path, file_path='dummy_file'):
    os.symlink(file_path, link_path)


def count_files(dir_path):
    count = 0
    for root, dirs, files in os.walk(dir_path):
        count += functools.reduce(lambda _sum, f: _sum + (0 if os.path.islink(os.path.join(root, f)) else 1), files, 0)
    return count


def count_directories(dir_path):
    count = 0
    for root, dirs, files in os.walk(dir_path):
        count += len(dirs)
    return count


def count_symlinks(dir_path):
    count = 0
    for root, dirs, files in os.walk(dir_path):
        count += functools.reduce(lambda _sum, f: _sum + (1 if os.path.islink(os.path.join(root, f)) else 0), files, 0)
    return count


class TestCaseWithFS(unittest.TestCase):
    """
    Base class for all tests which involve creation of file system hierarchies
    - Creates test directory and startup and deletes it during cleanup
    - Provides utilities for creation of file system hierarchies
    """
    TESTS_BASE = config.TEST_DIR

    def setUp(self):
        shutil.rmtree(self.TESTS_BASE, ignore_errors=True)
        os.makedirs(self.TESTS_BASE)

    def tearDown(self):
        shutil.rmtree(self.TESTS_BASE)

    @staticmethod
    def complete_path(path):
        return os.path.join(TestCaseWithFS.TESTS_BASE, path)

    def create_fs_tree(self, tree, base=None):
        """Create the specified directory tree in the tests directory"""

        def _create_path(name):
            return name if base is None else os.path.join(base, name)

        if 'files' in tree:
            for f in tree['files']:
                path = self.complete_path(_create_path(f))
                dummy_file(path)
        if 'links' in tree:
            for l in tree['links']:
                path = self.complete_path(_create_path(l))
                dummy_link(path)
        if 'dirs' in tree:
            for d in tree['dirs'].keys():
                path = self.complete_path(_create_path(d))
                os.mkdir(path)
                self.create_fs_tree(tree['dirs'][d], path)
