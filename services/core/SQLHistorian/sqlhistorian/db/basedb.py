from __future__ import absolute_import, print_function
from abc import abstractmethod
import importlib
import logging
import threading

from zmq.utils import jsonapi

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


class DbDriver(object):

    def __init__(self, dbapimodule, **kwargs):
        thread_name = threading.currentThread().getName()
        _log.debug("Constructing Driver for {} in thread: {}".format(
            dbapimodule, thread_name)
        )

        self.__dbmodule = importlib.import_module(dbapimodule)
        self.__connection = None
        self.__cursor = None
        self.__connect_params = kwargs

    def __connect(self):
        try:
            if self.__connection is None:
                self.__connection = self.__dbmodule.connect(**self.__connect_params)
            if self.__cursor is None:
                self.__cursor = self.__connection.cursor()

        except Exception as e:
            _log.warning(e.__class__.__name__ + "couldn't connect to database")

        return self.__connection is not None

    @abstractmethod
    def get_topic_map(self):
        pass

    @abstractmethod
    def insert_data_query(self):
        pass

    @abstractmethod
    def insert_topic_query(self):
        pass

    @abstractmethod
    def insert_meta_query(self):
        pass

    def insert_meta(self, topic_id, metadata):
        if not self.__connect():
            return False

        self.__cursor.execute(self.insert_meta_query(), (topic_id, jsonapi.dumps(metadata)))
        return True

    def insert_data(self, ts, topic_id, data):
        if not self.__connect():
            return False

        self.__cursor.execute(self.insert_data_query(), (ts, topic_id, jsonapi.dumps(data)))
        return True

    def insert_topic(self, topic):
        if not self.__connect():
            return False

        self.__cursor.execute(self.insert_topic_query(), (topic, ))
        row = [self.__cursor.lastrowid]
        return row

    def update_topic(self, topic, topic_id):

        self.__connect()

        if self.__connection is None:
            return False

        if not self.__cursor:
            self.__cursor = self.__connection.cursor()

        self.__cursor.execute(self.update_topic_query(), (topic, topic_id))

        return True
    
    def commit(self):
        successful = False
        if self.__connection is not None:
            self.__connection.commit()
            self.__connection.close()
            successful = True
        else:
            _log.warning('connection was null during commit phase.')

        self.__cursor = None
        self.__connection = None
        return successful

    def rollback(self):
        successful = False
        if self.__connection is not None:
            self.__connection.rollback()
            self.__connection.close()
            successful = True
        else:
            _log.warning('connection was null during rollback phase.')

        self.__cursor = None
        self.__connection = None
        return successful

    def select(self, query, args):
        try:
            conn = self.__dbmodule.connect(**self.__connect_params)
        except Exception as e:
            _log.warning(e.__class__.__name__ + "couldn't connect to database")
            conn = None

        if conn is None:
            return []

        cursor = conn.cursor()
        if args is not None:
            cursor.execute(query, args)
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows

    @abstractmethod
    def query(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {} for you)
        """
        pass
