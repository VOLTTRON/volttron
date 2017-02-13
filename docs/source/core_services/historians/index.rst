.. _Historian Index:
============================
VOLTTRON Historian Framework
============================

Historian Agents are the way by which device, actuator, datalogger, and
analysis are captured and stored in some sort of data store. Historians exist for the following storage options:

- A general :ref:`SQL Historian <SQL-Historian>` implemented for MySQL and SQLite
- :ref:`MongoDB Historian <Mongo-Historian>`
- :ref:`Crate Historian <Crate-Historian>`
- :ref:`Forward-Historian>` for sending data to another VOLTTRON instance
- :ref:`OpenEIS Historian <Analytics-Historian>`

Other implementations of historians can be created by following the
:ref:`developing historian agents <Developing-Historian-Agents>` section of
the wiki.

Historians are all built upon the BaseHistorian which provides general
functionality the specific implementations build upon.

| By default the base historian will listen to 4 separate root topics
(datalogger/*, record/*, actuators/\ *, and device/*. Each of root
topics has a :ref:`specific message syntax <Historian-Topic-Syntax>` that
it is expecting
| for incoming data. Messages that are published to actuator are assumed
to be part of the actuation process. Messages published to datalogger
will be assumed to be timepoint data that is composed of units and
specific types with the assumption that they have the ability to be
graphed easily. Messages published to devices are data that comes
directly from drivers. Finally Messages that are published to record
will be handled as string data and can be customized to the user
specific situation. Please consult the :ref:`Historian Topic
Syntax <Historian-Topic-Syntax>` page for a specific syntax.

| This base historian will cache all received messages to a local
database
| before publishing it to the historian. This allows recovery for
unexpected
| happenings before the successful writing of data to the historian.


.. toctree::
    :glob:
    :maxdepth: 2

    *
