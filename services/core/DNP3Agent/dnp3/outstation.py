# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / Kisensum.
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
# United States Department of Energy, nor SLAC, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

import logging
import sys

from volttron.platform.agent import utils

from pydnp3 import opendnp3, openpal, asiopal, asiodnp3

from models import PointValue, PointDefinition
from models import POINT_TYPE_ANALOG_INPUT, POINT_TYPE_BINARY_INPUT

utils.setup_logging()
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

    app = None
    outstation = None

    def __init__(self, local_ip, port, outstation_config):
        """
            Initialize the outstation's Application Layer.

        @param local_ip: Host name (DNS resolved) or IP address of remote endpoint. Default: 0.0.0.0.
        @param port: Port remote endpoint is listening on. Default: 20000.
        @param outstation_config: A dictionary of configuration parameters. All are optional. Parameters include:
            database_sizes: (integer) Size of the ??. Default: 10.
            event_buffers: (integer) Size of the database event buffers. Default: 10.
            allow_unsolicited: (boolean) Whether to allow unsolicited requests. Default: True.
            link_local_addr: (integer) Link layer local address. Default: 10.
            link_remote_addr: (integer) Link layer remote address. Default: 1.
            log_levels: List of bit field names (OR'd together) that filter what gets logged by DNP3. Default: NORMAL.
                        Possible values: ALL, ALL_APP_COMMS, ALL_COMMS, NORMAL, NOTHING
            threads_to_allocate: (integer) Threads to allocate in the manager's thread pool. Default: 1.
        """
        super(DNP3Outstation, self).__init__()

        _log.debug('Configuring the DNP3 stack.')
        self.stack_config = asiodnp3.OutstationStackConfig(outstation_config.get('database_sizes', opendnp3.DatabaseSizes.AllTypes(10)))
        self.stack_config.outstation.eventBufferConfig = outstation_config.get('event_buffers', opendnp3.EventBufferConfig().AllTypes(10))
        self.stack_config.outstation.params.allowUnsolicited = outstation_config.get('allow_unsolicited', True)
        self.stack_config.link.LocalAddr = outstation_config.get('link_local_addr', 10)
        self.stack_config.link.RemoteAddr = outstation_config.get('link_remote_addr', 1)
        self.stack_config.link.KeepAliveTimeout = openpal.TimeDuration().Max()

        # Configure the outstation database of points (input only) based on the contents of the data dictionary.
        _log.debug('Configuring the DNP3 Outstation database.')
        db_config = self.stack_config.dbConfig
        for point in PointDefinition.point_list():
            if point.point_type == POINT_TYPE_ANALOG_INPUT:
                cfg = db_config.analog[int(point.index)]
            elif point.point_type == POINT_TYPE_BINARY_INPUT:
                cfg = db_config.binary[int(point.index)]
            else:
                # This database's point configuration is limited to Binary and Analog input data types.
                cfg = None
            if cfg:
                cfg.clazz = point.eclass
                cfg.svariation = point.svariation
                cfg.evariation = point.evariation

        _log.debug('Creating a DNP3Manager.')
        threads_to_allocate = outstation_config.get('threads_to_allocate', 1)
        self.log_handler = asiodnp3.ConsoleLogger(False).Create(False)       # (or use this during regression testing)
        # self.log_handler = MyLogger()
        self.manager = asiodnp3.DNP3Manager(threads_to_allocate, self.log_handler)

        _log.debug('Creating the DNP3 channel, a TCP server.')
        self.retry_parameters = asiopal.ChannelRetry().Default()
        # self.listener = asiodnp3.PrintingChannelListener().Create()          # (or use this during regression testing)
        self.listener = AppChannelListener()
        self.channel = self.manager.AddTCPServer("server",
                                                 self.dnp3_log_level(outstation_config),
                                                 self.retry_parameters,
                                                 local_ip,
                                                 port,
                                                 self.listener)

        _log.debug('Adding the DNP3 Outstation to the channel.')
        # self.command_handler =  opendnp3.SuccessCommandHandler().Create()    # (or use this during regression testing)
        self.command_handler = OutstationCommandHandler()
        self.outstation = self.channel.AddOutstation("outstation", self.command_handler, self, self.stack_config)

        # Set the singleton instance that communicates with the Master.
        self.set_outstation(self.outstation)

        _log.debug('Enabling the DNP3 Outstation. Traffic can now start to flow.')
        self.outstation.Enable()

    def reload_parameters(self, local_ip, port, outstation_config):
        _log.debug('In reload_parameters')

    @classmethod
    def get_app(cls):
        """Return the singleton OutstationApp instance, which holds this implementation's Outstation business logic."""
        return cls.app

    @classmethod
    def set_app(cls, app):
        """Set the singleton instance of OutstationApp."""
        cls.app = app

    @classmethod
    def get_outstation(cls):
        """Get the singleton instance of IOutstation."""
        return cls.outstation

    @classmethod
    def set_outstation(cls, outstn):
        """
            Set the singleton instance of IOutstation, as returned from the channel's AddOutstation call.

            Making IOutstation available as a singleton allows other classes
            to send commands to it -- see apply_update().
        """
        cls.outstation = outstn

    def dnp3_log_level(self, outstation_config):
        """
            Return a bit-encoded integer that indicates the level of DNP3 logging.

            If a list of level names is specified in the Outstation config,
            use a union of those names to construct the integer. Otherwise return the default log level.
        """
        log_level_config_names = outstation_config.get('log_levels', [])
        if log_level_config_names:
            names_to_bitmasks = {
                'ALL': opendnp3.levels.ALL,
                'ALL_APP_COMMS': opendnp3.levels.ALL_APP_COMMS,
                'ALL_COMMS': opendnp3.levels.ALL_COMMS,
                'NORMAL': opendnp3.levels.NORMAL,
                'NOTHING': opendnp3.levels.NOTHING
            }
            log_level = 0
            for name in log_level_config_names:
                log_level = log_level | names_to_bitmasks.get(name, 0)
        else:
            log_level = opendnp3.levels.NORMAL
            log_level_config_names = 'default'
        _log.debug('Setting DNP3 log level={} ({})'.format(log_level, log_level_config_names))
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
        _log.debug('DNP3 GetApplicationIIN: IINField LSB={}, MSB={}'.format(iin_field.LSB, iin_field.MSB))
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
        builder = asiodnp3.UpdateBuilder()
        builder.Update(value, index)
        update = builder.Build()
        cls.get_outstation().Apply(update)

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


