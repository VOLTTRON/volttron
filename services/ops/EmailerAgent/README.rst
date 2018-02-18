.. _Emailer

=======
Emailer
=======

The Emailer agent allows an instance of the VOLTTRON platform to send email.
When used in combination with the AlertAgent agent alerts from unpublished
configured devices will automatically be sent.  In addition, agents
are able to send emails directly through the pubsub interface.

Agents needing to send an email through the instance can do so by sending the
following header and message to the emailer topic.  The emailer monitors the
'platform/send_email' topic.  The following is the expected payload for the
message body and the optional header.

Optional Headers
~~~~~~~~~~~~~~~~

Emails by default will be sent to the initial configured email addresses.  The
below headers will overwrite those properties for the current email being sent.

.. code-block:: python

    {
        "from-address": 'foo@bar.com',
        "to-addresses": ['alpha.beta@foo.com', 'bob-and-joe@bar.com']
    }

Required Message Body
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    {
        "subject": "I am a happy camper",
        "message": "This is a big long string message that I am sending"
    }

Example Sending of Email
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    headers = {
        "from-address": 'foo@bar.com',
        "to-addresses": ['alpha.beta@foo.com', 'bob-and-joe@bar.com']
    }

    message = {
        "subject": "I am a happy camper",
        "message": "This is a big long string message that I am sending"
    }

    self.vip.pubsub.publish('pubsub', topic='platform/send_email',
                            headers=headers, message=message)

Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by the ForwardHistorian agent.

.. code-block:: python

    {
        # The smtp-address (Simple Mail Transfer Protocol) to ship the email
        # from the "from-address" to each of the recipients.  This value
        # currently does not support authenticated connections.
        "smtp-address": "smtp.example.com",

        # The sending address of the email.  This value will be listed in the
        # FROM attributed of the message envelop.  It will also be show in the
        # reply of the message when a recipient chooses reply from their
        # email client.
        "from-address": "no-reply@example.com",

        # A list of default email addresses for sending alerts to.  Each
        # address will be sent a copy of the email as if from a mailing list.
        "to-addresses": [
            "admin1@example.com"
        ],

        # When an alert is sent typically it can have the effect of being
        # sent many times.  This setting throttles the sending of email only
        # after a specific number of minutes.
        #
        # DEFAULT: "allow-frequency-minutes": 60
        "allow-frequency-minutes": 120
    }