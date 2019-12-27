from paho.mqtt.client import MQTTv311, MQTTv31
from paho.mqtt.subscribe import callback

PORT = 5000
PROTOCOL = MQTTv311

# Callback function to print out message topics and payloads
def listen(client, userdata, message):
    print(message.topic, message.payload)

# Subscribe to all messages and loop forever
callback(listen, '#', port=PORT, protocol=PROTOCOL)
