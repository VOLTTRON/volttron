# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, 8minutenergy / Kisensum.
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
# Neither 8minutenergy nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by 8minutenergy or Kisensum.
# }}}

import logging

from pydnp3 import opendnp3, openpal, asiopal, asiodnp3

_log = logging.getLogger(__name__)


class DNP3Master:
    """
        Interface for all master application callback info except for measurement values.
    """

    def __init__(self,
                 log_levels=opendnp3.levels.NORMAL | opendnp3.levels.ALL_APP_COMMS,
                 host_ip="127.0.0.1",  # presumably outstation
                 local_ip="0.0.0.0",
                 port=20000,
                 log_handler=asiodnp3.ConsoleLogger().Create(),
                 channel_listener=asiodnp3.PrintingChannelListener().Create(),
                 soe_handler=asiodnp3.PrintingSOEHandler().Create(),
                 master_application=asiodnp3.DefaultMasterApplication().Create(),
                 stack_config=None):

        self.log_levels = log_levels
        self.host_ip = host_ip
        self.local_ip = local_ip
        self.port = port
        self.log_handler = log_handler
        self.channel_listener = channel_listener
        self.soe_handler = soe_handler
        self.master_application = master_application

        self.stackConfig = stack_config
        if not self.stackConfig:
            # The master config object for a master.
            self.stackConfig = asiodnp3.MasterStackConfig()
            self.stackConfig.master.responseTimeout = openpal.TimeDuration().Seconds(2)
            self.stackConfig.link.RemoteAddr = 10

        self.manager = None
        self.channel = None
        self.master = None

    def connect(self):
        """Connect to an outstation, add an master to the channel, and start the communications."""

        # Root DNP3 object used to create channels and sessions
        if not self.manager:
            self.manager = asiodnp3.DNP3Manager(1, self.log_handler)

        # Connect via a TCPClient socket to a outstation
        self.channel = self.manager.AddTCPClient("tcpclient",
                                                 self.log_levels,
                                                 asiopal.ChannelRetry(),
                                                 self.host_ip,
                                                 self.local_ip,
                                                 self.port,
                                                 self.channel_listener)

        # Create a new master on a previously declared port, with a name, log level, command acceptor, and config info.
        # This returns a thread-safe interface used for sending commands.
        self.master = self.channel.AddMaster("master",
                                             self.soe_handler,
                                             self.master_application,
                                             self.stackConfig)

        # Enable the master. This will start communications.
        self.master.Enable()

    def reconnect(self, host_ip, port):
        """Reconnect master to a different host and port and start the communications."""
        if self.master:
            self.master.Disable()

        if self.channel:
            self.channel.Shutdown()

        self.host_ip = host_ip
        self.port = port
        self.connect()

    def send_direct_operate_command(self, command, index, callback=asiodnp3.PrintingCommandCallback.Get(),
                                    config=opendnp3.TaskConfig().Default()):
        """
            Direct operate a single command

        :param command: command to operate
        :param index: index of the command
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        self.master.DirectOperate(command, index, callback, config)

    def send_direct_operate_command_set(self, command_set, callback=asiodnp3.PrintingCommandCallback.Get(),
                                        config=opendnp3.TaskConfig().Default()):
        """
            Direct operate a set of commands

        :param command_set: set of command headers
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        self.master.DirectOperate(command_set, callback, config)

    def send_select_and_operate_command(self, command, index, callback=asiodnp3.PrintingCommandCallback.Get(),
                                        config=opendnp3.TaskConfig().Default()):
        """
            Select and operate a single command

        :param command: command to operate
        :param index: index of the command
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        self.master.SelectAndOperate(command, index, callback, config)

    def send_select_and_operate_command_set(self, command_set, callback=asiodnp3.PrintingCommandCallback.Get(),
                                            config=opendnp3.TaskConfig().Default()):
        """
            Select and operate a set of commands

        :param command_set: set of command headers
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        self.master.SelectAndOperate(command_set, callback, config)

    def shutdown(self):
        """
            Shutdown manager and terminate the threadpool
        """
        del self.master
        del self.channel
        if self.manager:
            self.manager.Shutdown()


