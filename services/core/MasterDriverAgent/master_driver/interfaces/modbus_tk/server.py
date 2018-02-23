# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

import argparse
import logging
import multiprocessing
import serial
import time
import socket
import types

from client import Client
from modbus_tk.modbus_tcp import TcpServer
from modbus_tk.modbus_rtu import RtuServer
from modbus_tk.hooks import install_hook

logger = logging.getLogger(__name__)

###########################################################################################
#   MONKEY PATCH ALERT
#
#   To allow regression tests to quickly start-up/shutdown their Modbus slaves,
#   we are monkey patching two methods in modbus_tk.modbus_tcp.TcpServer.  These changes
#   shutdown the socket as quickly as possible and re-use the socket port even if it is
#   in TIME_WAIT.  Both of these one line changes are REQUIRED to avoid the dreaded
#   "Address already in use" error.
#
###########################################################################################


def _do_init(self):
    """initialize server"""
    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if self._timeout_in_sec:
        self._sock.settimeout(self._timeout_in_sec)
    # BIND to port even if it is still in TIME_WAIT
    self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self._sock.setblocking(0)
    self._sock.bind(self._sa)
    self._sock.listen(10)
    self._sockets.append(self._sock)


def _do_exit(self):
    """clean the server tasks"""
    # close the sockets
    for sock in self._sockets:
        try:
            # Immediately shut down connection.
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            self._sockets.remove(sock)
        except Exception as msg:
            raise Exception("Error while closing socket, Exception occurred: %s", msg)
    self._sock.close()
    self._sock = None

###########################################################################################
#  The two methods above are patched the TcpServer instance that is created by Server
#  below. See Server.__init__ method.
###########################################################################################


