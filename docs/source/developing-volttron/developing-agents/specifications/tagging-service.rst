.. _Tagging-Service-Specification:

===============
Tagging Service
===============

***********
Description
***********
Tagging service provides VOLTTRON users the ability to add semantic tags to
different topics so that topic can be queried by tags instead of specific
topic name or topic name pattern.

********
Taxonomy
********
VOLLTTRON will use tags from
`Project Haystack <http://project-haystack.org/tag>`_.
Tags defined in haystack will be imported into VOLTTRON and grouped by
categories to tag topics and topic name prefix.

**********
Dependency
**********

Once data in VOLTTRON has been tagged, users will be able to query topics
based on tags and use the resultant topics to query the historian

********
Features
********

 1. User should be able to tag individual components of a topic such as campus,
    building, device, point etc.
 2. Using the tagging service users should only be able to add tags already
    defined in the volttron tagging schema. New tags should be explicitly added
    to the tagging schema before it can be used to tag topics or topic prefix
 3. Users should be able batch process and tag multiple topic names or topic
    prefix using a template. At the end of this, users should be notified about
    the list of topics that did not confirm to the template. This will help users
    to individually add or edit tags for those specific topics
 4. When users query for topics based on a tag, the results would correspond
    to the current metadata values. It is up to the calling agent/application
    to periodically query for latest updates if needed.
 5. Users should be able query based on tags on a specific topic or its topic
    prefix/parents
 6. Allow for count and skip parameters in queries to restrict count and
    allow pagination

***
API
***

1. Get the list of tag categories available
-------------------------------------------
rpc call to tagging service method **'get_categories'** with optional parameters:

    1. **include_description** - set to True to return available description
       for each category. Default = False
    2. **skip** - number of categories to skip. this parameter along with count can be
       used for paginating results
    3. **count** - limit the total number of tag categories returned to given count
    4. **order** - ASCENDING or DESCENDING. By default, it will be sorted in
       ascending order

2. Get the list of tags for a specific category
-----------------------------------------------
rpc call to tagging service method **'get_tags_by_category'** with parameter:

    1. **category** - <category name>

    and optional parameters:

    2. **include_kind** - indicate if result should include the
        kind/data type for tags returned. Defaults to False
    3. **include_description** - indicate if result should include
        available description for tags returned. Defaults to False
    4. **skip** - number of tags to skip. this parameter along with count can be
       used for paginating results
    5. **count** - limit the total number of tags returned to given count
    6. **order** - ASCENDING or DESCENDING. By default, it will be sorted in
       ascending order

3. Get the list of tags for a topic_name or topic_name_prefix
-------------------------------------------------------------
rpc call to tagging service method **get_tags_by_topic**

with parameter
    1. **topic_prefix** - topic name or topic name prefix

and optional parameters:

    2. **include_kind** - indicate if result should include the
        kind/data type for tags returned. Defaults to False
    3. **include_description** - indicate if result should include
        available description for tags returned. Defaults to False
    4. **skip** - number of tags to skip. this parameter along with count can be
       used for paginating results
    5. **count** - limit the total number of tags returned to given count
    6. **order** - ASCENDING or DESCENDING. By default, it will be sorted in
       ascending order

