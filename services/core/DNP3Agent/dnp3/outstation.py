# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / 8minutenergy / Kisensum.
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
# This material was prepared in part as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor SLAC, nor 8minutenergy, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, 8minutenergy, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

import os
import logging

from pydnp3 import opendnp3, openpal, asiopal, asiodnp3

# from volttron.platform.agent import utils

# utils.setup_logging()
_log = logging.getLogger(__name__)


class DNP3Outstation(opendnp3.IOutstationApplication):
    """
        Model the Application Layer of a DNP3 outstation.

        This class models the interface for all outstation callback info except for control requests.

        DNP3 spec section 5.1.6.2:
            The Application Layer provides the following services for the DNP3 User Layer in an outstation:
                - Notifies the DNP3 User Layer when action requests, such as control output,
                  analog output, freeze and file operations, arrive from a master.
                - Requests data and information from the outstation that is wanted by a master
                  and formats the responses returned to a master.
                - Assures that event data is successfully conveyed to a master (using
                  Application Layer confirmation).
                - Sends notifications to the master when the outstation restarts, has queued events,
                  and requires time synchronization.

        DNP spec section 5.1.6.3:
            The Application Layer requires specific services from the layers beneath it.
                - Partitioning of fragments into smaller portions for transport reliability.
                - Knowledge of which device(s) were the source of received messages.
                - Transmission of messages to specific devices or to all devices.
                - Message integrity (i.e., error-free reception and transmission of messages).
                - Knowledge of the time when messages arrive.
                - Either precise times of transmission or the ability to set time values
                  into outgoing messages.
    """

    outstation = None
    outstation_config = {}
    agent = None

    def __init__(self, local_ip, port, outstation_config):
        """
            Initialize the outstation's Application Layer.

        @param local_ip: Host name (DNS resolved) or IP address of remote endpoint. Default: 0.0.0.0.
        @param port: Port remote endpoint is listening on. Default: 20000.
        @param outstation_config: A dictionary of configuration parameters. All are optional. Parameters include:
            database_sizes: (integer) Size of the Outstation's point database, by point type. Default: 10000.
            event_buffers: (integer) Size of the database event buffers. Default: 10.
            allow_unsolicited: (boolean) Whether to allow unsolicited requests. Default: True.
            link_local_addr: (integer) Link layer local address. Default: 10.
            link_remote_addr: (integer) Link layer remote address. Default: 1.
            log_levels: List of bit field names (OR'd together) that filter what gets logged by DNP3. Default: [NORMAL].
                        Possible values: ALL, ALL_APP_COMMS, ALL_COMMS, NORMAL, NOTHING
            threads_to_allocate: (integer) Threads to allocate in the manager's thread pool. Default: 1.
        """
        super(DNP3Outstation, self).__init__()
        self.local_ip = local_ip
        self.port = port
        self.set_outstation_config(outstation_config)
        # The following variables are initialized after start() is called.
        self.stack_config = None
        self.log_handler = None
        self.manager = None
        self.retry_parameters = None
        self.listener = None
        self.channel = None
        self.command_handler = None

    def start(self):
        _log.debug('Configuring the DNP3 stack.')
        self.stack_config = asiodnp3.OutstationStackConfig(opendnp3.DatabaseSizes.AllTypes(self.outstation_config.get('database_sizes', 10000)))
        self.stack_config.outstation.eventBufferConfig = opendnp3.EventBufferConfig.AllTypes(self.outstation_config.get('event_buffers', 10))
        self.stack_config.outstation.params.allowUnsolicited = self.outstation_config.get('allow_unsolicited', True)
        self.stack_config.link.LocalAddr = self.outstation_config.get('link_local_addr', 10)
        self.stack_config.link.RemoteAddr = self.outstation_config.get('link_remote_addr', 1)
        self.stack_config.link.KeepAliveTimeout = openpal.TimeDuration().Max()

        # Configure the outstation database of points based on the contents of the data dictionary.
        _log.debug('Configuring the DNP3 Outstation database.')
        db_config = self.stack_config.dbConfig
        for point in self.get_agent().point_definitions.all_points():
            if point.point_type == 'Analog Input':
                cfg = db_config.analog[int(point.index)]
            elif point.point_type == 'Binary Input':
                cfg = db_config.binary[int(point.index)]
            else:
                # This database's point configuration is limited to Binary and Analog data types.
                cfg = None
            if cfg:
                cfg.clazz = point.eclass
                cfg.svariation = point.svariation
                cfg.evariation = point.evariation

        _log.debug('Creating a DNP3Manager.')
        threads_to_allocate = self.outstation_config.get('threads_to_allocate', 1)
        # self.log_handler = asiodnp3.ConsoleLogger().Create()              # (or use this during regression testing)
        # self.log_handler = MyLogger().Create()
        self.log_handler = MyLogger()
        self.manager = asiodnp3.DNP3Manager(threads_to_allocate, self.log_handler)

        _log.debug('Creating the DNP3 channel, a TCP server.')
        self.retry_parameters = asiopal.ChannelRetry().Default()
        # self.listener = asiodnp3.PrintingChannelListener().Create()       # (or use this during regression testing)
        self.listener = AppChannelListener()
        self.channel = self.manager.AddTCPServer("server",
                                                 self.dnp3_log_level(),
                                                 self.retry_parameters,
                                                 self.local_ip,
                                                 self.port,
                                                 self.listener)

        _log.debug('Adding the DNP3 Outstation to the channel.')
        # self.command_handler =  opendnp3.SuccessCommandHandler().Create() # (or use this during regression testing)
        self.command_handler = OutstationCommandHandler()
        self.outstation = self.channel.AddOutstation("outstation", self.command_handler, self, self.stack_config)

        # Set the singleton instance that communicates with the Master.
        self.set_outstation(self.outstation)

        _log.info('Enabling the DNP3 Outstation. Traffic can now start to flow.')
        self.outstation.Enable()

    def reload_parameters(self, local_ip, port, outstation_config):
        _log.debug('In reload_parameters')
        self.local_ip = local_ip
        self.port = port
        self.outstation_config = outstation_config

    @classmethod
    def get_agent(cls):
        """Return the singleton DNP3Agent or MesaAgent instance."""
        agt = cls.agent
        if agt is None:
            raise ValueError('Outstation has no configured agent')
        return agt

    @classmethod
    def set_agent(cls, agent):
        """Set the singleton DNP3Agent or MesaAgent instance."""
        cls.agent = agent

    @classmethod
    def get_outstation(cls):
        """Get the singleton instance of IOutstation."""
        outst = cls.outstation
        if outst is None:
            raise AttributeError('IOutstation is not yet enabled')
        return outst

    @classmethod
    def set_outstation(cls, outstn):
        """
            Set the singleton instance of IOutstation, as returned from the channel's AddOutstation call.

            Making IOutstation available as a singleton allows other classes
            to send commands to it -- see apply_update().
        """
        cls.outstation = outstn

    @classmethod
    def get_outstation_config(cls):
        """Get the outstation_config, a dictionary of configuration parameters."""
        return cls.outstation_config

    @classmethod
    def set_outstation_config(cls, outstn_cfg):
        """
            Set the outstation_config.

            It's managed as a class variable so that it can be examined by the class method apply_update().

        :param outstn_cfg: A dictionary of configuration parameters.
        """
        cls.outstation_config = outstn_cfg

    def dnp3_log_level(self):
        """
            Return a bit-encoded integer that indicates the level of DNP3 logging.

            If a list of level names is specified in the Outstation config,
            use a union of those names to construct the integer. Otherwise return the default log level.
        """
        log_level_list = self.outstation_config.get('log_levels', ['NORMAL'])
        # log_level_list should be a list of strings. If it's not (e.g., if it's a simple string), fail.
        if not isinstance(log_level_list, list):
            raise TypeError('log_levels should be configured as a list of strings, not as {}'.format(log_level_list))
        log_level_list = [s.upper() for s in log_level_list]

        name_to_bitmasks = {
            'ALL': opendnp3.levels.ALL,
            'ALL_APP_COMMS': opendnp3.levels.ALL_APP_COMMS,
            'ALL_COMMS': opendnp3.levels.ALL_COMMS,
            'NORMAL': opendnp3.levels.NORMAL,
            'NOTHING': opendnp3.levels.NOTHING
        }
        log_level = 0
        for name in log_level_list:
            log_level = log_level | name_to_bitmasks.get(name, 0)

        _log.debug('Setting DNP3 log level={} ({})'.format(log_level, log_level_list))
        return log_level

    # Overridden method
    def ColdRestartSupport(self):
        """Return a RestartMode enumerated type value indicating whether cold restart is supported."""
        _log.debug('In DNP3 ColdRestartSupport')
        return opendnp3.RestartMode.UNSUPPORTED

    # Overridden method
    def GetApplicationIIN(self):
        """Return the application-controlled IIN field."""
        application_iin = opendnp3.ApplicationIIN()
        application_iin.configCorrupt = False
        application_iin.deviceTrouble = False
        application_iin.localControl = False
        application_iin.needTime = False
        iin_field = application_iin.ToIIN()
        # Experiment with setting iin_field to an error value, e.g. configCorrupt to indicate that
        # a point couldn't be found in the Outstation's database.
        # Other interesting IIN values might be PARAM_ERROR, ALREADY_EXECUTING, FUNC_NOT_SUPPORTED.
        if iin_field.LSB != 0 or iin_field.MSB != 0:
            status_string = 'IINField LSB={}, MSB={}'.format(iin_field.LSB, iin_field.MSB)
            DNP3Outstation.get_agent().publish_outstation_status(status_string)
        return application_iin

    # Overridden method
    def SupportsAssignClass(self):
        _log.debug('In DNP3 SupportsAssignClass')
        return False

    # Overridden method
    def SupportsWriteAbsoluteTime(self):
        _log.debug('In DNP3 SupportsWriteAbsoluteTime')
        return False

    # Overridden method
    def SupportsWriteTimeAndInterval(self):
        _log.debug('In DNP3 SupportsWriteTimeAndInterval')
        return False

    # Overridden method
    def WarmRestartSupport(self):
        """Return a RestartMode enumerated value indicating whether a warm restart is supported."""
        _log.debug('In DNP3 WarmRestartSupport')
        return opendnp3.RestartMode.UNSUPPORTED

    @classmethod
    def apply_update(cls, value, index):
        """
            Record an opendnp3 data value (Analog, Binary, etc.) in the outstation's database.

            The data value gets sent to the Master as a side-effect.

        :param value: An instance of Analog, Binary, or another opendnp3 data value.
        :param index: (integer) Index of the data definition in the opendnp3 database.
        """
        _log.debug('Recording DNP3 {} measurement, index={}, value={}'.format(type(value).__name__, index, value.value))
        max_index = cls.get_outstation_config().get('database_sizes', 10000)
        if index > max_index:
            raise ValueError('Attempt to set a value for index {} which exceeds database size {}'.format(index,
                                                                                                         max_index))
        builder = asiodnp3.UpdateBuilder()
        builder.Update(value, index)
        update = builder.Build()
        try:
            cls.get_outstation().Apply(update)
        except AttributeError as err:
            if not os.environ.get('UNITTEST', False):
                raise err

    def shutdown(self):
        """
            Execute an orderly shutdown of the Outstation.

            The debug messages may be helpful if errors occur during shutdown.
        """
        _log.debug('Exiting DNP3 Outstation module...')
        _log.debug('Garbage collecting DNP3 Outstation...')
        self.set_outstation(None)
        _log.debug('Garbage collecting DNP3 stack config...')
        self.stack_config = None
        _log.debug('Garbage collecting DNP3 channel...')
        self.channel = None
        _log.debug('Garbage collecting DNP3Manager...')
        self.manager = None


