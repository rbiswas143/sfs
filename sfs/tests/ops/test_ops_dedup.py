import collections
import os
import time

import sfs.core as core
import sfs.file_system as fs
import sfs.helper as sfs_helper
import sfs.ops.ops_dedup as ops_dedup
import sfs.tests.helper as test_helper


class TestDedupOps(test_helper.TestCaseWithFS):

    def test_get_json_path(self):
        # Generates correct json path for a given target directory
        target_dir = os.path.join(self.TESTS_BASE, 'dir1')
        exp = "{}{}{}".format(
            os.path.join(target_dir, os.path.basename(target_dir)),
            ops_dedup.constants['DEDUP_FILE_EXTENSION'],
            core.constants['SFS_FILE_EXTENSION']
        )
        self.assertEqual(exp, ops_dedup.get_json_path(target_dir))

    def test_serialization(self):
        dups = [
            [
                ops_dedup.DuplicateLink(
                    os.path.join('dir1', 'file1'), os.path.join('col', 'dir1', 'file1'),
                    size=100, ctime=200, keep=1
                ),
                ops_dedup.DuplicateLink(
                    os.path.join('dir2', 'file1'), os.path.join('col', 'dir2', 'file1'),
                    size=100, ctime=200, keep=0
                )
            ],
            [
                ops_dedup.DuplicateLink(
                    os.path.join('dir3', 'file2'), os.path.join('col', 'dir3', 'file2'),
                    size=100, ctime=200, keep=1
                ),
                ops_dedup.DuplicateLink(
                    os.path.join('dir4', 'file2'), os.path.join('col', 'dir4', 'file2'),
                    size=100, ctime=200, keep=0
                )
            ]
        ]

        # Serialization of a list of DuplicateLinks works
        serialized = [list(map(lambda dup_link: dup_link.to_json(), dup_list)) for dup_list in dups]
        self.assertEqual(len(dups), len(serialized))
        for dup_list, ser_list in zip(dups, serialized):
            self.assertEqual(len(dup_list), len(ser_list))
            for d, s in zip(dup_list, ser_list):
                self.assertTrue(isinstance(s, collections.OrderedDict))
                self.assertEqual(['Link Path', 'Source Path', 'Size', 'Last Modified', 'Keep'], list(s.keys()))
                self.assertEqual(d.sfs_path, s['Link Path'])
                self.assertEqual(d.source_path, s['Source Path'])
                self.assertEqual(sfs_helper.get_readable_size(d.size), s['Size'])
                self.assertEqual(time.ctime(d.ctime), s['Last Modified'])
                self.assertEqual(d.keep, s['Keep'])

        # De-serialization of a list of DuplicateLinks works
        deserialized = [list(map(lambda s: ops_dedup.DuplicateLink.from_json(s), ser_list)) for ser_list in serialized]
        for dup_list, deser_list in zip(dups, deserialized):
            self.assertEqual(len(dup_list), len(deser_list))
            for d, s in zip(dup_list, deser_list):
                self.assertTrue(isinstance(s, ops_dedup.DuplicateLink))
                self.assertEqual(d.sfs_path, s.sfs_path)
                self.assertEqual(d.keep, s.keep)

    def test_dedup(self):
        # Setup an SFS and a collection
        sfs_root = os.path.join(self.TESTS_BASE, 'sfs_root')
        os.mkdir(sfs_root)
        col_root = os.path.join(self.TESTS_BASE, 'col_root')
        col_files = [(os.path.join(col_root, rel_path), size) for rel_path, size in [
            (os.path.join('dir1', 'file1'), 100),
            (os.path.join('dir1', 'file2'), 200),
            (os.path.join('dir1', 'file3'), 500),
            (os.path.join('dir2', 'file1'), 100),
            (os.path.join('dir2', 'file2'), 300),
            (os.path.join('dir2', 'file4'), 500),
            (os.path.join('dir3', 'file2'), 200),
        ]]
        for col_file, size in col_files:
            os.makedirs(os.path.dirname(col_file), exist_ok=True)
            test_helper.dummy_file(col_file, size)

        # Create SFS and add a collection
        core.SFS.init_sfs(sfs_root)
        sfs = core.SFS.get_by_path(sfs_root)
        sfs.add_collection('col', col_root)

        exp = [
            [
                ops_dedup.DuplicateLink(
                    os.path.join('col', 'dir1', 'file1'), source_path=os.path.join(col_root, 'dir1', 'file1'),
                    size=100, keep=1
                ),
                ops_dedup.DuplicateLink(
                    os.path.join('col', 'dir2', 'file1'), source_path=os.path.join(col_root, 'dir2', 'file1'),
                    size=100, keep=0
                )
            ],
            [
                ops_dedup.DuplicateLink(
                    os.path.join('col', 'dir1', 'file2'), source_path=os.path.join(col_root, 'dir1', 'file2'),
                    size=200, keep=1
                ),
                ops_dedup.DuplicateLink(
                    os.path.join('col', 'dir3', 'file2'), source_path=os.path.join(col_root, 'dir3', 'file2'),
                    size=200, keep=0
                )
            ]
        ]

        # Returns list of duplicate files
        dups = ops_dedup.find_dups(sfs, sfs_root, keep='first')
        self.assertEqual(len(exp), len(dups))
        for exp_list, dup_list in zip(exp, dups):
            self.assertEqual(len(exp_list), len(dup_list))
            for e, d in zip(exp_list, dup_list):
                self.assertTrue(isinstance(e, ops_dedup.DuplicateLink))
                self.assertEqual(e.sfs_path, d.sfs_path)
                self.assertEqual(e.source_path, d.source_path)
                self.assertEqual(e.size, d.size)
                self.assertEqual(e.keep, d.keep)

        # Marks files for deletion according to the parameter keep
        dups2 = ops_dedup.find_dups(sfs, sfs_root, keep='all')
        for dup_list in dups2:
            for d in dup_list:
                self.assertEqual(1, d.keep)

        # Deletes files marked for deletion
        del_count = ops_dedup.del_dups(sfs_root, dups)
        self.assertEqual(2, del_count)
        self.assertTrue(os.path.isfile(os.path.join(sfs_root, 'col', 'dir1', 'file1')))
        self.assertFalse(os.path.isfile(os.path.join(sfs_root, 'col', 'dir2', 'file1')))
        self.assertTrue(os.path.isfile(os.path.join(sfs_root, 'col', 'dir1', 'file2')))
        self.assertFalse(os.path.isfile(os.path.join(sfs_root, 'col', 'dir3', 'file2')))
        self.assertEqual(5, fs.count_nodes(sfs_root)['links'])