class VisitorIndexedBinary(opendnp3.IVisitorIndexedBinary):
    """
        Override IVisitorIndexedBinary in this manner to implement visiting elements of IndexedBinary collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedBinary, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedBinary
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedDoubleBitBinary(opendnp3.IVisitorIndexedDoubleBitBinary):
    """
        Override IVisitorIndexedDoubleBitBinary in this manner to implement visiting elements of IndexedDoubleBitBinary
        collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedDoubleBitBinary, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedDoubleBitBinary
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedCounter(opendnp3.IVisitorIndexedCounter):
    """
        Override IVisitorIndexedCounter in this manner to implement visiting elements of IndexedCounter collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedCounter, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedCounter
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedFrozenCounter(opendnp3.IVisitorIndexedFrozenCounter):
    """
        Override IVisitorIndexedFrozenCounter in this manner to implement visiting elements of IndexedFrozenCounter
        collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedFrozenCounter, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedFrozenCounter
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedAnalog(opendnp3.IVisitorIndexedAnalog):
    """
        Override IVisitorIndexedAnalog in this manner to implement visiting elements of IndexedAnalog collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedAnalog, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedAnalog
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedBinaryOutputStatus(opendnp3.IVisitorIndexedBinaryOutputStatus):
    """
        Override IVisitorIndexedBinaryOutputStatus in this manner to implement visiting elements of
        IndexedBinaryOutputStatus collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedBinaryOutputStatus, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedBinaryOutputStatus
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedAnalogOutputStatus(opendnp3.IVisitorIndexedAnalogOutputStatus):
    """
        Override IVisitorIndexedAnalogOutputStatus in this manner to implement visiting elements of
        IndexedAnalogOutputStatus collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedAnalogOutputStatus, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedAnalogOutputStatus
        """
        self.index_and_value.append((indexed_instance.index, indexed_instance.value.value))


class VisitorIndexedTimeAndInterval(opendnp3.IVisitorIndexedTimeAndInterval):
    """
        Override IVisitorIndexedTimeAndInterval in this manner to implement visiting elements of
        IndexedTimeAndInterval collection.

        This is used in SOEHandler callback.
    """

    def __init__(self):
        super(VisitorIndexedTimeAndInterval, self).__init__()
        self.index_and_value = []

    def OnValue(self, indexed_instance):
        """
            Process current value visiting.

        :param indexed_instance: current value visiting, an instance of IndexedTimeAndInterval
        """
        # The TimeAndInterval class is a special case, because it doesn't have a "value" per se.
        ti_instance = indexed_instance.value
        ti_dnptime = ti_instance.time
        ti_interval = ti_instance.interval
        self.index_and_value.append((indexed_instance.index, (ti_dnptime.value, ti_interval)))


class LogHandler(openpal.ILogHandler):
    """
        Override ILogHandler in this manner to implement application-specific logging behavior.
    """

    def __init__(self):
        super(LogHandler, self).__init__()

    def Log(self, entry):
        flag = opendnp3.LogFlagToString(entry.filters.GetBitfield())
        filters = entry.filters.GetBitfield()
        location = entry.location.rsplit('/')[-1] if entry.location else ''
        message = entry.message
        _log.debug('LOG\t\t{:<10}\tfilters={:<5}\tlocation={:<25}\tentry={}'.format(flag, filters, location, message))


class ChannelListener(asiodnp3.IChannelListener):
    """
        Override IChannelListener in this manner to implement application-specific channel behavior.
    """

    def __init__(self):
        super(ChannelListener, self).__init__()

    def OnStateChange(self, state):
        _log.debug('In AppChannelListener.OnStateChange: state={}'.format(opendnp3.ChannelStateToString(state)))


