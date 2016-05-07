import contextlib
import os
import shelve
from .registry import PlatformRegistry


class ResourceDirectory:

    def __init__(self):
        self._datafile = os.path.join(os.environ['VOLTTRON_HOME'],
                                      'data/resources.shelve')

        def save_object(key, data):
            if not isinstance(key, basestring):
                raise ValueError('keys must be a string')

            with contextlib.closing(
                    shelve.open(self._datafile, 'c')) as shelf:
                shelf[key] = data

        def retrieve_object(key):
            if not isinstance(key, basestring):
                raise ValueError('keys must be a string')

            if not os.path.exists(self._datafile):
                raise KeyError('invalid key')

            with contextlib.closing(
                    shelve.open(self._datafile, 'r')) as shelf:
                return shelf[key]

        self._registry = PlatformRegistry(retrieve_object, save_object)

    @property
    def platform_registry(self):
        return self._registry



