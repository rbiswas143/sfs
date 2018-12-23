import os
import pkgutil
import importlib

_ops_module_prefix = 'ops_'


def import_ops():
    """Import all CLI modules in the current package"""
    for _, name, ispkg in pkgutil.iter_modules([os.path.dirname(__file__)]):
        if ispkg:
            continue
        if name.startswith(_ops_module_prefix):
            importlib.import_module('.' + name, __name__)