class SOEHandler(opendnp3.ISOEHandler):
    """
        Override ISOEHandler in this manner to implement application-specific sequence-of-events behavior.

        This is an interface for SequenceOfEvents (SOE) callbacks from the Master stack to the application layer.
    """

    def __init__(self):
        super(SOEHandler, self).__init__()
        self.result = {
            "Binary": {},
            "DoubleBitBinary": {},
            "Counter": {},
            "FrozenCounter": {},
            "Analog": {},
            "BinaryOutputStatus": {},
            "AnalogOutputStatus": {},
            "TimeAndInterval": {}
        }

    def Process(self, info, values):
        """
            Process measurement data.

        :param info: HeaderInfo
        :param values: A collection of values received from the Outstation (various data types are possible).
        """
        visitor_class_types = {
            opendnp3.ICollectionIndexedBinary: VisitorIndexedBinary,
            opendnp3.ICollectionIndexedDoubleBitBinary: VisitorIndexedDoubleBitBinary,
            opendnp3.ICollectionIndexedCounter: VisitorIndexedCounter,
            opendnp3.ICollectionIndexedFrozenCounter: VisitorIndexedFrozenCounter,
            opendnp3.ICollectionIndexedAnalog: VisitorIndexedAnalog,
            opendnp3.ICollectionIndexedBinaryOutputStatus: VisitorIndexedBinaryOutputStatus,
            opendnp3.ICollectionIndexedAnalogOutputStatus: VisitorIndexedAnalogOutputStatus,
            opendnp3.ICollectionIndexedTimeAndInterval: VisitorIndexedTimeAndInterval
        }

        visitor_class = visitor_class_types[type(values)]
        visitor = visitor_class()

        # Visit all the elements of a collection
        values.Foreach(visitor)

        for index, value in visitor.index_and_value:
            self.result[type(values).__name__.split("ICollectionIndexed")[1]][index] = value

    def Start(self):
        pass

    def End(self):
        pass


class MasterApplication(opendnp3.IMasterApplication):
    def __init__(self):
        super(MasterApplication, self).__init__()

        # Overridden method
        def AssignClassDuringStartup(self):
            _log.debug('In MasterApplication.AssignClassDuringStartup')
            return False

        # Overridden method
        def OnClose(self):
            _log.debug('In MasterApplication.OnClose')

        # Overridden method
        def OnOpen(self):
            _log.debug('In MasterApplication.OnOpen')

        # Overridden method
        def OnReceiveIIN(self, iin):
            _log.debug('In MasterApplication.OnReceiveIIN')

        # Overridden method
        def OnTaskComplete(self, info):
            _log.debug('In MasterApplication.OnTaskComplete')

        # Overridden method
        def OnTaskStart(self, type, id):
            _log.debug('In MasterApplication.OnTaskStart')


def collection_callback(result=None):
    """
    :type result: opendnp3.CommandPointResult
    """
    print("Header: {0} | Index:  {1} | State:  {2} | Status: {3}".format(
        result.headerIndex,
        result.index,
        opendnp3.CommandPointStateToString(result.state),
        opendnp3.CommandStatusToString(result.status)
    ))


def command_callback(result=None):
    """
    :type result: opendnp3.ICommandTaskResult
    """
    print("Received command result with summary: {}".format(opendnp3.TaskCompletionToString(result.summary)))
    result.ForeachItem(collection_callback)


def restart_callback(result=opendnp3.RestartOperationResult()):
    if result:
        if result.summary == opendnp3.TaskCompletion.SUCCESS:
            status_message = "Success, Time: {0}".format(result.restartTime.GetMilliseconds())
        else:
            status_message = "Failure: {0}".format(opendnp3.TaskCompletionToString(result.summary))
    else:
        status_message = "Failure: No result returned"

    _log.debug(status_message)


def main():
    dnp3_master = DNP3Master(log_handler=LogHandler(),
                             channel_listener=ChannelListener(),
                             soe_handler=SOEHandler(),
                             master_application=MasterApplication())
    dnp3_master.connect()
    # Ad-hoc tests can be inserted here if desired.
    dnp3_master.shutdown()


if __name__ == '__main__':
    main()
