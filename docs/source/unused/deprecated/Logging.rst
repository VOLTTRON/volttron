Data Logging
------------

A mechanism allowing agents to store timeseries data has been provided.
In VOLTTRON 2.0 this facility was provided by an sMAP agent but it has
now been folded into the new Historians. This service still uses the old
format to maintain compatibility.

Data Logging Format
~~~~~~~~~~~~~~~~~~~

Data sent to the data logger should be sent as a JSON object that
consists of a dictionary of dictionaries. The keys of the outer
dictionary are used as the points to store the data items. The inner
dictionary consists of 2 required fields and 1 optional. The required
fields are "Readings" and "Units". Readings contains the data that will
be written. It may contain either a single value, or a list of lists
which consists of timestamp/value pairs. Units is a string that
identifies the meaning of the scale values of the data. The optional
entry is data\_type, which indicates the type of the data to be stored.
This may be either long or double.

::

    {
        "test3": {
            "Readings": [[1377788595, 1.1],[1377788605,2.0]],
            "Units": "KwH",
            "data_type": "double"
        },
        "test4": {
            "Readings": [[1377788595, 1.1],[1377788605,2.0]],
            "Units": "TU",
            "data_type": "double"
        }
    }

Example Code
~~~~~~~~~~~~

::

            headers[headers_mod.FROM] = self._agent_id
            headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
            
            mytime = int(time.time())
            
            content = {
                "listener": {
                    "Readings": [[mytime, 1.0]],
                    "Units": "TU",
                    "data_type": "double"
                },
                "hearbeat": {
                    "Readings": [[mytime, 1.0]],
                    "Units": "TU",
                    "data_type": "double"
                }
            }
            
            
            
            self.publish('datalogger/log/', headers, json.dumps(content))

