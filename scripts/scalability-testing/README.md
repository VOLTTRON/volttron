# Message Bus Benchmarking

Benchmarks the message bus is generally performed with the following configuration:

    python config_builder.py --count=1500 --publish-only-depth-all --scalability-test fake fake18.csv null

This will create configuration files in configs/ directory to produce fake data from 1500 devices with 18 points each.

To use put the configurations into the configuration store run the following command. **NOTE: the volttron platform must be running at this point**

````
python ../install_platform_driver_configs.py configs
````

To start the test launch the Platform Driver Agent. A shortcut is to launch the Platform Driver is found in the scripts directory

````
cd ..
./launch_drivers.sh
````    

This will launch the platform driver using the configurations created earlier. The PlatformDriver will publish 5 sets of 1500 device "all" publishes and time the results. After 5 publishes have finished the platform driver will print the average time and quit.

To change the number of points on each device to 6 rerun config_builder.py and change "fake18.csv" to "fake6.csv". To change the number of devices change the value passed to the --count argument.

To test generally how well a Historian will perform on the platform start the fake historian in another terminal with the command:

    ./launch_fake_historian.sh

Start the scalability drivers again and note the change in results. It should also be noted that fake historian does not have a good way to measure it's performance yet. By watching the historian log one should note approximately how long it takes to "catch up" after the platform driver has finished each publish.

To have the drivers publish all points individually as well the breadth first remove "--publish-only-depth-all" when you run config_builder.py.

By default the interval for publishing is every 60 seconds. This can be changed with the "--interval" setting. This will only affect how often a the drivers will attempt to publish and will not affect benchmarks results unless the interval is shorter than the total time to publish or the the total time for the historian to catch up.
