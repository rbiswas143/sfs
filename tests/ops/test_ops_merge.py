import collections
import copy
import os
import time

import sfs.core as core
import sfs.file_system as fs
import sfs.helper as sfs_helper
import sfs.ops.ops_merge as ops_merge
import tests.helper as test_helper


class TestDedupMerge(test_helper.TestCaseWithFS):

    def test_get_json_path(self):
        # Generates correct json path for a given target directory
        target_dir = os.path.join(self.TESTS_BASE, 'dir1')
        exp = "{}{}{}".format(
            os.path.join(target_dir, os.path.basename(target_dir)),
            ops_merge.constants['MERGE_FILE_EXTENSION'],
            core.constants['SFS_FILE_EXTENSION']
        )
        self.assertEqual(exp, ops_merge.get_json_path(target_dir))

    def test_serialization(self):
        conflicts = [
            ops_merge.MergeConflict(
                'test/path1',
                target=ops_merge.MergeConflict.FileStats(
                    'file1', size=100, ctime=200, is_link=True, is_dir=False, source_path='source/path1',
                    source_size=300, source_ctime=None, keep=False
                ),
                source=ops_merge.MergeConflict.FileStats(
                    'file2', size=150, ctime=300, is_link=False, is_dir=False, keep=True
                )
            ),
            ops_merge.MergeConflict(
                'test/path3',
                target=ops_merge.MergeConflict.FileStats(
                    'file3', size=370, ctime=600, is_link=True, is_dir=False, source_path=None,
                    source_size=None, source_ctime=400, keep=True
                ),
                source=ops_merge.MergeConflict.FileStats(
                    'file4', size=500, ctime=700, is_link=False, is_dir=True, keep=True
                )
            ),
        ]

        # Serialization of a list of merge conflicts works
        serialized = list(map(lambda c: c.to_dict(), conflicts))
        for conflict, ser in zip(conflicts, serialized):
            self.assertTrue(isinstance(ser, collections.OrderedDict))
            self.assertEqual(['Path', 'Target', 'Source'], list(ser.keys()))
            for con, s in zip([conflict.target, conflict.source], [ser['Target'], ser['Source']]):
                self.assertEqual(con.name, s['Name'])
                self.assertEqual(sfs_helper.get_readable_size(con.size), s['Size'])
                self.assertEqual(time.ctime(con.ctime), s['Last Modified'])
                node_type = 'Directory' if con.is_dir else ('Symlink' if con.is_link else 'File')
                self.assertEqual(node_type, s['Type'])
                keep = 1 if con.keep else 0
                self.assertEqual(keep, s['Keep'])
                if not con.is_link:
                    self.assertEqual(5, len(s))
                else:
                    self.assertEqual('na' if con.source_path is None else con.source_path, s['Source Path'])
                    self.assertEqual(
                        'na' if con.source_size is None else sfs_helper.get_readable_size(con.source_size),
                        s['Source Size']
                    )
                    self.assertEqual(
                        'na' if con.source_ctime is None else time.ctime(con.source_ctime), s['Source Last Modified']
                    )

        # De-serialization of a list of DuplicateLinks works
        deserialized = list(map(lambda ser: ops_merge.MergeConflict.from_dict(ser), serialized))
        for conflict, deser in zip(conflicts, deserialized):
            self.assertTrue(isinstance(deser, ops_merge.MergeConflict))
            self.assertEqual(conflict.path, deser.path)
            for con, ds in zip([conflict.target, conflict.source], [deser.target, deser.source]):
                self.assertIs(con.keep, ds.keep)
                self.assertIs(con.name, ds.name)

    def test_merge(self):
        # Create SFS and collections
        self.create_fs_tree({
            'dirs': {
                'target': {
                    'files': ['file_1', 'file_t'],
                    'links': ['link_1', 'link_t'],
                    'dirs': {
                        'dir_1': {
                            'files': ['file_2', 'file_t2'],
                        },
                        'file_or_dir': {
                            'files': ['file_t1'],
                            'links': ['link_t1']
                        }
                    }
                },
                'source': {
                    'files': ['file_1', 'file_s'],
                    'links': ['link_1', 'link_s'],
                    'dirs': {
                        'dir_1': {
                            'files': ['file_2', 'file_s2'],
                        },
                        'dir_s': {
                            'files': ['file_s1'],
                        }
                    }
                },
                'sfs_root': {}
            }
        })
        sfs_root = os.path.join(self.TESTS_BASE, 'sfs_root')
        target_col_root = os.path.join(self.TESTS_BASE, 'target')
        source_col_root = os.path.join(self.TESTS_BASE, 'source')
        core.SFS.init_sfs(sfs_root)
        sfs = core.SFS.get_by_path(sfs_root)
        sfs.add_collection('target', target_col_root)
        sfs.add_collection('source', source_col_root)

        # Delete collection to generate foreign links
        sfs.del_collection('source')

        # Add additional nodes for testing
        target = os.path.join(sfs_root, 'target')
        source = os.path.join(sfs_root, 'source')
        test_helper.dummy_file(os.path.join(source, 'file_or_dir'))

        # Marks files to keep according to the parameter value
        for mode in ops_merge.constants['MERGE_MODES'].values():
            conflicts = ops_merge.get_merge_conflicts(sfs, target, source, keep=mode)
            target_stats = conflicts[0].target
            source_stats = conflicts[0].source
            if mode == ops_merge.constants['MERGE_MODES']['KEEP_TARGET']:
                self.assertTrue(target_stats.keep)
                self.assertFalse(source_stats.keep)
            elif mode == ops_merge.constants['MERGE_MODES']['KEEP_SOURCE']:
                self.assertFalse(target_stats.keep)
                self.assertTrue(source_stats.keep)
            else:
                self.assertTrue(target_stats.keep)
                self.assertTrue(source_stats.keep)

        # Compute a map of conflict paths to conflict stats
        conflicts = ops_merge.get_merge_conflicts(sfs, target, source)
        conflict_dict = {fs.expand_path(os.path.join(target, con.path)): con for con in conflicts}

        # Identifies all conflicted paths
        exp_conflicts = ['file_1', 'link_1', 'file_or_dir', os.path.join('dir_1', 'file_2')]
        self.assertEqual(len(exp_conflicts), len(conflicts))
        self.assertTrue(all(fs.expand_path(os.path.join(target, path)) in conflict_dict for path in exp_conflicts))

        # Computes correct link stats
        target_stats = conflict_dict[fs.expand_path(os.path.join(target, 'file_1'))].target
        self.assertIsInstance(target_stats, ops_merge.MergeConflict.FileStats)
        self.assertEqual(target_stats.name, 'file_1')
        self.assertEqual(target_stats.size, os.stat(os.path.join(target, 'file_1'), follow_symlinks=False).st_size)
        self.assertEqual(target_stats.ctime, os.stat(os.path.join(target, 'file_1'), follow_symlinks=False).st_ctime)
        self.assertTrue(target_stats.is_link)
        self.assertFalse(target_stats.is_dir)
        self.assertTrue(target_stats.keep)
        self.assertTrue(target_stats.source_path, os.path.join(target_col_root, 'file_1'))
        self.assertTrue(target_stats.source_size, os.stat(os.path.join(target_col_root, 'file_1')).st_size)
        self.assertTrue(target_stats.source_ctime, os.stat(os.path.join(target_col_root, 'file_1')).st_ctime)

        source_stats = conflict_dict[fs.expand_path(os.path.join(target, 'file_1'))].source
        self.assertRegex(source_stats.name, '{}\.merged\.[0-9]+'.format('file_1'))
        self.assertTrue(source_stats.source_path, os.path.join(source_col_root, 'file_1'))
        self.assertIsNone(source_stats.source_size)
        self.assertIsNone(source_stats.source_ctime)

        # Computes file stats correctly
        file_stats = conflict_dict[fs.expand_path(os.path.join(target, 'file_or_dir'))].source
        self.assertRegex(file_stats.name, '{}\.merged\.[0-9]+'.format('file_or_dir'))
        self.assertEqual(file_stats.size, os.stat(os.path.join(source, 'file_or_dir'), follow_symlinks=False).st_size)
        self.assertEqual(file_stats.ctime, os.stat(os.path.join(source, 'file_or_dir'), follow_symlinks=False).st_ctime)
        self.assertFalse(file_stats.is_link)
        self.assertFalse(file_stats.is_dir)
        self.assertIsNone(file_stats.source_path)
        self.assertIsNone(file_stats.source_size)
        self.assertIsNone(file_stats.source_ctime)

        # Computes directory stats correctly
        dir_stats = conflict_dict[fs.expand_path(os.path.join(target, 'file_or_dir'))].target
        self.assertEqual(dir_stats.name, 'file_or_dir')
        self.assertEqual(dir_stats.size, os.stat(os.path.join(target, 'file_or_dir'), follow_symlinks=False).st_size)
        self.assertEqual(dir_stats.ctime, os.stat(os.path.join(target, 'file_or_dir'), follow_symlinks=False).st_ctime)
        self.assertFalse(dir_stats.is_link)
        self.assertTrue(dir_stats.is_dir)
        self.assertIsNone(dir_stats.source_path)
        self.assertIsNone(dir_stats.source_size)
        self.assertIsNone(dir_stats.source_ctime)

        # Validates conflicts correctly

        self.assertIs(ops_merge.validate_merge_conflicts(target, source, conflicts), True)

        copied = copy.deepcopy(conflicts)
        copied_dict = {fs.expand_path(os.path.join(target, con.path)): con for con in copied}
        copied_dict[fs.expand_path(os.path.join(target, 'file_1'))].source.keep = True
        self.assertIs(ops_merge.validate_merge_conflicts(target, source, copied), True)
        copied_dict[fs.expand_path(os.path.join(target, 'file_1'))].source.name = 'file_1'
        self.assertEqual(
            sorted([os.path.join(target, 'file_1'), os.path.join(source, 'file_1')]),
            sorted(ops_merge.validate_merge_conflicts(target, source, copied)))
        copied_dict[fs.expand_path(os.path.join(target, 'file_1'))].target.keep = False
        self.assertIs(ops_merge.validate_merge_conflicts(target, source, copied), True)

        copied = copy.deepcopy(conflicts)
        copied_dict = {fs.expand_path(os.path.join(target, con.path)): con for con in copied}
        copied_dict[fs.expand_path(os.path.join(target, 'file_or_dir'))].target.name = 'dir_1'
        self.assertEqual(
            sorted([os.path.join(target, 'file_or_dir'), os.path.join(target, 'dir_1')]),
            sorted(ops_merge.validate_merge_conflicts(target, source, copied)))

        copied = copy.deepcopy(conflicts)
        copied_dict = {fs.expand_path(os.path.join(target, con.path)): con for con in copied}
        copied_dict[fs.expand_path(os.path.join(target, 'link_1'))].source.keep = True
        copied_dict[fs.expand_path(os.path.join(target, 'link_1'))].source.name = 'link_s'
        self.assertEqual(
            sorted([os.path.join(source, 'link_1'), os.path.join(source, 'link_s')]),
            sorted(ops_merge.validate_merge_conflicts(target, source, copied)))

        # Merges directories using computed conflicts stats and returns updated stats

        conflict_dict[fs.expand_path(os.path.join(target, 'file_1'))].target.keep = False
        conflict_dict[fs.expand_path(os.path.join(target, 'file_1'))].source.keep = True
        conflict_dict[fs.expand_path(os.path.join(target, 'file_or_dir'))].target.keep = False
        conflict_dict[fs.expand_path(os.path.join(target, 'file_or_dir'))].source.keep = True
        conflict_dict[fs.expand_path(os.path.join(target, 'file_or_dir'))].source.name = 'file_or_dir'
        conflict_dict[fs.expand_path(os.path.join(target, 'link_1'))].target.name = 'test_rename_link'

        merge_stats = ops_merge.merge(target, source, conflicts)
        exp_merge_stats = {
            'DIRS_CREATED': 1,
            'DIRS_DELETED': 1,
            'NODES_RENAMED': 1,
            'NODES_DELETED': 3,
            'FILES_MERGED': 1,
            'LINKS_MERGED': 5,
        }
        self.assertEqual(exp_merge_stats, merge_stats)
        self.assertEqual({
            'files': 1,
            'links': 10,
            'dirs': 2
        }, fs.count_nodes(target))
