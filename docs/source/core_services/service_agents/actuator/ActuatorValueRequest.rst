.. _ActuatorValueRequest:

ActuatorAgent Interaction
-------------------------

Once an Task has been scheduled and the time slot for one or more of the
devices has started an agent may interact with the device using the
**get** and **set** topics.

Both **get** and **set** are responded to the same way. See
[#ActuatorReply Actuator Reply] below.

Getting values
~~~~~~~~~~~~~~

While the sMap driver for a device should always be setup to
periodically broadcast the state of a device you may want an up to the
moment value for an actuation point on a device.

To request a value publish a message to the following topic:

::

    #python
    'devices/actuators/get/<full device path>/<actuation point>'

Setting Values
~~~~~~~~~~~~~~

Value are set in a similar manner:

To set a value publish a message to the following topic:

::

    #python
    'devices/actuators/set/<full device path>/<actuation point>'

With this header:

::

    #python
    {
        'requesterID': <Ignored, VIP Identity used internally>
    }

And the message contents being the new value of the actuator.

**The actuator agent expects all messages to be JSON and will parse them
accordingly. Use publish\_json to send messages where possible. This is
significant for Boolean values especially.**

Actuator Reply
~~~~~~~~~~~~~~

#ActuatorReply The ActuatorAgent will reply to both **get** and *set*'
on the **value** topic for an actuator:

::

    #python
    'devices/actuators/value/<full device path>/<actuation point>'

With this header:

::

    #python
    {
        'requesterID': <Agent VIP identity>
    }

With the message containing the value encoded in JSON.

Actuator Error Reply
~~~~~~~~~~~~~~~~~~~~

If something goes wrong the ActuatorAgent will reply to both **get** and
*set*' on the **error** topic for an actuator:

::

    #python
    'devices/actuators/error/<full device path>/<actuation point>'

With this header:

::

    #python
    {
        'requesterID': <Agent VIP identity>
    }

The message will be in the following form:

::

    #python
    {
        'type': <Error Type or name of the exception raised by the request>
        'value': <Specific info about the error>
    }

Common Error Types
^^^^^^^^^^^^^^^^^^

| ``LockError:: Returned when a request is made when we do not have permission to use a device. (Forgot to schedule, preempted and we did not handle the preemption message correctly, ran out of time in time slot, etc...)``
| ``ValueError:: Message missing or could not be parsed as JSON.``

Other error types involve problem with communication between the
ActuatorAgent and sMap.
