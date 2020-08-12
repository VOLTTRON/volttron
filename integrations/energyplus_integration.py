# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import os
import logging
from gevent import monkey, sleep
import weakref
import socket
import subprocess
from datetime import datetime
from calendar import monthrange
from volttron.platform.agent.base_simulation_integration.base_sim_integration import BaseSimIntegration

monkey.patch_socket()
_log = logging.getLogger(__name__)
__version__ = '1.0'

HAS_ENERGYPLUS = True


class EnergyPlusSimIntegration(BaseSimIntegration):
    """
    The class is responsible for integration with EnergyPlus simulation
    """

    def __init__(self, config, pubsub, core):
        super(EnergyPlusSimIntegration, self).__init__(config)
        self.pubsub = weakref.ref(pubsub)
        self.core = weakref.ref(core)
        self.current_time = 0
        self.inputs = []
        self.outputs = []
        self.current_values = {}
        self.version = 8.4
        self.bcvtb_home = '.'
        self.model = None
        self.customizedOutT = 0
        self.weather = None
        self.socketFile = None
        self.variableFile = None
        self.time = 0
        self.vers = 2
        self.flag = 0
        self.sent = None
        self.rcvd = None
        self.socket_server = None
        self.simulation = None
        self.step = None
        self.eplus_inputs = 0
        self.eplus_outputs = 0
        self.cosim_sync_counter = 0
        self.time_scale = 1.0
        self.passtime = False
        self.size = None
        self.real_time_flag = False
        self.currenthour = datetime.now().hour
        self.currentday = datetime.now().day
        self.currentmonth = datetime.now().month
        self.length = 1
        self.maxday = monthrange(2012, self.currentmonth)[1]
        self.callback = None
        self.month = None
        self.year = None
        self.day = None
        self.minute = None
        self.operation = None
        self.timestep = None
        self.cosimulation_sync = None
        self.real_time_periodic = None
        self.co_sim_timestep = None
        self.startmonth = None
        self.startday = None
        self.endmonth = None
        self.endday = None
        self.sim_flag = 0
        self.cwd = os.getcwd()

    def register_inputs(self, config=None, callback=None):
        """
        Store input and output configurations
        Save the user agent callback
        :return:
        """
        self.inputs = self.config.get('inputs', [])
        self.outputs = self.config.get('outputs', [])
        if 'properties' in self.config and isinstance(self.config['properties'], dict):
            self.__dict__.update(self.config['properties'])
        self.callback = callback

    def start_socket_server(self):
        """
        Connect to EnergyPlus socket server and
        register a receiver callback
        """
        self.socket_server = SocketServer()
        self.socket_server.size = self.size
        self.socket_server.on_recv = self.recv_eplus_msg
        self.socket_server.connect()
        self.core().spawn(self.socket_server.start)

    def start_simulation(self):
        """
        Start EnergyPlus simulation
        :return:
        """
        self.start_socket_server()
        self._start_eplus_simulation()

    def _start_eplus_simulation(self):
        """
        Check the model path and start EnergyPlus
        """
        if not self.model:
            self.exit('No model specified.')
        if not self.weather:
            self.exit('No weather specified.')
        model_path = self.model
        if model_path[0] == '~':
            model_path = os.path.expanduser(model_path)
        if model_path[0] != '/':
            model_path = os.path.join(self.cwd, model_path)
        weather_path = self.weather
        if weather_path[0] == '~':
            weather_path = os.path.expanduser(weather_path)
        if weather_path[0] != '/':
            weather_path = os.path.join(self.cwd, weather_path)
        model_dir = os.path.dirname(model_path)
        bcvtb_dir = self.bcvtb_home
        if bcvtb_dir[0] == '~':
            bcvtb_dir = os.path.expanduser(bcvtb_dir)
        if bcvtb_dir[0] != '/':
            bcvtb_dir = os.path.join(self.cwd, bcvtb_dir)
        _log.debug('Working in %r', model_dir)

        self._write_port_file(os.path.join(model_dir, 'socket.cfg'))
        self._write_variable_file(os.path.join(model_dir, 'variables.cfg'))

        if self.version >= 8.4:
            cmd_str = "cd %s; export BCVTB_HOME=%s; energyplus -w %s -r %s" % (
                model_dir, bcvtb_dir, weather_path, model_path)
        else:
            cmd_str = "export BCVTB_HOME=%s; runenergyplus %s %s" % (bcvtb_dir, model_path, weather_path)
        _log.debug('Running: %s', cmd_str)
        f = open(model_path, 'r')
        lines = f.readlines()
        f.close()
        endmonth = 0
        if self.currentday + self.length > self.maxday:
            endday = self.currentday + self.length - self.maxday
            endmonth = self.currentmonth + 1
        else:
            endday = self.currentday + self.length
            endmonth = self.currentmonth
        for i in range(len(lines)):
            if lines[i].lower().find('runperiod,') != -1:
                if not self.real_time_flag:
                    lines[i + 2] = '    ' + str(self.startmonth) + ',                       !- Begin Month' + '\n'
                    lines[i + 3] = '    ' + str(self.startday) + ',                       !- Begin Day of Month' + '\n'
                    lines[i + 4] = '    ' + str(self.endmonth) + ',                      !- End Month' + '\n'
                    lines[i + 5] = '    ' + str(self.endday) + ',                      !- End Day of Month' + '\n'
                else:
                    lines[i + 2] = '    ' + str(self.currentmonth) + ',                       !- Begin Month' + '\n'
                    lines[i + 3] = '    ' + str(
                        self.currentday) + ',                       !- Begin Day of Month' + '\n'
                    lines[i + 4] = '    ' + str(endmonth) + ',                      !- End Month' + '\n'
                    lines[i + 5] = '    ' + str(endday) + ',                      !- End Day of Month' + '\n'
        for i in range(len(lines)):
            if lines[i].lower().find('timestep,') != -1 and lines[i].lower().find('update frequency') == -1:
                if lines[i].lower().find(';') != -1:
                    lines[i] = '  Timestep,' + str(self.timestep) + ';' + '\n'
                else:
                    lines[i + 1] = '  ' + str(self.timestep) + ';' + '\n'
        if self.customizedOutT > 0:
            lines.append('ExternalInterface:Actuator,') + '\n'
            lines.append('    outT,     !- Name') + '\n'
            lines.append('    Environment,  !- Actuated Component Unique Name') + '\n'
            lines.append('    Weather Data,  !- Actuated Component Type') + '\n'
            lines.append('    Outdoor Dry Bulb;          !- Actuated Component Control Type') + '\n'
        f = open(model_path, 'w')

        for i in range(len(lines)):
            f.writelines(lines[i])
        f.close()
        self.simulation = subprocess.Popen(cmd_str, shell=True)

    def publish_all_to_simulation(self, inputs):
        self.inputs = inputs
        self.send_eplus_msg()

    def send_eplus_msg(self):
        """
        Send inputs to EnergyPlus
        """
        if self.socket_server:
            args = self.input()
            msg = '%r %r %r 0 0 %r' % (self.vers, self.flag, self.eplus_inputs, self.time)
            for obj in args:
                if obj.get('name', None) and obj.get('type', None):
                    msg = msg + ' ' + str(obj.get('value'))
            self.sent = msg + '\n'
            _log.info('Sending message to EnergyPlus: ' + msg)
            self.sent = self.sent.encode()
            self.socket_server.send(self.sent)
    
    def recv_eplus_msg(self, msg):
        """
        Receive outputs from EnergyPlus, parse the messages and hand it over
        to user callback
        """
        self.rcvd = msg
        self.parse_eplus_msg(msg)
        # Call Agent callback to do whatever with the message
        if self.callback is not None:
            self.callback()
    
    def parse_eplus_msg(self, msg):
        """
        Parse EnergyPlus message to update output values and
        simulation datetime
        """
        msg = msg.decode("utf-8") 
        msg = msg.rstrip()
        _log.info(f"Received message from EnergyPlus: {msg}")
        arry = msg.split()
        arry = [float(item) for item in arry]
        _log.info(f"Received message from EnergyPlus: {arry}")
        slot = 6
        self.sim_flag = arry[1]

        if self.sim_flag != 0.0:
            # Exit based on error status
            _log.debug("FLAG: {} - {}".format(self.sim_flag, type(self.sim_flag)))
            self._check_sim_flag()
        elif arry[2] < self.eplus_outputs and len(arry) < self.eplus_outputs + 6:
            self.exit('Got message with ' + arry[2] + ' inputs. Expecting ' + str(self.eplus_outputs) + '.')
        else:
            if float(arry[5]):
                self.time = float(arry[5])
            for input in self.inputs:
                name_value = input.get('name', None)
                dynamic_default_value = input.get('dynamic_default', None)
                if name_value is not None and dynamic_default_value is not None:
                    slot = 6
                    for output in self.outputs:
                        _log.debug("Output: {}".format(output))
                        default_value = output.get('default', None)
                        if default_value is not None:
                            if default_value.lower().find(name_value.lower()) != -1:
                                input['default'] = float(arry[slot])
                        slot += 1
            slot = 6
            for output in self.outputs:
                name_value = output.get('name', None)
                type_value = output.get('type', None)
                field_value = output.get('field', None)
                if name_value is not None and type_value is not None:
                    try:
                        output['value'] = float(arry[slot])
                    except:
                        _log.debug(slot)
                        self.exit('Unable to convert received value to double.')
                    if "currentmonthv" in type_value.lower():
                        self.month = float(arry[slot])
                        _log.debug(f"month {self.month}")
                    elif "currentdayofmonthv" in type_value.lower():
                        self.day = float(arry[slot])
                        _log.debug(f"day {self.day}")
                    elif "currenthourv" in type_value.lower():
                        self.hour = float(arry[slot])
                        _log.debug(f"hour {self.hour}")
                    elif "currentminutev" in type_value.lower():
                        self.minute = float(arry[slot])
                        _log.debug(f"minute: {self.minute}")
                    elif field_value is not None and 'operation' in field_value.lower():
                        self.operation = float(arry[slot])
                        _log.debug(f"operation (1:on, 0: off) {self.operation}")
                    slot += 1

    def _check_sim_flag(self):
        """
        Exit the process based on simulation status
        """
        if self.sim_flag == '1':
            self.exit('Simulation reached end: ' + self.sim_flag)
        elif self.sim_flag == '-1':
            self.exit('Simulation stopped with unspecified error: ' + self.sim_flag)
        elif self.sim_flag == '-10':
            self.exit('Simulation stopped with error during initialization: ' + self.sim_flag)
        elif self.sim_flag == '-20':
            self.exit('Simulation stopped with error during time integration: ' + self.sim_flag)

    def publish_to_simulation(self, topic, message):
        """
        Publish message on EnergyPlus simulation
        :param topic: EnergyPlus input field
        :param message: message
        :return:
        """
        pass

    def make_time_request(self, time_request=None):
        """
        Cannot request time with energyplus
        :param time_request:
        :return:
        """
        pass

    def pause_simulation(self):
        pass

    def resume_simulation(self):
        pass

    def is_sim_installed(self):
        return HAS_ENERGYPLUS

    def stop_simulation(self):
        """
        Stop EnergyPlus simulation
        :return:
        """
        if self.socket_server:
            # Close connection to EnergyPlus server
            self.socket_server.stop()
            self.socket_server = None

    def _write_port_file(self, path):
        fh = open(path, "w+")
        fh.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        fh.write('<BCVTB-client>\n')
        fh.write('  <ipc>\n')
        fh.write('    <socket port="%r" hostname="%s"/>\n' % (self.socket_server.port, self.socket_server.host))
        fh.write('  </ipc>\n')
        fh.write('</BCVTB-client>')
        fh.close()

    def _write_variable_file(self, path):
        fh = open(path, "w+")
        fh.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        fh.write('<!DOCTYPE BCVTB-variables SYSTEM "variables.dtd">\n')
        fh.write('<BCVTB-variables>\n')
        for obj in self.outputs:
            if 'name' in obj and 'type' in obj:
                self.eplus_outputs = self.eplus_outputs + 1
                fh.write('  <variable source="EnergyPlus">\n')
                fh.write('    <EnergyPlus name="%s" type="%s"/>\n' % (obj.get('name'), obj.get('type')))
                fh.write('  </variable>\n')
        for obj in self.inputs:
            if 'name' in obj and 'type' in obj:
                self.eplus_inputs = self.eplus_inputs + 1
                fh.write('  <variable source="Ptolemy">\n')
                fh.write('    <EnergyPlus %s="%s"/>\n' % (obj.get('type'), obj.get('name')))
                fh.write('  </variable>\n')
        fh.write('</BCVTB-variables>\n')
        fh.close()

    def input(self):
        return self.inputs