class OutstationApp:
    """
        This class enables inclusion of application-specific logic, responding to
        DNP3 activity such as receipt of a PointValue. This singleton's functions can be called
        from anywhere; process_point_value() is called from OutstationCommandHandler.
    """

    def __init__(self, publish_point_callback=None):
        """Initialize the OutstationApp instance. Configure a callback for publishing received point values."""
        self.publish_point_callback = publish_point_callback

    def process_point_value(self, point_value):
        """
            A PointValue was received from the Master. Process its payload.

        :param point_value: A PointValue.
        """
        _log.debug('Received DNP3 {}'.format(point_value))
        if point_value.command_type == 'Select':
            # Perform any needed validation now, then wait for the subsequent Operate command.
            pass
        else:
            PointValue.add_to_current_values(point_value)
            self.echo_point(point_value)
            if self.publish_point_callback:
                self.publish_point_callback(point_value)

    def echo_point(self, point_value):
        """
            When appropriate, echo a received PointValue, sending it back to the Master as Input.

        :param point_value: A PointValue.
        """
        echo = point_value.point_def.echo
        if echo is not None:
            # An echo has been defined. Send the received value back to the Master, using the configured point type.
            echo_point_type = PointDefinition.point_type_for_group(echo.get('group'))
            if echo_point_type == POINT_TYPE_ANALOG_INPUT:
                value = float(point_value.value)
                wrapped_value = opendnp3.Analog(value)
            elif echo_point_type == POINT_TYPE_BINARY_INPUT:
                # If the Master sent a function code, echo True if it was LATCH_ON, false otherwise
                value = point_value.value or (point_value.function_code == opendnp3.ControlCode.LATCH_ON)
                wrapped_value = opendnp3.Binary(value)
            else:
                value = wrapped_value = None
            if wrapped_value is not None:
                _log.debug('Echoing received DNP3 point, echo={}, type={}, value={}'.format(echo,
                                                                                            echo_point_type,
                                                                                            value))
                DNP3Outstation.apply_update(wrapped_value, echo.get('index'))


