clear; clc;

config_url = 'tcp://*:5556';       %Socket to send and receive configuration information
data_url = 'tcp://*:5557';    %Socket to send and receive device data
recv_timeout = 50000;          %Number of millisecond to wait for device data


%Open and connect sockets
context = py.zmq.Context();
config_socket = context.socket(py.zmq.PAIR);
config_socket.bind(config_url);
data_socket = context.socket(py.zmq.PAIR);
data_socket.bind(data_url);

%Sleep to allow sockets to connect.
py.time.sleep(1.0);

%Send config request to Volttron
disp('Sending config request');
try
    message = 'config';
    config_socket.send_string(message,py.zmq.NOBLOCK);
catch ZMQError
    disp('No Volttron agent running to receive message. Exiting');
    return
end

% Wait to receive config parameters
disp('waiting for config params')
event = config_socket.poll(recv_timeout);
if event > 0
    disp('Receiving config params and initial data')
    config_params = config_socket.recv_json();
    disp(config_params)
    
    disp('waiting for initial data')
    
    %TODO: add following code in loop to keep receiving device data
    
        % wait to receive data
        event = data_socket.poll(recv_timeout);
        if event > 0
           disp('Receiving data')
           data = data_socket.recv_pyobj();
           disp('Got data from WH')
           % Sample data = {'temperature_heater1': 12.0, 'temperature_heater3': 32.0, 'temperature_heater2': 22.0}
           disp(data)
        end

        %Send commands
        matlab_result = '{"commands":{"Zone1":[["temperature",27]],"Zone2":[["temperature",28]]}}';
        disp('sending matlab result')
        data_socket.send_json(matlab_result,py.zmq.NOBLOCK);
    
else
    disp('Config params not received. exiting')
    return
    
end

if not(config_socket.closed)
    config_socket.close();
end
if not(data_socket.closed)
    data_socket.close();
end