class OutstationCommandHandler(opendnp3.ICommandHandler):
    """
        ICommandHandler implements the Outstation's handling of Select and Operate,
        which relay commands and data from the Master to the Outstation.
    """

    def Start(self):
        # This debug line is too chatty...
        # _log.debug('In DNP3 OutstationCommandHandler.Start')
        pass

    def End(self):
        # This debug line is too chatty...
        # _log.debug('In DNP3 OutstationCommandHandler.End')
        pass

    def Select(self, command, index):
        """
            The Master sent a Select command to the Outstation. Handle it.

        :param command: ControlRelayOutputBlock,
                        AnalogOutputInt16, AnalogOutputInt32, AnalogOutputFloat32, or AnalogOutputDouble64.
        :param index: int
        :return: CommandStatus
        """
        return DNP3Outstation.get_agent().process_point_value('Select', command, index, None)

    def Operate(self, command, index, op_type):
        """
            The Master sent an Operate command to the Outstation. Handle it.

        :param command: ControlRelayOutputBlock,
                        AnalogOutputInt16, AnalogOutputInt32, AnalogOutputFloat32, or AnalogOutputDouble64.
        :param index: int
        :param op_type: OperateType
        :return: CommandStatus
        """
        return DNP3Outstation.get_agent().process_point_value('Operate', command, index, op_type)


