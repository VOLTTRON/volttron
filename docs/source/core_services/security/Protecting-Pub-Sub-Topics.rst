*Note: pubsub-topic protection is a work in progress, and its
implementation is in `a feature
branch <https://github.com/VOLTTRON/volttron/tree/feature/pubsub_auth>`__.*

`VIP
authorization <https://github.com/VOLTTRON/volttron/wiki/VIP-Authorization>`__
enables VOLTTRON platform owners to protect pub/sub topics. More
specifically, a platform owner can limit who can publish to a given
topic. This protects subscribers on that platform from receiving
messages (on the protected topic) from unauthorized agents.

Example
=======

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
edit the file ``$VOLTTRON_HOME/auth.json``:

.. code:: JSON

    {
      "allow": [
        {"user_id": "Alice", "capabilities" : ["can_publish_to_foo"], "credentials": "CURVE:abc...", },
        {"user_id": "Bobby", "credentials": "CURVE:xyz...", },
      ]
    }

(The credentials are abbreviated to simplify the example.)

Alice's agents (i.e., agents that have been authenticated using Alice's
credentials) can publish to topic ``foo``. That is, Alice's agents can
call:

.. code:: Python

    self.vip.pubsub.publish('pubsub', 'foo', message='Here is a message')

Because Bobby's agents do not have the necessary capabilities, if those
agents try to publish to topic ``foo`` they will get an exception:

``to publish to topic "foo" requires capabilities ['can_publish_to_foo'], but capability list [] was provided``

Regular Expressions
-------------------

Topic names in ``$VOLTTRON_HOME/protected_topics.json`` can be specified
as regular expressions. To an regular expression in the topic name begin
and end the name with a "/". For example:

.. code:: JSON

    {
       "write-protect": [
          {"topic": "/foo/*.*/", "capabilities": ["can_publish_to_foo"]}
       ]
    }

This protects topics such as ``foo/bar`` and ``foo/anything``.

Ideas for Improvement
=====================

Read Protection
---------------

Currently, pub/sub protection can only write-protect topics. This is
useful when protecting the integrity of topic's messages. To protect
message confidentiality, we need a read-protection mechanism for
pub/sub.

Usability
---------

Currently, JSON files have to be manually edited to protect a pub/sub
topic. It would be nice to have an interface in ``volttron-ctl`` and/or
VOLTTRON Central for managing protected topics.
