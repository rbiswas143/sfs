import os

import sfs.core as core
import sfs.ops.ops_query as ops_query
import sfs.tests.helper as test_helper


class TestQueryOps(test_helper.TestCaseWithFS):

    def test_compute_directory_stats(self):
        sfs_root = os.path.join(self.TESTS_BASE, 'sfs_root')
        os.mkdir(sfs_root)
        col_name = 'col'
        col_root = os.path.join(self.TESTS_BASE, 'col_root')

        # Create collection files
        col_files = [(os.path.join(col_root, path), size) for path, size in [
            ('file_a', 100),
            ('file_b', 200),
            (os.path.join('dir_a', 'file_aa'), 300),
        ]]
        for path, size in col_files:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            test_helper.dummy_file(path, size)

        # Create SFS and collection
        core.SFS.init_sfs(sfs_root)
        sfs = core.SFS.get_by_path(sfs_root)
        sfs.add_collection(col_name, col_root)
        col = sfs.get_collection_by_name(col_name)

        # Create an orphan link
        stat_path = os.path.join(col.stats_base, 'file_a')
        os.unlink(stat_path)

        # Add a foreign link
        foreign_link = os.path.join(sfs_root, 'foreign_link')
        test_helper.dummy_link(foreign_link)

        # Must return correct directory stats
        dir_stats = ops_query.compute_directory_stats(sfs, sfs_root)
        self.assertEqual(dir_stats.size, 500)
        # self.assertEqual(dir_stats.files, 0)
        self.assertEqual(dir_stats.sub_directories, 2)
        self.assertEqual(dir_stats.active_links, 2)
        self.assertEqual(dir_stats.foreign_links, 1)
        self.assertEqual(dir_stats.orphan_links, 1)
        max_ctime = max(map(lambda path: os.stat(path[0]).st_ctime, col_files))
        self.assertEqual(dir_stats.ctime, max_ctime)
