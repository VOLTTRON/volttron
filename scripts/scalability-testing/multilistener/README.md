#Message Bus Benchmarking

This python script can be used to check the performance of PubSub communication for either ZMQ/RMQ message bus. It spins up multiple agents with each agent running as separate process and each listening on 'devices' topic. So 
it needs to run along with master driver with different scalability test confguration.
 
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
2. Build fake device configuration for the master driver. 
    ```sh
    cd scripts/scalability-testing/
    python config_builder.py --count=1500 --publish-only-depth-all --scalability-test fake fake18.csv null
    ```
This will create configuration files in configs/ directory to produce fake data from 1500 devices with 18 points each.

3. Set "driver_scrape_interval" parameter in configs/config to '0.0' so that master driver scrapes all the devices together with zero staggered scrape interval.

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
    python ../install_master_driver_configs.py configs
    ```
    
5. In a new terminal, activate the VOLTTRON environment and run the multi-listener script.
    
    ```sh
    source env/bin/activate
    cd scripts/scalability-testing/multilistener
    python multi_listener_agent.py -l 10 -d 1500 -m zmq -f test.log
    ```
    This starts 10 listeners, each listening for 1500 device topics. By default, agents use 'zmq' message bus. But you
    can the message bus by changing message bus option to '-m rmq'.
      
5. To start the test launch the Master Driver Agent. A shortcut is to launch the Master Driver is found in the scripts directory

    ```sh
    cd ..
    ./launch_drivers.sh
    ```

This will launch the master driver using the configurations created earlier. The MasterDriver will publish 5 sets of 1500 device "all" publishes and time the results. After 5 publishes have finished the master driver will print the average time and quit. After 5 set of publishes, 'multi_listener_agent.py' script will also finish execution. It finally prints the mean time taken to receive each set of publishes.
By default, the master driver runs on 'zmq' message bus. You can change the default setting, adding below environment
flag inside 'launch_drivers.sh' script.

    ```sh
    export MESSAGEBUS=rmq
    ```