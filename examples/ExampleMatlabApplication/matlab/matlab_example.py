import zmq

config_url = "tcp://localhost:5556"
data_url = "tcp://localhost:5557"
recv_timeout = 10000

context = zmq.Context()

config_socket = context.socket(zmq.PAIR)
config_socket.connect(config_url)

data_socket = context.socket(zmq.PAIR)
data_socket.connect(data_url)

#Wait for config request for given seconds
print("Waiting for config request")
event = config_socket.poll(recv_timeout)
# If there request received send config parameters and values
if event > 0 and config_socket.recv_string() == "config":
    try:
        print("Sending config_params")
        config_params = {"zone_temperature_list": ["ZoneTemperature1", "ZoneTemperature2"],
                        "zone_setpoint_list": ["ZoneTemperatureSP1", "ZoneTemperatureSP2"]}
        config_socket.send_json(config_params,zmq.NOBLOCK)

        print("Sending data")
        data = {"zone_temperature_list": ["72.3", "78.5"]}
        data_socket.send_pyobj(data,zmq.NOBLOCK)

    except ZMQError:
        print("No Matlab process running to send message")

    print("Waiting for matlab results")
    # wait for message from matlab
    event = data_socket.poll(recv_timeout)
    if event > 0:
        msg = data_socket.recv_json()
        print("Received commands"+msg)
else:
    print('Config request not received. Exiting.')


config_socket.close();
data_socket.close();