# Module copied from
# http://code.activestate.com/recipes/576642-persistent-dict-with-multiple-standard-file-format/
import csv
import os
import shutil
import shelve
import logging
import pickle

from volttron.platform import jsonapi

from threading import Thread
from queue import Queue
from copy import deepcopy

_log = logging.getLogger(__name__)


def load_create_store(filename):
    persist = PersistentDict(filename=filename, flag='c', format='json')
    return persist


class PersistentDict(dict):
    """ Persistent dictionary with an API compatible with shelve and anydbm.

    The dict is kept in memory, so the dictionary operations run as fast as
    a regular dictionary.

    Write to disk is delayed until close or sync (similar to gdbm's fast mode).

    Input file format is automatically discovered.
    Output file format is selectable between pickle, json, and csv.
    All three serialization formats are backed by fast C implementations.

    """

    _event_queue = Queue()
    _process_thread = None

    def __init__(self, filename, flag='c', mode=None,
                 format='pickle', *args, **kwds):
        self.flag = flag                    # r=readonly, c=create, or n=new
        self.mode = mode                    # None or an octal triple like 0644
        self.format = format                # 'csv', 'json', or 'pickle'
        self.filename = filename
        if flag != 'n' and os.access(filename, os.R_OK):
            fileobj = open(filename, 'rb' if format == 'pickle' else 'r')
            with fileobj:
                self._load(fileobj)

        if PersistentDict._process_thread is None:
            PersistentDict._process_thread = Thread(target=PersistentDict._process_loop)
            PersistentDict._process_thread.daemon = True  # Don't wait on thread to exit.
            PersistentDict._process_thread.start()

        dict.__init__(self, *args, **kwds)

    @staticmethod
    def _process_loop():
        while True:
            filename, contents, format, mode = PersistentDict._event_queue.get()

            PersistentDict._update_file(filename, contents, format, mode)


    def sync(self):
        """ Write dict to disk """
        if self.flag == 'r':
            return
        PersistentDict._update_file(self.filename, self, self.format, self.mode)

    def async_sync(self):
        """Write dict to disk via worker thread. Don't mix with sync if it can be helped"""
        if self.flag == 'r':
            return
        PersistentDict._event_queue.put((self.filename, deepcopy(self), self.format, self.mode))

    @staticmethod
    def _update_file(filename, contents, format, mode):
        #If we are empty delete the store if it exists.
        if not contents:
            try:
                os.remove(filename)
            except OSError:
                pass
            return

        tempname = filename + '.tmp'
        fileobj = open(tempname, 'wb' if format == 'pickle' else 'w')
        try:
            PersistentDict._dump(fileobj, contents, format)
        except Exception:
            os.remove(tempname)
            _log.error("Unable to sync to file {}".format(filename))
        finally:
            fileobj.close()
        shutil.move(tempname, filename)  # atomic commit
        if mode is not None:
            os.chmod(filename, mode)


    def close(self):
        self.sync()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    @staticmethod
    def _dump(fileobj, contents, format):
        if format == 'csv':
            csv.writer(fileobj).writerows(contents.items())
        elif format == 'json':
            jsonapi.dump(contents, fileobj, separators=(',', ':'))
        elif format == 'pickle':
            pickle.dump(dict(contents), fileobj, 2)
        else:
            raise NotImplementedError('Unknown format: ' + repr(self.format))

    def _load(self, fileobj):
        # try formats from most restrictive to least restrictive
        for loader in (pickle.load, jsonapi.load, csv.reader):
            fileobj.seek(0)
            try:
                return self.update(loader(fileobj))
            except Exception:
                pass
        raise ValueError('File not in a supported format')


if __name__ == '__main__':
    import random

    # Make and use a persistent dictionary
    with PersistentDict('/tmp/demo.json', 'c', format='json') as d:
        print(d, 'start')
        d['abc'] = '123'
        d['rand'] = random.randrange(10000)
        print(d, 'updated')

    # Show what the file looks like on disk
    with open('/tmp/demo.json', 'rb') as f:
        print(f.read())
