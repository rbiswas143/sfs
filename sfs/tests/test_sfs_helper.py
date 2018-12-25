import unittest

import sfs.helper as sfs_helper


class FrozenClassTests(unittest.TestCase):

    def test_frozen(self):
        @sfs_helper.frozen
        class TestClass:

            def __init__(self, test1, test2):
                self.test1 = test1
                self.test2 = test2

        obj = TestClass(10, 'test')

        # Attributes are set in the constructor
        self.assertEqual(obj.test1, 10)
        self.assertEqual(obj.test2, 'test')

        # Attributes cannot be modified
        with self.assertRaises(sfs_helper.Disallowed):
            obj.test1 = 20

        # New attributes cannot be added
        with self.assertRaises(sfs_helper.Disallowed):
            obj.test3 = 'test2'

        # Attribute values do not change
        self.assertEqual(obj.test1, 10)


class CacheTests(unittest.TestCase):

    def test_cached_property(self):
        @sfs_helper.has_cached_methods
        class TestClass:

            def __init__(self, x):
                self.x = x

            @sfs_helper.cached_method(cache_size=10)
            def test1(self, a):
                return self.x + a

        obj = TestClass(10)

        # Computes function the first time
        self.assertEqual(40, obj.test1(30))
        obj.x = 20

        # Returns cached value the second time
        self.assertEqual(40, obj.test1(30))

        # Computes value for an un-cached key
        self.assertEqual(35, obj.test1(15))

        # Computes function again once the cache limit is exceeded
        for i in range(10):
            obj.test1(i)
        self.assertEqual(50, obj.test1(30))

        # Caches are not shared between instances
        other = TestClass(5)
        self.assertEqual(35, other.test1(30))

    def test_cached_property_with_frozen_class(self):
        @sfs_helper.frozen
        @sfs_helper.has_cached_methods
        class TestClass:

            def __init__(self, x):
                self.x = [x]

            @sfs_helper.cached_method(cache_size=10)
            def test1(self, a):
                self.x[0] += 1
                return self.x[0] + a

        # Can create an object
        obj = TestClass(10)

        # Caching still works
        self.assertEqual(16, obj.test1(5))
        self.assertEqual(16, obj.test1(5))


class FileSizeHelperTests(unittest.TestCase):

    def test_with_default(self):
        # Returns value if not None else default
        default = 1
        self.assertEqual(10, sfs_helper.with_default(10, default))
        self.assertEqual(default, sfs_helper.with_default(None, default))

        # Wraps functions to make them yield defaults
        def test_func(x):
            return x * 2

        default = -1
        self.assertEqual(20, sfs_helper.with_default(test_func, default)(10))
        self.assertEqual(default, sfs_helper.with_default(test_func, default)(None))

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
            self.assertEqual(sfs_helper.get_readable_size(test), res)


class ConstantsClassTests(unittest.TestCase):

    def test_constants_class(self):
        @sfs_helper.constant_class
        class TestConstantsClass:
            CONSTANT_1 = 10
            CONSTANT_2 = 'test'

        # Cannot instantiate
        with self.assertRaises(sfs_helper.Disallowed):
            TestConstantsClass()

        # Cannot update class variables
        with self.assertRaises(sfs_helper.Disallowed):
            TestConstantsClass.CONSTANT_1 = 20

        # Cannot create new class variables
        with self.assertRaises(sfs_helper.Disallowed):
            TestConstantsClass.CONSTANT_3 = 100
