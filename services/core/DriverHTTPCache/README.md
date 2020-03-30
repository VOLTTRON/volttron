Driver HTTP Cache Agent
=======================

The Driver HTTP Cache agent is a simple agent designed to fetch data from remote APIs and cache it for a duration 
specified by the API. It requires no configuration to operate. JSON RPC calls exist for drivers to use to obtain data 
from remote web APIs via HTTP requests. Request results are then cached by the agent. The RPC calls include an update
frequency parameter which is used to specify the data update interval of the remote API end point. If a new RPC call 
is made between the timestamp of the previous request and that timestamp plus the update interval, cached data will be
returned. If an RPC call is made after the update interval has passed, then a new request HTTP request will be sent to
the remote API.

Example GET request RPC call:

    def driver_data_get(self, driver_type, group_id, url, headers,  params=None, body=None, 
                        update_frequency=60, refresh=False):
        
        """
        Get the most up to date remote API driver data based on provided update 
        frequency using HTTP GET request
        :param group_id: arbitrary identifier to separate driver data between 
        collections of devices
        :param driver_type: String representation of the type of driver
        :param url: String url for communicating with remote API
        :param update_frequency: Frequency in seconds between remote API data 
        updates, defaults to 60
        :param headers: HTTP request headers dictionary for remote API specified by 
        driver
        :param params: HTTP request parameters dictionary for remote API specified 
        by driver
        :param body: HTTP request body dictionary for remote API specified by driver
        :param refresh: If true, the Driver HTTP Cache agent will skip retrieving 
        cached data
        :return: Remote API response data dictionary to be parsed by driver`
        """
        
Example POST request RPC call:

    def driver_data_post(self, driver_type, group_id, url, headers,  data=None, json=None, 
                         update_frequency=60, refresh=False):

        """
        Get the most up to date remote API driver data based on provided update 
        frequency using HTTP POST request
        :param group_id: arbitrary identifier to separate driver data between 
        collections of devices
        :param driver_type: String representation of the type of driver
        :param url: String url for communicating with remote API
        :param update_frequency: Frequency in seconds between remote API data 
        updates, defaults to 60
        :param headers: HTTP request headers dictionary for remote API specified by 
        driver
        :param data: HTTP request parameters dictionary for remote API specified 
        by driver
        :param json: HTTP request body dictionary for remote API specified by driver
        :param refresh: If true, Driver HTTP Cache agent will skip retrieving cached 
        data
        :return: Remote API response data dictionary to be parsed by driver`
        """
        
Usage example from driver:

    data = self.vip.rpc.call(<Driver HTTP Cache identity>, "driver_data_get", <driver_type>, 
                             <group_id>, url, headers, update_frequency=180, params=params, 
                             refresh=refresh).get()
                             
The headers and params values are expected to be dictionaries to use as the 
request headers and request data as if making an HTTP request. The update
frequency is specified by the calling agent (in this case the Ecobee driver) and
should reflect the amount of time between remote API updates (Ecobee updates the
data available from their API every 3 minutes).

Installation
------------

These are the most basic installation steps for the Driver HTTP Cache agent. This guide
assumes the user is in the VOLTTRON_ROOT directory, and the VOLTTRON platform has 
been installed and bootstrapped per the instructions in the VOLTTRON README.

    1. If the platform has not been started:
    
        ./start-volttron
        
    2. If the environment has not been activated - you should see (volttron) next to <user>@<host> in your terminal window
        
        . env/bin/activate
        
    3. Install the agent
    
        python scripts/install-agent.py -s services/core/DriverHTTPCache -i <agent identity>
        
    4. Start the agent
    
        vctl start <agent uuid or identity>
    
At this point the agent should be running and ready for driver RPC calls to a
remote API.
