import contextlib
import os
import shelve

import gevent

from volttron.utils.persistance import load_create_store
from .registry import PlatformRegistry


class ResourceDirectory:

    def __init__(self):
        self._datafile = os.path.join(os.environ['VOLTTRON_HOME'],
                                      'data/resources.shelve')
        self._store = load_create_store(self._datafile)

        def save_object(key, data):
            if not isinstance(key, basestring):
                raise ValueError('keys must be a string')
            self._store[key] = data
            gevent.spawn(self._store.sync)

        def retrieve_object(key):
            if not isinstance(key, basestring):
                raise ValueError('keys must be a string')

            if not os.path.exists(self._datafile):
                raise KeyError('invalid key')

            return self._store[key]

        self._registry = PlatformRegistry(retrieve_object, save_object)

    @property
    def platform_registry(self):
        return self._registry



