.. _External_Data_Publisher_Agent:

=============================
External Data Publisher Agent
=============================

The External Data Publisher agent (ExternalData) was created to fetch data from remote APIs
based on configured values and publish the remote data on the VOLTTRON message bus. The agent
is primarily an agent wrapper around the requests library that sends the request then
broadcast it via VIP pub/sub publish.

Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported by the
ExternalData agent. Configuration values specify the interval between remote data polling
requests, default authentication for remote API calls, VOLTTRON message bus publish topics,
and for defining the remote API request behavior. Below is an example configuration file
with additional parameter documentation.

.. code-block:: python

    {
        #Interval at which to scrape the sources.
        "interval":300,

        #Global topic prefix for all publishes.
        "global_topic_prefix": "record",

        #Default user name and password if all sources require the same
        #credentials. Can be overridden in individual sources.
        #"default_user":"my_user_name",
        #"default_password" : "my_password",

        "sources":
        [
         {
            #Valid types are "csv", "json", and "raw"
            #Defaults to "raw"
            "type": "csv",
            #Source URL for CSV data.
            "url": "https://example.com/example",

            #URL parameters for data query (optional).
            # See https://en.wikipedia.org/wiki/Query_string
            "params": {"period": "currentinterval",
                       "format": "csv"},

            #Topic to publish on.
            "topic": "example/examplecsvdata1",

            #Column used to break rows in CSV out into separate publishes.
            #The key will be removed from the row data and appended to the end
            # of the publish topic.
            # If this option is missing the entire CSV will be published as a list
            # of objects.
            #If the column does not exist nothing will be published.
            "key": "Key Column",

            #Attempt to parse these columns in the data into numeric types.
            #Currently columns are parsed with ast.literal_eval()
            #Values that fail to parse are left as strings unless the
            # values is an empty string. Empty strings are changed to None.
            "parse": ["Col1", "Col2"],

            #Source specific authentication.
            "user":"username",
            "password" : "password"
         },
         {
            #Valid types are "csv", "json", and "raw"
            #Defaults to "raw"
            "type": "csv",
            #Source URL for CSV data.
            "url": "https://example.com/example_flat",

            #URL parameters for data query (optional).
            # See https://en.wikipedia.org/wiki/Query_string
            "params": {"format": "csv"},

            #Topic to publish on. (optional)
            "topic": "example/examplecsvdata1",

            #If the rows in a csv represent key/value pairs use this
            #setting to reduce this format to a single object for publishing.
            "flatten": true,

            #Attempt to parse these columns in the data into numeric types.
            #Currently columns are parsed with ast.literal_eval()
            #Values that fail to parse are left as strings unless the
            # values is an empty string. Empty strings are changed to None.
            "parse": ["Col1", "Col2"]
         },
         {
            #Valid types are "csv", "json", and "raw"
            #Defaults to "raw"
            "type": "json",
            #Source URL for JSON data.
            "url": "https://example.com/api/example1",

            #URL parameters for data query (optional)
            # See https://en.wikipedia.org/wiki/Query_string
            "params": {"format": "json"},

            #Topic to publish on. (optional)
            "topic": "example/exampledata1",

            #Path to desired data withing the JSON. Optional.
            #Elements in a path may be either a string or an integer.
            #Useful for peeling off unneeded layers around the wanted data.
            "path": ["parentobject", "0"],

            #After resolving the path above if the resulting data is a list
            # the key is the path to a value in a list item. Each item in the list
            # is published separately with the key appended to the end of the topic.
            # Elements in a key may be a string or an integer. (optional)
            "key": ["Location", "$"],

            #Source specific authentication.
            "user":"username",
            "password" : "password"
         }
        ]
    }