class Server (object):
    """Base Modbus Server.

    Basic Modbus Server that implements both RTU and TCP. For setting up an RTU server, make sure 'port' is configured
    to 0.  Basic hooks are set up here, so that when subclassing this class, only minimal functions (namely update)
    need to be overwritten.

    A Server can have multiple slaves, although TCP protocol only allows for one (RTU allows for multiple slaves).
    In this instance, the slave id should be set to 1.

    This class is mostly used for testing to simulate a modbus server that we would see in the field.
    """
    def __init__(self, address='127.0.0.1', port=502, baud=19200, timeout_in_sec=1, databank=None):
        """Initialize Base Server and install modbus hooks

        Has two important instance variables:
            _server - an instance of a Modbus RTU or TCP server.
            _slaves - dictionary of ModbusClient slaves keyed by slave ID. (For TCP, this should be 1)

        :param address: Address of the Server (Not used in RTU). Defaults to 127.0.0.1
        :param port: Port of the Server (0 for RTU, defaults to 502 for TCP). For RTU, this MUST be set to 0.
        :param baud: Baudrate (Not used in TCP). Defaults to 19200
        :param timeout_in_sec: Timeout (Not used in RTU). Defaults to 1
        :param databank: (Not used in RTU)
        """

        if port == 0:
            server_serial = serial.Serial(
                address,
                baudrate=baud,
                bytesize=8,
                parity=serial.PARITY_EVEN,
                stopbits=1,
                xonxoff=0)
            self._server = RtuServer(server_serial)
        else:
            self._server = TcpServer(address=address, port=port, timeout_in_sec=timeout_in_sec, databank=databank)
            #  Begin Monkey Patch
            self._server._do_init = types.MethodType(_do_init, self._server)
            self._server._do_exit = types.MethodType(_do_exit, self._server)
            # End Monkey Patch

        self._slaves = dict()

        # Set up basic modbus hooks. These by default just log when they are getting called. To handle requests,
        #  subclasses of Server should overwrite the 'update' method, which is called by 'after'.
        self.install_hook('modbus.Server.before_handle_request', 'before')
        self.install_hook('modbus.Server.after_handle_request', 'after')
        self.install_hook('modbus.Slave.handle_write_multiple_registers_request', 'write_register')
        self.install_hook('modbus.Slave.handle_write_single_register_request', 'write_register')
        self.install_hook('modbus.Slave.handle_read_holding_registers_request', 'read_register')
        self.install_hook('modbus.Slave.handle_write_multiple_coils_request', 'write_coils')
        self.install_hook('modbus.Slave.handle_write_single_coil_request', 'write_coils')

    def define_slave(self, slave_id, client_class, unsigned=True):
        """Add a Modbus Client Slave.

        :param slave_id: Slave ID. This must be 1 for Modbus TCP.
        :param client_class: Subclass of modbus.Client. This class holds all the register definitions.
        :param unsigned: Boolean indicating whether or not values are signed or unsigned.
        :return: Slave instance.
        """
        self._slaves[slave_id] = client_class
        slave = self._server.add_slave(slave_id, unsigned=unsigned)
        slave.klass = client_class
        if not issubclass(client_class, Client):
            raise TypeError("client_class must be subclass of {0}".format(Client))

        for request in client_class().requests():
            logger.info("Adding [%s], %s, %s, %s", request.name, request.table, request.address, request.count)
            slave.add_block(request.name, request.table, request.address, request.count)
        return slave

    @classmethod
    def install_hook(cls, hook_name, method):
        """Helper method for installing hooks. This is necessary to ensure child methods are called if implemented."""
        install_hook(hook_name, getattr(cls, method))

    def set_values(self, slave_id, field, values):
        slave = self._server.get_slave(slave_id)
        slave_class = self._slaves[slave_id]
        request = slave_class().get_request(field)
        slave.set_values(request.name, field.address, values)

    ##################
    # Server Methods #
    ##################

    def start(self):
        self._server.start()

    def stop(self):
        self._server.stop()

    def is_alive(self):
        return self._server._thread.isAlive()

    def set_verbose(self, on=True):
        self._server.set_verbose(on)

    ######################
    # Basic Modbus Hooks #
    ######################

    @staticmethod
    def before(args):
        server, request = args
        logger.debug("Before: {0}-{1}".format(server, request))

    @classmethod
    def after(cls, args):
        server, response = args
        logger.debug("After: {0}-{1}".format(server, response))
        cls.update(args)

    @staticmethod
    def update(args):
        pass

    @staticmethod
    def write_register(args):
        slave, request_pdu = args
        logger.debug("Writing: {0}-{1}".format(slave, request_pdu))

    @staticmethod
    def read_register(args):
        slave, request_pdu = args
        logger.debug("Reading: {0}-{1}".format(slave, request_pdu))

    @staticmethod
    def write_coils(args):
        slave, request_pdu = args
        logger.debug("Writing Coils: {0}-{1}".format(slave, request_pdu))


class ServerProcess (multiprocessing.Process):
    """Parent process to set up, start, and run a Server Instance

    Used pretty heavily in testing.
    """
    def __init__(self, *args, **kwargs):
        """Instantiate Modbus Server Process

        kwargs
            host: Server IP address
            port: Server Port
            server_class: A subclass of Server if desired, otherwise defaults to server.
        """
        self._host = kwargs.pop('host', '127.0.0.1')
        self._port = kwargs.pop('port', 5020)

        self._server_class = kwargs.pop('server_class', Server)
        self._server = self._server_class(address=self._host, port=self._port)
        super(ServerProcess, self).__init__(*args, **kwargs)

    @property
    def server(self):
        return self._server

    def stop(self):
        logging.debug("Got SIGTERM. Stopping.")
        self._server.stop()
        super(ServerProcess, self).terminate()

    def run(self):
        logger.debug("Starting ModbusServer: %s", __name__)
        self._server.start()

        # Only way I know of to keep the process running/waiting on the server loop.
        import signal

        def handler(signum, frame):
            logging.debug("Got SIGTERM. Stopping.")
            self._server.stop()
            super(ServerProcess, self).terminate()

        signal.signal(signal.SIGTERM, handler)

        while self._server.is_alive():
            time.sleep(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server Host/IP Address")
    parser.add_argument("--port", type=int, default=5020, help="Server Port Number")
    args = parser.parse_args()

    modbus_server = ServerProcess(host=args.host, port=args.port)
    modbus_server.start()
    modbus_server.join()