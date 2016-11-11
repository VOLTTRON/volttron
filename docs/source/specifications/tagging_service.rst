=============================
Tagging service specification
=============================

***********
Description
***********
Tagging service provides VOLTTRON users the ability add semantic tags to
different topics so that topic can be queries by tags instead of specific
topic name or topic name pattern.

********
Taxonomy
********
VOLLTTRON will use tags from
`Project Haystack <http://project-haystack.org/tag>`_.
Tags defined in haystack will be imported into VOLTTRON and grouped by
categories to tag entities.

**********
Dependency
**********

Once data in VOLTTRON has been tagged, users will be able to query topics
based on tags through the historian

********
Features
********

 1. User should be able to tag individual components of a topic such as campus,
    building, device, point etc.
 2. Using the tagging service users should only be able to add tags already
    defined in the volttron taggging schema. New tags should be explicitly added
    to the tagging schema before it can be used to tag topics or topic prefix
 3. Tag inheritance should be supported. For example, tags applied to
    /campus1/building1 should be inherited by /campus1/building1/device1
 4. Users should be able batch process and tag multiple topic names or topic
    prefix using a template. At the end of this, users should be notified about
    the list of topics that did not confirm to the template. This will help users
    to individually add or edit tags for those specific topics
 5. When a value of a tag is changed, users should be prompted to verify if
    this change denotes a new version or a value correction.  If this value
    denotes a new version, then older value of the tag should preserved in a
    history/audit store
 6. When users query for topics based on a tag, the results would correspond
    to the current metadata values. It is up to the calling agent/application to
    periodically query for latest updates if needed.
 7. Allow for count and skip parameters in queries to restrict count and
    allow pagination


***
API
***

1. Get the list of topic groups available
-----------------------------------------
   rpc call to tagging service method *'get_tag_groups'*

2. Get the list of tags for a specific group
--------------------------------------------
   rpc call to tagging service method *'get_group_tags'* with
   parameter *group=<string>*

3. Get the list of tags for a topic_name or topic_name_prefix
-------------------------------------------------------------
   rpc call to tagging service method *get_tags* with
   parameter topic_prefix=<string>

4. Find topic names by tags
---------------------------
   rpc call to tagging service method 'get_topics_by_tags' with the one or
   more of the following tags

   1. and - dictionary of tag and its corresponding values that should be
      matched with AND condition. only topics that contain all the tags in the
      list would be returned
   2. or -  dictionary of tag and its corresponding values that should be
      matched with OR condition. topics that contain any of the tags in the
      list would be returned.
   3. regex_and
   4. regex_or
   5. condition - json query string


5. Query data based on tags
---------------------------
   Use above api to get topics by tags and then use the result to query
   historian's query api.