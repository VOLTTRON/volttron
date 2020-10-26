.. _Emailer-Agent:

=============
Emailer Agent
=============

Emailer agent is responsible for sending emails for an instance. It has been written so that any agent on the instance
can send emails through it via the "send_email" method or through the pubsub message bus using the topic
"platform/send_email".

By default any alerts will be sent through this agent. In addition all emails will be published to the
"record/sent_email" topic for a historian to be able to capture that data.


Configuration
=============

A typical configuration for this agent is as follows. We need to specify the SMTP server address, email address of the
sender, email addresses of all the recipients and minimum time for duplicate emails based upon the key.


.. code-block:: python

    {
        "smtp-address": "smtp.foo.com",
        "from-address": "billy@foo.com",
        "to-addresses": ["ann@foo.com", "bob@gmail.com"],
        "allow-frequency-minutes": 10
    }

Finally package, install and start the agent. For more details, see
:ref:`Agent Creation Walk-through <Agent-Development>`