class OutstationCommandHandler(opendnp3.ICommandHandler):
    """
        ICommandHandler implements the Outstation's handling of Select and Operate,
        which relay commands and data from the Master to the Outstation.
    """

    def Start(self):
        _log.debug('In DNP3 OutstationCommandHandler.Start')

    def End(self):
        _log.debug('In DNP3 OutstationCommandHandler.End')

    def Select(self, command, index):
        """
            The Master sent a Select command to the Outstation. Handle it.

        :param command: ControlRelayOutputBlock,
                        AnalogOutputInt16, AnalogOutputInt32, AnalogOutputFloat32, or AnalogOutputDouble64.
        :param index: int
        :return: CommandStatus
        """
        point_value = PointValue.for_command('Select', command, index, None)
        if point_value:
            try:
                point_value = PointValue.for_command('Select', command, index, None)
                DNP3Outstation.get_app().process_point_value(point_value)
                return opendnp3.CommandStatus.SUCCESS
            except Exception as ex:
                _log.error('Error processing DNP3 Select command: {}'.format(ex))
                return opendnp3.CommandStatus.DOWNSTREAM_FAIL
        else:
            _log.error('No DNP3 PointDefinition for command with index {}'.format(index))
            return opendnp3.CommandStatus.DOWNSTREAM_FAIL

    def Operate(self, command, index, op_type):
        """
            The Master sent an Operate command to the Outstation. Handle it.

        :param command: ControlRelayOutputBlock,
                        AnalogOutputInt16, AnalogOutputInt32, AnalogOutputFloat32, or AnalogOutputDouble64.
        :param index: int
        :param op_type: OperateType
        :return: CommandStatus
        """
        point_value = PointValue.for_command('Operate', command, index, op_type)
        if point_value:
            try:
                point_value = PointValue.for_command('Operate', command, index, op_type)
                DNP3Outstation.get_app().process_point_value(point_value)
                return opendnp3.CommandStatus.SUCCESS
            except Exception as ex:
                _log.error('Error processing DNP3 Operate command: {}'.format(ex))
                return opendnp3.CommandStatus.DOWNSTREAM_FAIL
        else:
            _log.error('No DNP3 PointDefinition for command with index {}'.format(index))
            return opendnp3.CommandStatus.DOWNSTREAM_FAIL


class AppChannelListener(asiodnp3.IChannelListener):
    """
        IChannelListener has been overridden to implement application-specific channel behavior.
    """

    def __init__(self):
        super(AppChannelListener, self).__init__()

    def OnStateChange(self, state):
        _log.debug('In DNP3 AppChannelListener.OnStateChange: state={}'.format(state))


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


def main():
    """The Outstation has been started from the command line. Execute ad-hoc tests if desired."""
    local_ip = '0.0.0.0'
    port = 20000
    outstation_config = {}
    dnp3_outstation = DNP3Outstation(local_ip, port, outstation_config)
    dnp3_outstation.set_app(OutstationApp())
    _log.debug('DNP3 initialization complete. In command loop.')
    # Ad-hoc tests can be performed at this point if desired.
    dnp3_outstation.shutdown()
    _log.debug('DNP3 Outstation exiting.')
    exit()

if __name__ == '__main__':
    main()
