import pkgutil
from abc import abstractmethod


class DbDriver(object):
    
    @abstractmethod
    def get_topic_map(self):
        '''
        Data
        '''
        pass

    @abstractmethod
    def insert_data(self, ts, topic_id, data):
        pass
    
    @abstractmethod
    def insert_topic(self, topic, commit=True):
        pass
    
    @abstractmethod                        
    def query(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {} for you)
        """
        pass