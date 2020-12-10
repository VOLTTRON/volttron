#Message Bus Benchmarking

This python script can be used to check the performance of PubSub communication for either ZMQ/RMQ message bus.
It spins up multiple agents with each agent running as separate process and each listening on 'devices' topic.
So it needs to run along with platform driver with different scalability test confguration.

Steps:

1. Activate VOLTTRON environment and start VOLTTRON platform. Allow authentication to all incoming connections
    ```sh
    source env/bin/activate
    ./start-volttron
    vctl auth add
    domain []:
    address []:
    user_id []:
    capabilities (delimit multiple entries with comma) []:
    roles (delimit multiple entries with comma) []:
    groups (delimit multiple entries with comma) []:
    mechanism [CURVE]:
    credentials []: /.*/
    comments []:
    enabled [True]:
    ```

2. Build fake device configuration for the platform driver.
    ```sh
    cd scripts/scalability-testing/
    python config_builder.py --count=1500 --publish-only-depth-all --scalability-test fake fake18.csv null
    ```
This will create configuration files in configs/ directory to produce fake data from 1500 devices with 18 points each.

3. Set "driver_scrape_interval" parameter in configs/config to '0.0' so that platform driver scrapes all the devices together with zero staggered scrape interval.

{
    "scalability_test_iterations": 5,
    "publish_breadth_first_all": false,
    "publish_depth_first": false,
    "driver_scrape_interval": 0.02,
    "publish_breadth_first": false,
    "scalability_test": true
}

4. Put the configurations into the configuration store with the following command.

    ```sh
    python ../install_platform_driver_configs.py configs
    ```

5. In a new terminal, activate the VOLTTRON environment and run the multi-listener script.

    ```sh
    source env/bin/activate
    cd scripts/scalability-testing/multilistener
    python multi_listener_agent.py -l 10 -d 1500 -m zmq -f test.log
    ```
    This starts 10 listeners, each listening for 1500 device topics. By default, agents use 'zmq' message bus. But you
    can the message bus by changing message bus option to '-m rmq'.

5. To start the test launch the Platform Driver Agent. A shortcut is to launch the Platform Driver is found in the scripts directory

    ```sh
    cd ..
    ./launch_drivers.sh
    ```

This will launch the platform driver using the configurations created earlier. The MasterDriver will publish 5 sets of 1500 device "all" publishes and time the results. After 5 publishes have finished the platform driver will print the average time and quit. After 5 set of publishes, 'multi_listener_agent.py' script will also finish execution. It finally prints the mean time taken to receive each set of publishes.
By default, the platform driver runs on 'zmq' message bus. You can change the default setting, adding below environment
flag inside 'launch_drivers.sh' script.

    ```sh
    export MESSAGEBUS=rmq
    ```

## Looking at raw timing output

### The multi-listener script with raw data output

The `raw_output_multi_listener_agent.py` script is a modified version of the `multi_listener_agent.py` script, which will record the header and client times for each message received and save them in json format for more detailed processing.
This is particularly useful if you may be interested in decoupling any statistical analyses of the timing results from the process of configuring and running the agents to collect the data (for example, if you're interested in exploring multiple or less defined analyses, or if collecting data in many configurations where the time cost of re-running the collection is significant).
Some important notes about this script:
- The raw output file will either end with `.raw` (if the provided output file name has no extension), or will insert `.raw` prior to the extension (if one is present); the output file from the normal output script is not impacted.
- The raw output file must not already exist (this is checked before starting the agents).
  This is different from the overwrite behavior of the base script (and still present for the non-raw output file).

### Processing the data

An additional script (`process_file.py`) is included for parsing the raw output files and computing the average total time per scrape (that is, the difference between the source time of the first message in a set of scrape messages and the client time of the last message, averaged over all listeners and over the 5 sequential scrapes used in the test).
This script could be modified or expanded to look at other statistical metrics (possibly fitting to look for other trends, or computing other statistical moments for example).

## Other notes and tips

If running a large number of different configurations, working with the configuration store in the normal/supported way is quite slow (each interaction requires client/server interactions and were casually observed to take about a second).
An alternate way is to directly modify the configuration store's json file directly by:
1. stop the platform
2. modify the `VOLTTRON_HOME/configuration_store/<agent.identity>.store` file
3. restart the platform

For step 2, an extended bash command can be used unless the number of interactions was quite large.
This isn't the most efficient, but was very quick to write/modify as needed; a par of examples follow.
*Note:* to run the following commands you need to install two CLI tools: `jq` and `sponge`.
On debian, you can do that with `sudo apt-get install jq moreutils`.
For adding new devices:
```sh
for i in {1..99}; do
  echo "adding device [$i] at $(date)";
  jq --arg dname "devices/fake$i" '. + {($dname): .["devices/fake0"]}' $VOLTTRON_HOME/configuration_store/<agent.identity>.store | sponge $VOLTTRON_HOME/configuration_store/<agent.identity>.store;
done
```
(where the line breaks are optional, the update is done directly to the store file, and the `jq` and `sponge` tools were previously installed).
You can replace the json wrangling part of the jq command with the following to instead delete entries
```sh
jq --arg dname "devices/fake$i" 'del(.[$dname])'
```

Once the configuration store is configured to your needs, you run `raw_output_multi_listener_agent.py` in the same way as `multi_listener_agent.py` above.
You can run it with `--help` to see a description of the arguments, or as an example, for the case where you're interested in a single listener and have 10 devices installed in the platform driver, you could run the following (with your volttron virtual environment for a ZMQ platform activated):
```sh
python raw_output_multi_listener_agent.py -l 1 -d 10 -f `pwd`/1listener_10device_zmq.out -m zmq
```
which would produce two files in the current directory, `1listener_10device_zmq.out` and `1listener_10device_zmq.raw.out`.

You could then process the raw output file to have it compute the mean of the total time of the device scrapes by running:
```sh
./process_file.py -i 1listener_10device_zmq.raw.out
```
The results are printed to STDOUT.
