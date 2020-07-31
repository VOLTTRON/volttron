.. _VenAgentConfig:

OpenADR VEN Agent: Installation and Configuration
=================================================

The VEN agent can be configured, built and launched using the VOLTTRON agent installation
process described in
http://volttron.readthedocs.io/en/develop/devguides/agent_development/Agent-Development.html#agent-development.

The VEN agent depends on some third-party libraries that are not in the standard
VOLTTRON installation. They should be installed in the VOLTTRON virtual environment prior to building the agent:
::

    (volttron) $ cd $VOLTTRON_ROOT/services/core/OpenADRVenAgent
    (volttron) $ pip install -r requirements.txt

where **$VOLTTRON_ROOT** is the base directory of the cloned VOLTTRON code repository.

The VEN agent is designed to work in tandem with a “control agent,” another
VOLTTRON agent that uses VOLTTRON RPC calls to manage events and supply report data.
A sample control agent has been provided in the **test/ControlAgentSim** subdirectory
under OpenADRVenAgent.

The VEN agent maintains a persistent store of event and report data in
**$VOLTTRON_HOME/data/openadr.sqlite**. Some care should be taken in managing the
disk consumption of this data store. If no events or reports are active,
it is safe to take down the VEN agent and delete the file; the persistent
store will be reinitialized automatically on agent startup.

Configuration Parameters
------------------------

The VEN agent’s configuration file contains JSON that includes several parameters
for configuring VTN server communications and other behavior. A sample configuration
file, **openadrven.config**, has been provided in the agent directory.

The VEN agent supports the following configuration parameters:

========================= ======================== ====================================================
Parameter                 Example                  Description
========================= ======================== ====================================================
db_path                   “$VOLTTRON_HOME/data/    Pathname of the agent's sqlite database. Shell
                          openadr.sqlite”          variables will be expanded if they are present
                                                   in the pathname.
ven_id                    “0”                      The OpenADR ID of this virtual end node. Identifies
                                                   this VEN to the VTN. If automated VEN registration
                                                   is used, the ID is assigned by the VTN at that
                                                   time. If the VEN is registered manually with the
                                                   VTN (i.e., via configuration file settings), then
                                                   a common VEN ID should be entered in this config
                                                   file and in the VTN's site definition.
ven_name                  "ven01"                  Name of this virtual end node. This name is used
                                                   during automated registration only, identiying
                                                   the VEN before its VEN ID is known.
vtn_id                    “vtn01”                  OpenADR ID of the VTN with which this VEN
                                                   communicates.
vtn_address               “http://openadr-vtn.     URL and port number of the VTN.
                          ki-evi.com:8000”
send_registration         “False”                  (“True” or ”False”) If “True”, the VEN sends
                                                   a one-time automated registration request to
                                                   the VTN to obtain the VEN ID. If automated
                                                   registration will be used, the VEN should be run
                                                   in this mode initially, then shut down and run
                                                   with this parameter set to “False” thereafter.
security_level            “standard”               If 'high', the VTN and VEN use a third-party
                                                   signing authority to sign and authenticate each
                                                   request. The default setting is “standard”: the
                                                   XML payloads do not contain Signature elements.
poll_interval_secs        30                       (integer) How often the VEN should send an OadrPoll
                                                   request to the VTN. The poll interval cannot be
                                                   more frequent than the VEN’s 5-second process
                                                   loop frequency.
log_xml                   “False”                  (“True” or “False”) Whether to write each
                                                   inbound/outbound request’s XML data to the
                                                   agent's log.
opt_in_timeout_secs       1800                     (integer) How long to wait before making a
                                                   default optIn/optOut decision.
opt_in_default_decision   “optOut”                 (“True” or “False”) Which optIn/optOut choice
                                                   to make by default.
request_events_on_startup "False"                  ("True" or "False") Whether to ask the VTN for a
                                                   list of current events during VEN startup.
report_parameters         (see below)              A dictionary of definitions of reporting/telemetry
                                                   parameters.
