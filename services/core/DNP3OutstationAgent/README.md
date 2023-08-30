# DNP3 Outstation Agent

Distributed Network Protocol (DNP or DNP3) has achieved a large-scale acceptance since its introduction in 1993. This
protocol is an immediately deployable solution for monitoring remote sites because it was developed for communication of
critical infrastructure status, allowing for reliable remote control.

GE-Harris Canada (formerly Westronic, Inc.) is generally credited with the seminal work on the protocol. This protocol
is, however, currently implemented by an extensive range of manufacturers in a variety of industrial applications, such
as electric utilities.

DNP3 is composed of three layers of the OSI seven-layer functions model. These layers are application layer, data link
layer, and transport layer. Also, DNP3 can be transmitted over a serial bus connection or over a TCP/IP network.

# Prerequisites

* Python 3.8 + 

# Installation

1. Install volttron and start the platform.

   Refer to the [VOLTTRON Quick Start](https://volttron.readthedocs.io/en/main/tutorials/quick-start.html) to install
   the VOLTTRON platform.

    ```shell
    ...
    # Activate the virtual enviornment
    $ source env/bin/activate
    
    # Start the platform
    (volttron) $ ./start-volttron
    
    # Check (installed) agent status
    (volttron) $ vctl status
    UUID AGENT                            IDENTITY              TAG                   STATUS          HEALTH
    75 listeneragent-3.3                listeneragent-3.3_1   listener                             
    2f platform_driveragent-4.0         platform.driver       platform_driver
    ```

1. (If not satisfied yet,) install [dnp3-python](https://pypi.org/project/dnp3-python/) dependency.

    ```shell
    (volttron) $ pip install dnp3-python==0.2.3b3
    ```

1. Install and start the DNP3 Outstation Agent.

   Install the DNP3 Outstation agent with the following command:

    ```shell
    (volttron) $ vctl install <path-to-agent-wheel-or-directory-for-agent-installation> \
    --agent-config <path-to-config-file> \
    --tag  <dnp3-agent-tag> \
    --vip-identity <dnp3-agent-identity> \
    -f \
    --start
    ```

   Assuming at the package root path, installing a dnp3-agent with [example-config.json](example-config.json), called "
   dnp3-outstation-agent".

    ```shell
    (volttron) $ vctl install ./services/core/DNP3OutstationAgent/ \
    --agent-config services/core/DNP3OutstationAgent/example-config.json \
    --tag dnp3-outstation-agent \
    --vip-identity dnp3-outstation-agent \
    -f \
    --start
   
    # >>
    Agent 2e37a3bc-4438-4d52-8e05-cb6703cf3760 installed and started [11074]
    ```

   Please see more details about agent installation with `vctl install -h`.

1. View the status of the installed agent (and notice a new dnp3 outstation agent is installed and running.)

    ```shell
    (volttron) $ vctl status
    UUID AGENT                            IDENTITY              TAG                   STATUS          HEALTH
    2e dnp3_outstation_agentagent-0.2.0 dnp3-outstation-agent dnp3-outstation-agent running [11074] GOOD
    75 listeneragent-3.3                listeneragent-3.3_1   listener                             
    2f platform_driveragent-4.0         platform.driver       platform_driver
    ```

1. Verification

   The dnp3 outstation agent acts as a server, and we will demonstrate a typical use case in the "Demonstration"
   session.

# Agent Configuration

The required parameters for this agent are "outstation_ip", "port", "master_id", and "outstation_id".
Below is an example configuration can be found at [example-config.json](example-config.json).

```
    {
    'outstation_ip': '0.0.0.0',
    'port': 20000,
    'master_id': 2,
    'outstation_id': 1
    }
```

Note: as part of the Volttron configuration framework, this file will be added to
the `$VOLTTRON_HOME/agents/<agent-uuid>/<agent-name>/<agent-name.dist-info>/` as `config`,
e.g. `~/.volttron/agents/94e54843-4bd4-45d7-9a92-3d18588b5682/dnp3_outstation_agentagent-0.2.0/dnp3_outstation_agentagent-0.2.0.dist-info/config`

# Demonstration

If you don't have a dedicated DNP3 Master to test the DNP3 outstation agent against, you can setup a local DNP3 Master
instead. This DNP3 Master will
be hosted at localhost on a specific port (port 20000 by default, i.e. 127.0.0.1:20000).
This Master will communicate with the DNP3 outstation agent.

To setup a local master, we can utilize the dnp3demo module from the dnp3-python dependency. For more information about
the dnp3demo module, please refer
to [dnp3demo-Module.md](https://github.com/VOLTTRON/dnp3-python/blob/develop/docs/dnp3demo-Module.md)

## Setup DNP3 Master

1. Verify [dnp3-python](https://pypi.org/project/dnp3-python/) is installed properly:

    ```shell
    (volttron)  $ pip list | grep dnp3
    dnp3-python          0.2.3b2   
   
    (volttron) $ dnp3demo
    ms(1676667858612) INFO    manager - Starting thread (0)
    ms(1676667858612) WARN    server - Address already in use
    2023-02-17 15:04:18,612 dnp3demo.data_retrieval_demo    DEBUG   Initialization complete. OutStation in command loop.
    ms(1676667858613) INFO    manager - Starting thread (0)
    channel state change: OPENING
    ms(1676667858613) INFO    tcpclient - Connecting to: 127.0.0.1
    2023-02-17 15:04:18,613 dnp3demo.data_retrieval_demo    DEBUG   Initialization complete. Master Station in command loop.
    ms(1676667858613) INFO    tcpclient - Connected to: 127.0.0.1
    channel state change: OPEN
    2023-02-17 15:04:19.615457 ============count  1
    ====== Outstation update index 0 with 8.465443888876885
    ====== Outstation update index 1 with 17.77180643225464
    ====== Outstation update index 2 with 27.730343174887107
    ====== Outstation update index 0 with False
    ====== Outstation update index 1 with True
    
    ...
    
    2023-02-17 15:04:22,839 dnp3demo.data_retrieval_demo    DEBUG   Exiting.
    channel state change: CLOSED
    channel state change: SHUTDOWN
    ms(1676667864841) INFO    manager - Exiting thread (0)
    ms(1676667870850) INFO    manager - Exiting thread (0)
    ```

1. Run a DNP3 Master at local (with the default parameters)

   Assuming the DNP3 outstation agent is running, run the following commands and expect the similar output.
    ```shell
    (volttron) $ dnp3demo master
    dnp3demo.run_master {'command': 'master', 'master_ip': '0.0.0.0', 'outstation_ip': '127.0.0.1', 'port': 20000, 'master_id': 2, 'outstation_id': 1}
    ms(1676668214630) INFO    manager - Starting thread (0)
    2023-02-17 15:10:14,630 control_workflow_demo   INFO    Communication Config
    2023-02-17 15:10:14,630 control_workflow_demo   INFO    Communication Config
    2023-02-17 15:10:14,630 control_workflow_demo   INFO    Communication Config
    channel state change: OPENING
    ms(1676668214630) INFO    tcpclient - Connecting to: 127.0.0.1
    ms(1676668214630) INFO    tcpclient - Connected to: 127.0.0.1
    channel state change: OPEN
    2023-02-17 15:10:14,630 control_workflow_demo   DEBUG   Initialization complete. Master Station in command loop.
    2023-02-17 15:10:14,630 control_workflow_demo   DEBUG   Initialization complete. Master Station in command loop.
    2023-02-17 15:10:14,630 control_workflow_demo   DEBUG   Initialization complete. Master Station in command loop.
    ==== Master Operation MENU ==================================
    <ao> - set analog-output point value (for remote control)
    <bo> - set binary-output point value (for remote control)
    <dd> - display/polling (outstation) database
    <dc> - display configuration
    =================================================================
    
    ======== Your Input Here: ==(master)======
    
    ```

   Note: if the dnp3 agent is not running, you might observe the following output instead
    ```
    Start retry...
    Communication error.
    Communication Config {'masterstation_ip_str': '0.0.0.0', 'outstation_ip_str': '127.0.0.1', 'port': 20000, 'masterstation_id_int': 2, 'outstation_id_int': 1}
    ...
    ```

   This Master station runs at port 20000 by default. Please see `dnp3demo master -h` for configuration options.
   Note: If using customized master parameter, please make sure the DNP3 Outstation Agent is configured accordingly.
   Please refer to [DNP3-Primer.md](https://github.com/VOLTTRON/dnp3-python/blob/develop/docs/DNP3-Primer.md) for DNP3
   protocol fundamentals including connection settings.

## Basic operation demo

The dnp3demo master submodule is an interactive CLI tool to communicate with an outstation. The available options are
shown in the "Master Operation MENU" and should be self-explanatory. Here we can demonstrate <dd> and <ao> commands.

1. <dd> - display/polling (outstation) database

    ```shell
    ======== Your Input Here: ==(master)======
    dd
    You chose < dd > - display database
    {'Analog': {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}, 'AnalogOutputStatus': {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}, 'Binary': {0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: False, 7: False, 8: False, 9: False}, 'BinaryOutputStatus': {0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: False, 7: False, 8: False, 9: False}}
    ==== Master Operation MENU ==================================
    <ao> - set analog-output point value (for remote control)
    <bo> - set binary-output point value (for remote control)
    <dd> - display/polling (outstation) database
    <dc> - display configuration
    =================================================================

    ```

   Note that an outstation is initialed with "0.0" for Analog-type points, and "False" for Binary-type points, hence the
   output displayed above.

1. <ao> - set analog-output point value (for remote control)

    ```shell
    ======== Your Input Here: ==(master)======
    ao
    You chose <ao> - set analog-output point value
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    ======== Your Input Here: ==(master)======
    0.1233 0
    SUCCESS {'AnalogOutputStatus': {0: 0.1233, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}}
    You chose <ao> - set analog-output point value
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    ======== Your Input Here: ==(master)======
    1.3223 1
    SUCCESS {'AnalogOutputStatus': {0: 0.1233, 1: 1.3223, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}}
    You chose <ao> - set analog-output point value
    Type in <float> and <index>. Separate with space, then hit ENTER.
    Type 'q', 'quit', 'exit' to main menu.
    
    ======== Your Input Here: ==(master)======
    q
    ==== Master Operation MENU ==================================
    <ao> - set analog-output point value (for remote control)
    <bo> - set binary-output point value (for remote control)
    <dd> - display/polling (outstation) database
    <dc> - display configuration
    =================================================================
    
    ======== Your Input Here: ==(master)======
    dd
    You chose < dd > - display database
    {'Analog': {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}, 'AnalogOutputStatus': {0: 0.1233, 1: 1.3223, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0, 9: 0.0}, 'Binary': {0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: False, 7: False, 8: False, 9: False}, 'BinaryOutputStatus': {0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: False, 7: False, 8: False, 9: False}}

    ```

   Explain of the operation and expected output
    * We type "ao" (stands for "analog output") to enter the set point dialog.
    * We set AnalogOut index0==0.1233, (the prompt indicates the operation is successful.)
    * Then, we set AnalogOut index1==1.3223, (again, the prompt indicates the operation is successful.)
    * We type "q" (stands for "quit") to exit the set point dialog.
    * We use "dd" command and verified that AnalogOutput values are consistent to what we set ealier.

1. Bonus script for running DNP3 outstation agent interactively

   Similar to the interactive dnp3demo master submodule, we can run the dnp3 outstation agent interactively from the
   command line using [run_dnp3_outstation_agent_script.py](demo-scripts/run_dnp3_outstation_agent_script.py).

    ```shell
    (volttron) $ python services/core/DNP3OutstationAgent/demo-scripts/run_dnp3_outstation_agent_script.py 
    ...
    2023-02-17 15:58:04,123 volttron.platform.vip.agent.core INFO: Connected to platform: router: a2ae7a58-6ce7-4386-b5eb-71e386075c15 version: 1.0 identity: e91d54f6-d4ff-4fe5-afcb-cf8f360e84af
    2023-02-17 15:58:04,123 volttron.platform.vip.agent.core DEBUG: Running onstart methods.
    2023-02-17 15:58:07,137 volttron.platform.vip.agent.subsystems.auth WARNING: Auth entry not found for e91d54f6-d4ff-4fe5-afcb-cf8f360e84af: rpc_method_authorizations not updated. If this agent does have an auth entry, verify that the 'identity' field has been included in the auth entry. This should be set to the identity of the agent
    ========================= MENU ==================================
    <ai> - set analog-input point value
    <ao> - set analog-output point value
    <bi> - set binary-input point value
    <bo> - set binary-output point value
    
    <dd> - display database
    <di> - display (outstation) info
    <cr> - config then restart outstation

    ```

   dd command
    ```shell
    ======== Your Input Here: ==(DNP3 OutStation Agent)======
    dd
    You chose <dd> - display database
    {'Analog': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None, '8': None, '9': None}, 'AnalogOutputStatus': {'0': 0.1233, '1': 1.3223, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None, '8': None, '9': None}, 'Binary': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None, '8': None, '9': None}, 'BinaryOutputStatus': {'0': None, '1': None, '2': None, '3': None, '4': None, '5': None, '6': None, '7': None, '8': None, '9': None}}

   ```

   Note: [run_dnp3_outstation_agent_script.py](demo-scripts/run_dnp3_outstation_agent_script.py) script is a wrapper on
   the dnp3demo outstation submodle. For details about the interactive dnp3 station operations, please refer
   to [dnp3demo-Module.md](https://github.com/VOLTTRON/dnp3-python/blob/develop/docs/dnp3demo-Module.md)

# Run Tests

1. Install volttron testing dependencies
    ```shell
    (volttron) $ python bootstrap.py --testing
    UPDATE: ['testing']
    Installing required packages
    + pip install --upgrade --no-deps wheel==0.30
    Requirement already satisfied: wheel==0.30 in ./env/lib/python3.10/site-packages (0.30.0)
    + pip install --upgrade --install-option --zmq=bundled --no-deps pyzmq==22.2.1
    WARNING: Disabling all use of wheels due to the use of --build-option / --global-option / --install-option.
    ...
    ```

1. Run pytest
    ```shell
    (volttron) $ pytest services/core/DNP3OutstationAgent/tests/.
    ===================================================================================================== test session starts =====================================================================================================
    platform linux -- Python 3.10.6, pytest-7.1.2, pluggy-1.0.0 -- /home/kefei/project/volttron/env/bin/python
    cachedir: .pytest_cache
    rootdir: /home/kefei/project/volttron, configfile: pytest.ini
    plugins: rerunfailures-10.2, asyncio-0.19.0, timeout-2.1.0
    asyncio: mode=auto
    timeout: 300.0s
    timeout method: signal
    timeout func_only: False
    collected 40 items                                                
    ```