class AppChannelListener(asiodnp3.IChannelListener):
    """
        IChannelListener has been overridden to implement application-specific channel behavior.
    """

    def __init__(self):
        super(AppChannelListener, self).__init__()

    def OnStateChange(self, state):
        """
            There has been an outstation state change. Publish the new state to the message bus.

        :param state: A ChannelState.
        """
        DNP3Outstation.get_agent().publish_outstation_status(str(state))


# class MyLogger(asiodnp3.ConsoleLogger):
class MyLogger(openpal.ILogHandler):
    """
        ILogHandler has been overridden to implement application-specific logging behavior.
    """

    def __init__(self):
        super(MyLogger, self).__init__()

    def Log(self, entry):
        """Write a DNP3 log entry to the logger (debug level)."""
        location = entry.location.rsplit('/')[-1] if entry.location else ''
        filters = entry.filters.GetBitfield()
        message = entry.message
        _log.debug('DNP3Log {0}\t(filters={1}) {2}'.format(location, filters, message))
        # This is here as an example of how to send a specific log entry to the message bus as outstation status.
        # if 'Accepted connection' in message or 'Listening on' in message:
        #     DNP3Outstation.get_agent().publish_outstation_status(str(message))


def main():
    """The Outstation has been started from the command line. Execute ad-hoc tests if desired."""
    dnp3_outstation = DNP3Outstation('0.0.0.0', 20000, {})
    dnp3_outstation.start()
    _log.debug('DNP3 initialization complete. In command loop.')
    # Ad-hoc tests can be performed at this point if desired.
    dnp3_outstation.shutdown()
    _log.debug('DNP3 Outstation exiting.')
    exit()

if __name__ == '__main__':
    main()
