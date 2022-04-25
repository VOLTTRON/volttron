# OpenADRVenAgent

OpenADR (Automated Demand Response) is a standard for alerting and responding to the need to adjust electric power 
consumption in response to fluctuations in grid demand. 

For further information about OpenADR and this agent, please see the OpenADR documentation in VOLTTRON ReadTheDocs.

## Dependencies
The VEN agent depends on some third-party libraries that are not in the standard VOLTTRON installation. 
They should be installed in the VOLTTRON virtual environment prior to building the agent. Use requirements.txt in the 
agent directory to install the requirements

```
cd $VOLTTRON_ROOT/services/core/OpenADRVenAgent
pip install -r requirements.txt
```

## Configuration Parameters

The VEN agent’s configuration file contains JSON that includes several parameters for configuring VTN server communications and other behavior. A sample configuration file, config, has been provided in the agent directory.

The VEN agent supports the following configuration parameters:

|Parameter|Example|Description|
|---------|-------|-----------|
|db\_path|“\$VOLTTRON\_HOME/data/|Pathname of the agent's sqlite database. Shell|
||openadr.sqlite”|variables will be expanded if they are present|
|||in the pathname.|
|ven\_id|“0”|The OpenADR ID of this virtual end node. Identifies|
|||this VEN to the VTN. If automated VEN registration|
|||is used, the ID is assigned by the VTN at that|
|||time. If the VEN is registered manually with the|
|||VTN (i.e., via configuration file settings), then|
|||a common VEN ID should be entered in this config|
|||file and in the VTN's site definition.|
|ven\_name|"ven01"|Name of this virtual end node. This name is used|
|||during automated registration only, identiying|
|||the VEN before its VEN ID is known.|
|vtn\_id|“vtn01”|OpenADR ID of the VTN with which this VEN|
|||communicates.|
|vtn\_address|“<http://openadr-vtn>.|URL and port number of the VTN.|
||ki-evi.com:8000”||
|send\_registration|“False”|(“True” or ”False”) If “True”, the VEN sends|
|||a one-time automated registration request to|
|||the VTN to obtain the VEN ID. If automated|
|||registration will be used, the VEN should be run|
|||in this mode initially, then shut down and run|
|||with this parameter set to “False” thereafter.|
|security\_level|“standard”|If 'high', the VTN and VEN use a third-party|
|||signing authority to sign and authenticate each|
|||request. The default setting is “standard”: the|
|||XML payloads do not contain Signature elements.|
|poll\_interval\_secs|30|(integer) How often the VEN should send an OadrPoll|
|||request to the VTN. The poll interval cannot be|
|||more frequent than the VEN’s 5-second process|
|||loop frequency.|
|log\_xml|“False”|(“True” or “False”) Whether to write each|
|||inbound/outbound request’s XML data to the|
|||agent's log.|
|opt\_in\_timeout\_secs|1800|(integer) How long to wait before making a|
|||default optIn/optOut decision.|
|opt\_in\_default\_decision|“optOut”|(“True” or “False”) Which optIn/optOut choice|
|||to make by default.|
|request\_events\_on\_startup|"False"|("True" or "False") Whether to ask the VTN for a|
|||list of current events during VEN startup.|
|report\_parameters|(see below)|A dictionary of definitions of reporting/telemetry|
|||parameters.|

Reporting Configuration
=======================

The VEN’s reporting configuration, specified as a dictionary in the agent configuration, defines each telemetry element (metric) that the VEN can report to the VTN, if requested. By default, it defines reports named “telemetry” and "telemetry\_status", with a report configuration dictionary containing the following parameters:

|"telemetry" report: parameters|Example|Description|
|------------------------------|-------|-----------|
|report\_name|"TELEMETRY\_USAGE"|Friendly name of the report.|
|report\_name\_metadata|"METADATA\_TELEMETRY\_USAGE"|Friendly name of the report’s metadata, when sent|
|||by the VEN’s oadrRegisterReport request.|
|report\_specifier\_id|"telemetry"|Uniquely identifies the report’s data set.|
|report\_interval\_secs\_default|"300"|How often to send a reporting update to the VTN.|
|telemetry\_parameters (baseline\_power\_kw): r\_id|"baseline\_power"|(baseline\_power) Unique ID of the metric.|
|telemetry\_parameters (baseline\_power\_kw): report\_type|"baseline"|(baseline\_power) The type of metric being reported.|
|telemetry\_parameters (baseline\_power\_kw): reading\_type|"Direct Read"|(baseline\_power) How the metric was calculated.|
|telemetry\_parameters (baseline\_power\_kw): units|"powerReal"|(baseline\_power) The reading's data type.|
|telemetry\_parameters (baseline\_power\_kw): method\_name|"get\_baseline\_power"|(baseline\_power) The VEN method to use when|
|||extracting the data for reporting.|
|telemetry\_parameters (baseline\_power\_kw): min\_frequency|30|(baseline\_power) The metric’s minimum sampling|
|||frequency.|
|telemetry\_parameters (baseline\_power\_kw): max\_frequency|60|(baseline\_power) The metric’s maximum sampling|
|||frequency.|
|telemetry\_parameters (current\_power\_kw): r\_id|"actual\_power"|(current\_power) Unique ID of the metric.|
|telemetry\_parameters (current\_power\_kw): report\_type|"reading"|(current\_power) The type of metric being reported.|
|telemetry\_parameters (current\_power\_kw): reading\_type|"Direct Read"|(current\_power) How the metric was calculated.|
|telemetry\_parameters (current\_power\_kw): units|"powerReal"|(baseline\_power) The reading's data type.|
|telemetry\_parameters (current\_power\_kw): method\_name|"get\_current\_power"|(current\_power) The VEN method to use when|
|||extracting the data for reporting.|
|telemetry\_parameters (current\_power\_kw): min\_frequency|30|(current\_power) The metric’s minimum sampling|
|||frequency.|
|telemetry\_parameters (current\_power\_kw): max\_frequency|60|(current\_power) The metric’s maximum sampling|
|||frequency.|

|"telemetry\_status" report: parameters|Example|Description|
|--------------------------------------|-------|-----------|
|report\_name|"TELEMETRY\_STATUS"|Friendly name of the report.|
|report\_name\_metadata|"METADATA\_TELEMETRY\_STATUS"|Friendly name of the report’s metadata, when sent|
|||by the VEN’s oadrRegisterReport request.|
|report\_specifier\_id|"telemetry\_status"|Uniquely identifies the report’s data set.|
|report\_interval\_secs\_default|"300"|How often to send a reporting update to the VTN.|
|telemetry\_parameters (Status): r\_id|"Status"|Unique ID of the metric.|
|telemetry\_parameters (Status): report\_type|"x-resourceStatus"|The type of metric being reported.|
|telemetry\_parameters (Status): reading\_type|"x-notApplicable"|How the metric was calculated.|
|telemetry\_parameters (Status): units|""|The reading's data type.|
|telemetry\_parameters (Status): method\_name|""|The VEN method to use when extracting the data|
|||for reporting.|
|telemetry\_parameters (Status): min\_frequency|60|The metric’s minimum sampling frequency.|
|telemetry\_parameters (Status): max\_frequency|120|The metric’s maximum sampling frequency.|




