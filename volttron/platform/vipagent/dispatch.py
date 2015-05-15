
from __future__ import absolute_import, print_function

import weakref


__all__ = ['Signal']


class Signal(object):
    def __init__(self):
        self._receivers = weakref.WeakValueDictionary()

    def connect(self, receiver, owner=None):
        self._receivers[receiver] = receiver if owner is None else owner

    def disconnect(self, receiver):
        try:
            self._receivers.pop(receiver)
            return True
        except KeyError:
            return False

    def send(self, sender, **kwargs):
        return [receiver(sender, **kwargs)
                for receiver in self._receivers]

    def send_via(self, executor, sender, **kwargs):
        return [executor(receiver, sender, **kwargs)
                for receiver in self._receivers]
        
    def receiver(self, func):
        self.connect(func)
        return func
