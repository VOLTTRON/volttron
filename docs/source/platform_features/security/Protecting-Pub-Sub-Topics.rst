.. _Protected-Topics:

Protecting Pub/Sub Topics
=========================

VIP :ref:`authorization <VIP-Authorization>` enables 
VOLTTRON platform owners to protect pub/sub topics. More
specifically, a platform owner can limit who can publish to a given
topic. This protects subscribers on that platform from receiving
messages (on the protected topic) from unauthorized agents.

Example
-------

To protect a topic, add the topic name to
``$VOLTTRON_HOME/protected_topics.json``. For example, the following
protected-topics file declares that the topic ``foo`` is protected:

.. code:: JSON

    {
       "write-protect": [
          {"topic": "foo", "capabilities": ["can_publish_to_foo"]}
       ]
    }

**Note:** The capability name ``can_publish_to_foo`` is not special. It
can be any string, but it is easier to manage capabilities with
meaningful names.

Now only agents with the capability ``can_publish_to_foo`` can publish
to the topic ``foo``. To add this capability to authenticated agents,
run ``vctl auth update`` (or ``volttron-ctl auth add`` for new
authentication entries), and enter ``can_publish_to_foo`` in the capabilities
field:

.. code:: Bash

    capabilities (delimit multiple entries with comma) []: can_publish_to_foo

Agents that have the ``can_publish_to_foo`` capabilites can publish to topic ``foo``.
That is, such agents can call:

.. code:: Python

    self.vip.pubsub.publish('pubsub', 'foo', message='Here is a message')

If unauthorized agents try to publish to topic ``foo`` they will get an exception:

``to publish to topic "foo" requires capabilities ['can_publish_to_foo'], but capability list [] was provided``

Regular Expressions
-------------------

Topic names in ``$VOLTTRON_HOME/protected_topics.json`` can be specified
as regular expressions. In order to use a regular expression, the topic name 
must begin and end with a "/". For example:

.. code:: JSON

    {
       "write-protect": [
          {"topic": "/foo/*.*/", "capabilities": ["can_publish_to_foo"]}
       ]
    }

This protects topics such as ``foo/bar`` and ``foo/anything``.
