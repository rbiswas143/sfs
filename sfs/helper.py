import collections
import functools

import sfs.exceptions as exceptions
import sfs.log_utils as log


# Exceptions


class Disallowed(exceptions.SFSException):
    """Exception class for attempts to perform restricted operations"""
    pass


# Development Utils

def untested(x):
    """Decorator to mark a class or function as untested"""
    log.logger.warn('A component has been marked untested: %s', x.__name__)
    return x


# Decorators


def wraps_class(cls):
    """
    Updates attributes of wrapper class to match that of wrapped class similar to what functools.wraps does for
    functions
    """

    def decorator(wrapper):
        for attr in functools.WRAPPER_ASSIGNMENTS:
            if hasattr(cls, attr):
                setattr(wrapper, attr, getattr(cls, attr))
        return wrapper

    return decorator


def frozen(cls):
    """Marks a class as readonly after instantiation"""

    @functools.wraps(cls, updated=[])
    class FrozenClassWrapper(cls):
        def __init__(self, *args, **kwargs):
            cls.__init__(self, *args, **kwargs)
            self._frozen = True

        def __setattr__(self, key, value):
            if hasattr(self, '_frozen') and self._frozen is True:
                raise Disallowed('Cannot update frozen object of class "{}"'.format(type(self).__name__))
            cls.__setattr__(self, key, value)

    return FrozenClassWrapper


def has_cached_methods(cls):
    """Enables caching on class methods"""

    @wraps_class(cls)
    class CachedMethodsWrapper(cls):
        def __init__(self, *args, **kwargs):
            cls.__init__(self, *args, **kwargs)
            self._cached_methods = collections.defaultdict(collections.OrderedDict)

    return CachedMethodsWrapper


def cached_method(cache_size=100):
    """
    Decorator to cache the output of class method by its positional arguments
    Up tp 'cache_size' values are cached per method and entries are remvoed in a FIFO order
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            _dict = self._cached_methods[fn.__name__]
            if args in _dict:
                return _dict[args]
            res = fn(self, *args, **kwargs)
            if len(_dict) >= cache_size:
                _dict.popitem(False)
            _dict[args] = res
            return res

        return wrapper

    return decorator


# Utils


def with_default(val_or_func, default):
    if callable(val_or_func):
        return lambda val: default if val is None else val_or_func(val)
    return default if val_or_func is None else val_or_func


def get_readable_size(size_bytes):
    """Convert size in bytes to human readable string"""
    temp = size_bytes
    units = ['Bytes', 'kB', 'MB', 'GB']
    for x in range(len(units)):
        if temp >= 1024 and x < (len(units) - 1):
            temp = float(temp) / 1024
            continue
        break
    return '%.2f %s' % (temp, units[x])


# Unused


class ConstantsMetaClass(type):
    """Metaclass to prevent modification of class attributes"""

    def __setattr__(self, key, value):
        raise Disallowed('Cannot modify constant class')


def constant_class(cls):
    """
    Decorator to mark a class as a constant class
    Constant classes cannot be instantiated and their class attributes cannot be updated
    """

    class ConstantClassWrapper(cls, metaclass=ConstantsMetaClass):
        def __new__(cls):
            raise Disallowed('Cannot instantiate constant class')

    return ConstantClassWrapper