========================= ======================== ====================================================

Reporting Configuration
-----------------------

The VEN’s reporting configuration, specified as a dictionary in the agent configuration,
defines each telemetry element (metric) that the VEN can report to the VTN, if requested.
By default, it defines reports named “telemetry” and "telemetry_status", with a report
configuration dictionary containing the following parameters:

======================================================= =========================== ====================================================
"telemetry" report: parameters                          Example                     Description
======================================================= =========================== ====================================================
report_name                                             "TELEMETRY_USAGE"           Friendly name of the report.
report_name_metadata                                    "METADATA_TELEMETRY_USAGE"  Friendly name of the report’s metadata, when sent
                                                                                    by the VEN’s oadrRegisterReport request.
report_specifier_id                                     "telemetry"                 Uniquely identifies the report’s data set.
report_interval_secs_default                            "300"                       How often to send a reporting update to the VTN.
telemetry_parameters (baseline_power_kw): r_id          "baseline_power"            (baseline_power) Unique ID of the metric.
telemetry_parameters (baseline_power_kw): report_type   "baseline"                  (baseline_power) The type of metric being reported.
telemetry_parameters (baseline_power_kw): reading_type  "Direct Read"               (baseline_power) How the metric was calculated.
telemetry_parameters (baseline_power_kw): units         "powerReal"                 (baseline_power) The reading's data type.
telemetry_parameters (baseline_power_kw): method_name   "get_baseline_power"        (baseline_power) The VEN method to use when
                                                                                    extracting the data for reporting.
telemetry_parameters (baseline_power_kw): min_frequency 30                          (baseline_power) The metric’s minimum sampling
                                                                                    frequency.
telemetry_parameters (baseline_power_kw): max_frequency 60                          (baseline_power) The metric’s maximum sampling
                                                                                    frequency.
telemetry_parameters (current_power_kw): r_id           "actual_power"              (current_power) Unique ID of the metric.
telemetry_parameters (current_power_kw): report_type    "reading"                   (current_power) The type of metric being reported.
telemetry_parameters (current_power_kw): reading_type   "Direct Read"               (current_power) How the metric was calculated.
telemetry_parameters (current_power_kw): units          "powerReal"                 (baseline_power) The reading's data type.
telemetry_parameters (current_power_kw): method_name    "get_current_power"         (current_power) The VEN method to use when
                                                                                    extracting the data for reporting.
telemetry_parameters (current_power_kw): min_frequency  30                          (current_power) The metric’s minimum sampling
                                                                                    frequency.
telemetry_parameters (current_power_kw): max_frequency  60                          (current_power) The metric’s maximum sampling
                                                                                    frequency.
======================================================= =========================== ====================================================

======================================================= =========================== ====================================================
"telemetry_status" report: parameters                   Example                     Description
======================================================= =========================== ====================================================
report_name                                             "TELEMETRY_STATUS"          Friendly name of the report.
report_name_metadata                                    "METADATA_TELEMETRY_STATUS" Friendly name of the report’s metadata, when sent
                                                                                    by the VEN’s oadrRegisterReport request.
report_specifier_id                                     "telemetry_status"          Uniquely identifies the report’s data set.
report_interval_secs_default                            "300"                       How often to send a reporting update to the VTN.
telemetry_parameters (Status): r_id                     "Status"                    Unique ID of the metric.
telemetry_parameters (Status): report_type              "x-resourceStatus"          The type of metric being reported.
telemetry_parameters (Status): reading_type             "x-notApplicable"           How the metric was calculated.
telemetry_parameters (Status): units                    ""                          The reading's data type.
telemetry_parameters (Status): method_name              ""                          The VEN method to use when extracting the data
                                                                                    for reporting.
telemetry_parameters (Status): min_frequency            60                          The metric’s minimum sampling frequency.
telemetry_parameters (Status): max_frequency            120                         The metric’s maximum sampling frequency.
======================================================= =========================== ====================================================
