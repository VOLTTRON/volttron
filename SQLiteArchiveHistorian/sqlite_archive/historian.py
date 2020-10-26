"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from services.core.SQLHistorian.sqlhistorian.historian import historian, SQLHistorian
from SQLiteArchiveHistorian.sqlite_archive.sqlitefuncts_archiver import SQLiteArchiverFuncts
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

class MaskedString(str):
    def __repr__(self):
        return repr('********')


def sqlite_archive(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: SqliteArchive
    :rtype: SqliteArchive
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    connection = config.get('connection', None)
    assert connection is not None

    params = connection.get('params', None)
    assert params is not None

    # Avoid printing passwords in the debug message
    for key in ['pass', 'passwd', 'password', 'pw']:
        try:
            params[key] = MaskedString(params[key])
        except KeyError:
            pass

    utils.update_kwargs_with_config(kwargs, config)
    return SqliteArchiveHistorian(**kwargs)


class SqliteArchiveHistorian(SQLHistorian):
    """
    Document agent constructor here.
    """

    def __init__(self, connection, tables_def=None, archive_period="", **kwargs):
        self.connection = connection
        self.tables_def, self.table_names = self.parse_table_def(tables_def)
        self.archive_period_units = archive_period[-1:]
        self.archive_period = int(archive_period[:-1])
        # Create two instance so connection is shared within a single thread.
        # This is because sqlite only supports sharing of connection within
        # a single thread.
        # historian_setup and publish_to_historian happens in background thread
        # everything else happens in the MainThread

        # One utils class instance( hence one db connection) for main thread
        self.main_thread_dbutils = SQLiteArchiverFuncts(self.connection['params'], self.table_names)
        # One utils class instance( hence one db connection) for main thread
        # this gets initialized in the bg_thread within historian_setup
        self.bg_thread_dbutils = None
        super(SQLHistorian, self).__init__(**kwargs)

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. If a configuration exists at startup
        this will be called before onstart.

        Is called every time the configuration in the store changes.
        """
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")

        try:
            setting1 = int(config["setting1"])
            setting2 = str(config["setting2"])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        self.setting1 = setting1
        self.setting2 = setting2

        self._create_subscriptions(self.setting2)

    def _create_subscriptions(self, topic):
        #Unsubscribe from everything.
        self.vip.pubsub.unsubscribe("pubsub", None, None)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self._handle_publish)

    def _handle_publish(self, peer, sender, bus, topic, headers,
                                message):
        pass

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        This is method is called once the Agent has successfully connected to the platform.
        This is a good place to setup subscriptions if they are not dynamic or
        do any other startup activities that require a connection to the message bus.
        Called after any configurations methods that are called at startup.

        Usually not needed if using the configuration store.
        """
        #Example publish to pubsub
        #self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")

        #Exmaple RPC call
        #self.vip.rpc.call("some_agent", "some_method", arg1, arg2)

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        pass

    @RPC.export
    def rpc_method(self, arg1, arg2, kwarg1=None, kwarg2=None):
        """
        RPC method

        May be called from another agent via self.core.rpc.call """
        return self.setting1 + arg1 - arg2

def main():
    """Main method called to start the agent."""
    utils.vip_main(sqlite_archive, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