4. Find topic names by tags
---------------------------
rpc call to tagging service method **'get_topics_by_tags'** with the one or
more of the following parameters

    1. **and_condition** - dictionary of tag and its corresponding values that
       should be matched using equality operator or a list of tags that should
       exists/be true. Tag conditions are combined with AND condition. Only
       topics that match all the tags in the list would be returned
    2. **or_condition** -  dictionary of tag and its corresponding values that
       should be matched using equality operator or a list tags that should
       exist/be true. Tag conditions are combined with OR condition.
       Topics that match any of the tags in the list would be returned.
       If both **and_condition** and **or_condition** are provided then they
       are combined using AND operator.
    3. **condition** - conditional statement to be used for matching tags. If
       this parameter is provided the above two parameters are ignored. The
       value for this parameter should be an expression that contains one or
       more query conditions combined together with an "AND" or "OR".
       Query conditions can be grouped together using parenthesis.
       Each condition in the expression should conform to one of the following format:

       1. <tag name/ parent.tag_name> <binary_operator> <value>
       2. <tag name/ parent.tag_name>
       3. <tag name/ parent.tag_name> LIKE <regular expression within single quotes
       4. the word NOT can be prefixed before any of the above three to negate
          the condition.
       5. expressions can be grouped with parenthesis.

       For example

          .. code-block:: python

            condition="tag1 = 1 and not (tag2 < '' and tag2 > '') and tag3 and NOT tag4 LIKE '^a.*b$'"
            condition="NOT (tag5='US' OR tag5='UK') AND NOT tag3 AND NOT (tag4 LIKE 'a.*')"
            condition="campusRef.geoPostalCode='20500' and equip and boiler"

    6. **skip** - number of topics to skip. this parameter along with count can be
       used for paginating results
    7. **count** - limit the total number of tag topics returned to given count
    8. **order** - ASCENDING or DESCENDING. By default, it will be sorted in
       ascending order


5. Query data based on tags
---------------------------
Use above api to get topics by tags and then use the result to query
historian's query api.

6. Add tags to specific topic name or topic name prefix
-------------------------------------------------------
rpc call to to tagging service method **'add_topic_tags'** with parameters:

    1. **topic_prefix** - topic name or topic name prefix
    2. **tags** - {<valid tag>:value, <valid_tag>: value,... }
    3. **update_version** - True/False. Default to False. If set to True and if any
       of the tags update an existing tag value the older value would be preserved
       as part of tag version history. **NOTE:** This is a placeholder.
       Current version does not support versioning.

7. Add tags to multiple topics
------------------------------
rpc call to to tagging service method **'add_tags'** with parameters:

    1. **tags** - dictionary object containing the topic and the tag details.
       format:

       .. code-block:: python

            <topic_name or prefix or topic_name pattern>: {<valid tag>:<value>, ... }, ... }

    2. **update_version** - True/False. Default to False. If set to True and if any
       of the tags update an existing tag value the older value would be preserved
       as part of tag version history


*****************
Use case examples
*****************

1. Loading news tags for an existing VOLTTRON instance
------------------------------------------------------

Current topic names:

| /campus1/building1/deviceA1/point1
| /campus1/building1/deviceA1/point2
| /campus1/building1/deviceA1/point3
| /campus1/building1/deviceA2/point1
| /campus1/building1/deviceA2/point2
| /campus1/building1/deviceA2/point3
| /campus1/building1/deviceB1/point1
| /campus1/building1/deviceB1/point2
| /campus1/building1/deviceB2/point1
| /campus1/building1/deviceB1/point2


