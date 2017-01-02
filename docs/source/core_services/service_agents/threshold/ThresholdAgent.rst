.. _ThresholdAgent:

Threshold Detection Agent
=========================

The ThresholdDetectionAgent will publish an alert when a value published to a
topic exceeds or falls below a configured value. The agent can be configured to
watch topics are associated with a single value or to watch devices' all topics.

Configuration
-------------

The ThresholdDetectionAgent supports the :ref:`configstore <VOLTTRON-Configuration-Store>`
and can be configured with a file named "config".

The file must be in the following format:

- Topics and points in device publishes may have maximum and minimum thresholds but both are not required

- A device's point entries are configured the same way as standard topic entries

.. code-block:: python

   {
       "topic": {
           "threshold_max": 10
       },

       "devices/some/device/all": {
           "point0": {
               "threshold_max": 10,
               "threshold_min": 0
           },
           "point1": {
               "threshold_max": 42
           }
       }
   }
