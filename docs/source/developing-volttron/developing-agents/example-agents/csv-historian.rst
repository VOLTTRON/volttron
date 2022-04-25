.. _CSV-Historian:

=============
CSV Historian
=============

The CSV Historian Agent is an example historian agent that writes device data to the CSV file specified in the
configuration file.


Explanation of CSV Historian
============================

The Utils module of the VOLTTRON platform includes functions for setting up global logging for the platform:

.. code-block:: python

    utils.setup_logging()
    _log = logging.getLogger(__name__)


The ``historian`` function is called by ``utils.vip_main`` when the agents is started (see below).  ``utils.vip_main``
expects a callable object that returns an instance of an Agent.  This method of dealing with a configuration file and
instantiating an Agent is common practice.

.. literalinclude:: ../../../../../examples/CSVHistorian/csv_historian/historian.py
   :pyobject: historian

All historians must inherit from `BaseHistorian`.  The `BaseHistorian` class handles the capturing and caching of all
device, logging, analysis, and record data published to the message bus.

.. code-block:: python

    class CSVHistorian(BaseHistorian):

The Base Historian creates a separate thread to handle publishing data to the data store.  In this thread the Base
Historian calls two methods on the created historian, ``historian_setup`` and ``publish_to_historian``.

The Base Historian created the new thread in it's ``__init__`` method. This means that any instance variables
must assigned in ``__init__`` before calling the Base Historian's ``__init__`` method.

.. literalinclude:: ../../../../../examples/CSVHistorian/csv_historian/historian.py
   :pyobject: CSVHistorian.__init__

Historian setup is called shortly after the new thread starts. This is where a Historian sets up a connect the first
time.  In our example we create the `Dictwriter` object that we will use to create and add lines to the CSV file.

We keep a reference to the file object so that we may flush its contents to disk after writing the header and after we
have written new data to the file.

The CSV file we create will have 4 columns: `timestamp`, `source`, `topic`, and `value`.

.. literalinclude:: ../../../../../examples/CSVHistorian/csv_historian/historian.py
   :pyobject: CSVHistorian.historian_setup

``publish_to_historian`` is called when data is ready to be published. It is passed a list of dictionaries.  Each
dictionary contains a record of a single value that was published to the message bus.

The dictionary takes the form:

.. code-block:: python

    {
        '_id': 1,
        'timestamp': timestamp1.replace(tzinfo=pytz.UTC), #Timestamp in UTC
        'source': 'scrape', #Source of the data point.
        'topic': "pnnl/isb1/hvac1/thermostat", #Topic that published to without prefix.
        'value': 73.0, #Value that was published
        'meta': {"units": "F", "tz": "UTC", "type": "float"} #Meta data published with the topic
    }

Once the data is written to the historian we call ``self.report_all_handled()`` to inform the `BaseHistorian` that all
data we received was successfully published and can be removed from the cache.  Then we can flush the file to ensure
that the data is written to disk.

.. literalinclude:: ../../../../../examples/CSVHistorian/csv_historian/historian.py
   :pyobject: CSVHistorian.publish_to_historian

This agent does not support the Historian Query interface.


Agent Testing
-------------

The CSV Historian can be tested by running the included `launch_my_historian.sh` script.


Agent Installation
------------------

This Agent may be installed on the platform using the :ref:`standard method <installing-and-running-agents>`.