Step 1:
^^^^^^^
Create a python dictionary object contains topic name pattern and its
corresponding tag/value pair. Use topic pattern names to fill out tags that
can be applied to more than one topic or topic prefix. Use specific topic name
and topic prefix for tags that apply only to a single entity. For example:

    .. code-block:: python

        {
        # tags specific to building1
        '/campus1/building1':
            {
            'site': true,
            'dis': ": 'some building description',
            'yearBuilt': 2015,
            'area': '24000sqft'
            },
        # tags that apply to all device of a specific type
        '/campus1/building1/deviceA*':
            {
            'dis': "building1 chilled water system - CHW",
            'equip': true,
            'campusRef':'campus1',
            'siteRef': 'campus1/building1',
            'chilled': true,
            'water' : true,
            'secondaryLoop': true
            }
        # tags that apply to point1 of all device of a specific type
        '/campus1/building1/deviceA*/point1':
            {
            'dis': "building1 chilled water system - point1",
            'point': true,
            'kind': 'Bool',
            'campusRef':'campus1',
            'siteRef': 'campus1/building1'
            }
        # tags that apply to point2 of all device of a specific type
        '/campus1/building1/deviceA*/point2':
            {
            'dis': "building1 chilled water system - point2",
            'point': true,
            'kind': 'Number',
            'campusRef':'campus1',
            'siteRef': 'campus1/building1'
            }
        # tags that apply to point3 of all device of a specific type
        '/campus1/building1/deviceA*/point3':
            {
            'dis': "building1 chilled water system - point3",
            'point': true,
            'kind': 'Number',
            'campusRef':'campus1',
            'siteRef': 'campus1/building1'
            }
        # tags that apply to all device of a specific type
        '/campus1/building1/deviceB*':
            {
            'dis': "building1 device of type B",
            'equip': true,
            'chilled': true,
            'water' : true,
            'secondaryLoop': true,
            'campusRef':'campus1',
            'siteRef': 'campus1/building1'
            }
        # tags that apply to point1 of all device of a specific type
        '/campus1/building1/deviceB*/point1':
            {
            'dis': "building1 device B - point1",
            'point': true,
            'kind': 'Bool',
            'campusRef':'campus1',
            'siteRef': 'campus1/building1',
            'command':true
            }
        # tags that apply to point1 of all device of a specific type
        '/campus1/building1/deviceB*/point2':
            {
            'dis': "building1 device B - point2",
            'point': true,
            'kind': 'Number',
            'campusRef':'campus1',
            'siteRef': 'campus1/building1'
            }
        }

Step 2: Create tags using template above
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Make an RPC call to the add_tags method and pass the python dictionary object

Step 3: Create tags specific to a point or device
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Any tags that were not included in step one and needs to be added later can be
added using the rpc call to tagging service either the method
**'add_topic_tags'** **'add_tags'**

 For example:

    .. code-block:: python

        agent.vip.rpc.call(
                'platform.tagging',
                'add_topic_tags',
                topic_prefix='/campus1/building1/deviceA1',
                tags={'tag1':'value'})


    .. code-block:: python

        agent.vip.rpc.call(
                'platform.tagging',
                'add_topic_tags',
                tags={
                    '/campus1/building1/deviceA2':
                        {'tag1':'value'},
                    '/campus1/building1/deviceA2/point1':
                        {'equipRef':'campus1/building1/deviceA2'}
                     }
                )



2. Querying based on a topic's tag and it parent's tags
-------------------------------------------------------

Query - Find all points that has the tag 'command' and belong to a device/unit
that has a tag 'chilled'

.. code-block:: python

    agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            condition='temperature and equip.chilled)

In the above code block 'command' and 'chilled' are the tag names that would be
searched, but since the tag 'chilled' is prefixed with 'equip.' the tag in a parent topic

The above query would match the topic '/campus1/building1/deviceB1/point1' if
tags in the system are as follows

'/campus1/building1/deviceB1/point1' tags:

.. code-block:: python

        {
        'dis': "building1 device B - point1",
        'point': true,
        'kind': 'Bool',
        'campusRef':'campus1',
        'siteRef': 'campus1/building1',
        'equipRef': 'campus1/building1/deviceB1',
        'command':true
        }

'/campus1/building1/deviceB1' tags

.. code-block:: python

        {
        'dis': "building1 device of type B",
        'equip': true,
        'chilled': true,
        'water' : true,
        'secondaryLoop': true,
        'campusRef':'campus1',
        'siteRef': 'campus1/building1'
        }




****************************
Possible future improvements
****************************
    1. Versioning - When a value of a tag is changed, users should be prompted
       to verify if this change denotes a new version or a value correction.
       If this value denotes a new version, then older value of the tag should
       preserved in a history/audit store
    2. Validation of tag values based on data type
    3. Support for units validation and  conversions
    4. Processing and saving geologic coordinates that can enable users to do
       geo-spatial queries in databases that support it.
