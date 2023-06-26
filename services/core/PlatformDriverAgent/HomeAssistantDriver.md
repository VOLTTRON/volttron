**VOLTTRON Home Assistant Driver.** 

Please see the README for the platform driver.
[services/core/PlatformDriverAgent/README.md](https://github.com/riley206/Rileys_volttron/blob/55146b78d3ab7f53d08598df272cdda2d0aa8d3d/services/core/PlatformDriverAgent/README.md)
```mermaid
  sequenceDiagram
    HomeAssistant Driver->>HomeAssistant: Retrieve Entity Data (REST API)
    HomeAssistant-->>HomeAssistant Driver: Entity Data (Status Code: 200)
    HomeAssistant Driver->>PlatformDriverAgent: Publish Entity Data
    PlatformDriverAgent->>Controller Agent: Publish Entity Data

    Controller Agent->>HomeAssistant Driver: Instruct to Turn Off Light
    HomeAssistant Driver->>HomeAssistant: Send Turn Off Light Command (REST API)
    HomeAssistant-->>HomeAssistant Driver: Command Acknowledgement (Status Code: 200)

```
The first thing you will need is the IP address and your long lived access token from your Home Assistant instance. 
In the Home Assistant ui you can click on your profile picture and scroll all the way down to find your long lived access token. 
![image](https://github.com/riley206/Rileys_volttron/assets/89715390/deb8d632-b0db-45de-ac7d-88c27e5fb2a1)


Next, you can either clone this repository as is, or manually grab the three files necessary to add to your VOLTTRON instance.

The three files you will need are HomeAssistant_Driver/home_assistant.config, HomeAssistant_Driver/home_assistant_registers.json, and services/core/PlatformDriverAgent/platform_driver/interfaces/home_assistant.py

Once you have these files in the same place (or you just cloned this) you can add what you need to the config file and the registers file. The config file stores your IP address, your port, and your access token from Home Assistant. If you would like to send data from VOLTTRON to Home Assistant, you can change "devices/fake-device/all" to whatever device running in VOLTTRON. You can then add the points in the points_to_grab_from_topic. This will take point values from devices running in VOLTTRON and send them to Home Assistant. If you do not want anything to be sent you can leave default or leave blank.

For example if you are running the fake driver in VOLTTRON and want to send data, the volttron_topic would be "devices/fake-device/all" and you can grab points such as EKG and EKG_Cos to send to Home Assistant.

```json
{
    "driver_config": {
        "ip_address": "Your Home Assistant IP",
        "access_token": "Your Home Assistant Access Token",
        "volttron_topic": "devices/fake-device/all",
        "points_to_grab_from_topic": ["EKG", "EKG_Cos"],
        "port": "Your Home Assistant Port"
    },
    "driver_type": "home_assistant",
    "registry_config":"config://home_assistant_registers.json",
    "interval": 30,
    "timezone": "UTC"
}
```
Your register file will contain the entities along with their attributes. For devices with no attributes lets say for example a humidity sensor, this driver will label the humidity as state since its the only value being pulled. If you would like to change this to another value you can add the attribute state_replace and the name of what it should be. For example "state_replace": "humidity". Since this sensor only pulls one value it will replace state: 50% with humidity: 50%.

```json
    {
        "Point Name": "sensor.average_humidity_1621",
        "Volttron Point Name": "sensor.average_humidity_1621",
        "Units": "%",
        "Units Details": "%",
        "Writable": true,
        "Starting Value": 20,
        "Type": "float",
        "Notes": "Average humidity of 1621",
        "Attributes": {
            "state_replace": "humidity"
        }
    },
```

Other devices such as thermostats will have multiple attributes, simply add the attributes in the attributes field so we can keep values the same. 

```json
    {
        "Point Name": "climate.thermostat",
        "Volttron Point Name": "climate.thermostat",
        "Units": "C",
        "Units Details": "C",
        "Writable": true,
        "Starting Value": true,
        "Type": "boolean",
        "Notes": "lights bedroom",
        "Attributes": {
            "temperature": "current_temperature",
            "humidity": "current_humidity"
        }
    },
```
For example, let's consider a thermostat with an attribute called "current_temperature" in Home Assistant. In order to keep data continuity and ensure consistency, we can map this attribute to the key "temperature" in VOLTTRON. This means that in VOLTTRON the attribute will show as "temperature" while it actually corresponds to the attribute "current_temperature" in Home Assistant. 

Attributes can be found in developer tools or by opening the device in the GUI of Home Assistant. 

![image](https://github.com/riley206/Rileys_volttron/assets/89715390/a367e61e-8b73-4f35-a179-dfda235ddcbe)


We are now ready to get the driver running. Right now you can install the listener agent and a historian if you are looking to store data and view in VOLTTRON. Install the platform driver and make sure the home_assistant.py is in the interfaces folder. 

Add the registers file and the config file into the VOLTTRON config store. 

here are examples:  vctl config store platform.driver home_assistant_registers.csv HomeAssistant_Driver/home_assistant_registers.json --json
                    vctl config store platform.driver devices/fakedevice examples/configurations/driver/fake.config

Once this is complete you should be able to start the platform driver and tail the volttron log to see the devices being pulled in from Home Asssistant. 

**VOLTTRON Home Assistant Driver - Code.**

Pulling Data from Home Assistant:

Pulling data from Home Assistant is managed by the get_entity_data function, which is called within the _scrape_all function. The get_entity_data function starts by creating the headers used for the REST API which includes your access token for authorization. We then create the URL with the last segment of the URL being the entitiy_id we have retireved through the registers file. This will grab the JSON data about that entity and return the response. 

```python
    def _scrape_all(self):
        result = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False)

        def get_entity_data(entity_id):
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            url = f"http://{self.ip_address}:{self.port}/api/states/{entity_id}" # the /states grabs cuurent state AND attributes of a specific entity
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json() # return the json attributes from entity
            else:
                _log.error(f"Request failed with status code {response.status_code}: {entity_id} {response.text}")
                return None
```

Next, we loop through the read and write registers, which contain the entity IDs. We assign entity_id to our point names and attributes to attributes. Lastly, entity_data is assigned as the function is called to pass the entity data we got from the API into the entity_data variable. 

```python
        for register in read_registers + write_registers:
            
            entity_id = register.point_name
            attributes = register.attributes
            entity_data = get_entity_data(entity_id) # assign arrtributes to entity_data  
```

**Controlling Entities**

Controlling Home Assistant entities happens in the parse_config method.

As before, we need to create headers and a URL for use. This time we use light/turn_on at the end of the URL, the "light" is the domain and "turn_on" is the service. You can read more here https://developers.home-assistant.io/docs/api/rest/ 

Next, we add the entity_id and brightness in the payload to add it to our response, we also use requests.post rather than requests.get. 
When we call the function, it will turn on all the lights and set the brightness. Control for the thermostats is pretty much the same. 

We also assume that light entities start with "light" since in Home Assistant all light entites will indeed start with the string light. This allows us to only send controls for lights rather than sending the turn_on service to other devices. The same has been done for thermostats. 

```python
        def turn_on_lights(brightness_level):
            url2 = f"http://{self.ip_address}:{self.port}/api/services/light/turn_on"
            
            headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
            point_names = point_name.split('\n')
            for entity in point_names:
                if entity.startswith("light"): # this will ensure that only lights are conrolled and not other devices
                    try:
                     # ranges from 0 - 255 for most lights
                        payload = {
                            "entity_id": f"{entity}",
                            "brightness": brightness_level,
                        }
                        response = requests.post(url2, headers=headers, data=json.dumps(payload))
                        if response.status_code == 200:
                            _log.info(f"Turned on {entity}")
                    except:
                        continue
                else:
                    continue
```

**Reaacting to changes**

Reacting to changes happens in the _create_subscriptions and _handle_publish functions. 

```python
    def _create_subscriptions(self, topic):
        """
        Unsubscribe from all pub/sub topics and create a subscription to a topic in the configuration which triggers
        the _handle_publish callback
        """
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self._handle_publish)    
        
    def _handle_publish(self, peer, sender, bus, topic, headers, messages):
        for message in messages: #subscribes to itself then stores states and if they change it runs the commands 
            for entity_id, entity_data in message.items():
                
                state = entity_data.get("state", None)
                brightness = entity_data.get("brightness", None)
                temperature = entity_data.get("temperature", None)

                previous_state = self.previous_states.get(entity_id, None)
                previous_brightness = self.previous_states.get(f"{entity_id}_brightness", None)
                previous_temperature = self.previous_states.get(f"{entity_id}_temperature", None)

                #LIGHTS
                if entity_id.startswith("light.") and not self.first_pass: #if it starts with light and its not the first pass to store previous values. 
                    if state != previous_state:  # if state changed
                        if state == "on":
                            _log.info(f"{entity_id} value has been detected as on")
                            self.turn_on_lights(entity_id, 255 if brightness is None else brightness)
                        elif state == "off":
                            _log.info(f"{entity_id} detected as off!")
                            self.turn_off_lights(entity_id)
                        else:
                            continue

                    # this handles brightness change even when state doesn't change
                    if brightness != previous_brightness:
                        _log.info(f"{entity_id} brightness has been detected and changed to {brightness} / 254")
                        self.turn_on_lights(entity_id, brightness)

                    self.previous_states[entity_id] = state
                    self.previous_states[f"{entity_id}_brightness"] = brightness # example previous_states[light.entity_brightness] = brightness

                # THERMOSTATS
                elif entity_id.startswith("climate.") and not self.first_pass:

                    if state != previous_state:
                        if state == "cool":
                            self.change_thermostat_mode("cool")
                            _log.info(f"{entity_id} value has been changed to cool")
                        elif state == "heat":
                            _log.info(f"{entity_id} value has been changed to heat")
                            self.change_thermostat_mode("heat")
                        elif state == "off":
                            _log.info(f"{entity_id} value has been changed to off")
                            self.change_thermostat_mode("off")
                        else: 
                            continue
                    if temperature != previous_temperature:
                        _log.info(f"{entity_id} temperature has been detected and changed to {temperature} degrees F")
                        self.set_thermostat_temperature(temperature)

                    self.previous_states[entity_id] = state
                    self.previous_states[f"{entity_id}_temperature"] = temperature # example previous_states[light.entity_brightness] = brightness
                else:
                    continue
            if self.first_pass:
                self.first_pass = False
```

This is not the ideal setup and will most likely be updated in the future. This works by subscribing to its own point on the message bus and storing its values during the first run, after the second run of the code it will check if the values have changed and if they have it will call the Home Assistant control functions to take action. For example, if a light goes from on to off, it will run the turn_off_lights function. 