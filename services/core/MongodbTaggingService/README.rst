.. _Mongodb_Tagging_Service:

=======================
Mongodb Tagging Service
=======================

Mongodb tagging service provide APIs to tag both topic names(device points) and
topic name prefixes (campus, building, unit/equipment, sub unit) and then
query for relevant topics based on saved tag names and values. This agent
stores the tags in a mongodb database.

Tags used by this agent are not user defined. They have to be pre-defined in a
resource file at volttron_data/tagging_resources. The agent validates against
this predefined list of tags every time user add tags to topics. Tags can be
added to one topic at a time or multiple topics by using a topic name
pattern(regular expression). This agent uses tags from
`project haystack <https://project-haystack.org/>`_. and adds a few custom
tags for campus and VOLTTRON point name.

Each tag has an associated value and users can query for topic names based
tags and its values using a simplified sql-like query string. Queries can
specify tag names with values or tags without values for boolean tags(markers).
Queries can combine multiple conditions with keyword AND and OR,
and use the keyword NOT to negate a conditions.

Dependencies and Limitations
----------------------------

1. When adding tags to topics, this agent calls the platform.historian's
   get_topic_list and hence requires the platform.historian to be running
   but it doesn't require the historian to use any specific database. It
   does not require platform.historian to be running for using its
   query APIs.
2. Resource files that provides the list of valid tags is mandatory and should
   be in volttron_data/tagging_reosurces/tags.csv
3. Tagging service only provides APIs query for topic names based on tags.
   Once the list of topic names is retrieved, users should use the historian
   APIs to get the data corresponding to those topics.
4. Current version of tagging service does not support versioning of
   tag/values. When tags values set using tagging service APIs update/overwrite
   any existing tag entries in the database

Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by this agent.

.. code-block:: python

    {
        "connection": {
            "type": "mongodb",
            "params": {
                "host": "localhost",
                "port": 27017,
                "database": "test_historian",
                "user": "username for this db. should have read write access",
                "passwd": "password for this db"
            }
        },
        # optional. Specify if collections created for tagging should have names
        # starting with a specific prefix <given prefix>_<collection_name>
        "table_prefix":"volttron",

        # optional. Specify if you want tagging service to query the historian
        # with this vip identity. defaults to platform.historian
        "historian_vip_identity": "crate.historian"
    }

See Also
--------

`TaggingServiceSpec`_