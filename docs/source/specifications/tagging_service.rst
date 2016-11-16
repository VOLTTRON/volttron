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

******************
Software Interface
******************

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