class SocketServer(object):
    """
    Socket Server class for connecting to EnergyPlus
    """
    def __init__(self, **kwargs):
        self.sock = None
        self.size = 4096
        self.client = None
        self.sent = None
        self.rcvd = None
        self.host = "127.0.0.1"
        self.port = None

    def on_recv(self, msg):
        _log.debug('Received %s' % msg)

    def run(self):
        self.listen()

    def connect(self):
        if self.host is None:
            self.host = socket.gethostname()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.port is None:
            self.sock.bind((self.host, 0))
            self.port = self.sock.getsockname()[1]
        else:
            self.sock.bind((self.host, self.port))
        _log.debug('Bound to %r on %r' % (self.port, self.host))

    def send(self, msg):
        self.sent = msg
        if self.client is not None and self.sock is not None:
            try:
                self.client.send(self.sent)
            except Exception:
                _log.error('We got an error trying to send a message.')

    def recv(self):
        if self.client is not None and self.sock is not None:
            try:
                msg = self.client.recv(self.size)
            except Exception:
                _log.error('We got an error trying to read a message')
            return msg

    def start(self):
        _log.debug('Starting socket server')
        self.run()

    def stop(self):
        if self.sock != None:
            self.sock.close()

    def listen(self):
        self.sock.listen(10)
        _log.debug('server now listening')
        self.client, addr = self.sock.accept()
        _log.debug('Connected with ' + addr[0] + ':' + str(addr[1]))
        while True:
            msg = self.recv()
            if msg:
                self.rcvd = msg
                self.on_recv(msg)
