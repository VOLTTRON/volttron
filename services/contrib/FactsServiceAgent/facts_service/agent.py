"""
Ecorithm Facts Service Agent

This agent sends collected data to Ecorithm's Facts Service API using HTTPS
requests.

Each request must be authenticated using an username/password pair provided
by Ecorithm. Authentication is configured in the Facts Service parameters
group of the config.

If the Building Automation System (BAS) being trended belong to a unique
building, the `building_id` parameter must be set to match the building number
provided by Ecorithm. Topic to building_id mapping must be empty (`{}`).

If the BAS trends multiple buildings or a campus, the `building_id` must be
set to `null` and the `topic_building_mapping` must be filled.

Note that this agent won't be able to read data stored on Facts Service such
as the SQLHistorian would be able to. It is only unidirectional.

Author: Thibaud Nesztler
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import requests
import pytz
import sqlite3
from tzlocal import get_localzone
from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = '1.3.2'


def historian(config_path, **kwargs):
    """
    Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: `FactsService`
    :rtype: `FactsService`
    """

    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    # Gather all settings from configuration into kwargs.
    # This ensures that settings common to all historians
    # are passed to BaseHistorian.
    utils.update_kwargs_with_config(kwargs, config_dict)
    return FactsService(**kwargs)


class FactsService(BaseHistorian):
    """
    Sends trend data to Ecorithm's Facts Service using HTTP PUT requests.
    """

    def __init__(self, facts_service_parameters={}, building_parameters={},
                 **kwargs):
        # The publish_to_historian function will run in a
        # separate thread unless you change this to True.
        # Unless you need to interact with the VOLTTRON platform
        # leave this unchanged.
        kwargs["process_loop_in_greenlet"] = False
        super(FactsService, self).__init__(**kwargs)

        self._facts_service_base_api_url = None
        self._facts_service_username = None
        self._facts_service_password = None
        self._building_id = None
        self._topic_building_mapping = None
        self._db_path = None
        self._db_connection = None
        self._db_is_alive = False

        # The base historian handles the interaction with the
        # configuration store.
        config = {
            "facts_service_parameters": facts_service_parameters,
            "building_parameters": building_parameters
        }
        # Add our settings to the base historians default settings.
        self.update_default_config(config)

    def configure(self, configuration):
        # The base historian will call this whenever the
        # Historian is reconfigured in the main process thread.

        # If the Historian is already running historian_teardown
        # will be called before this is called and
        # historian_setup will be called afterwards.

        facts_service_parameters = configuration["facts_service_parameters"]
        building_parameters = configuration["building_parameters"]

        if not isinstance(facts_service_parameters, dict):
            _log.warning(
                "Supplied facts_service_parameters is not a dict, ignored"
            )
            facts_service_parameters = {}

        if not isinstance(building_parameters, dict):
            _log.warning("Supplied building_parameters is not a dict, ignored")
            building_parameters = {}

        self._facts_service_base_api_url = \
            facts_service_parameters.get("base_api_url")
        self._facts_service_username = facts_service_parameters.get("username")
        self._facts_service_password = facts_service_parameters.get("password")
        self._db_path = facts_service_parameters.get(
            "unmapped_topics_database", "unmapped_topics.db"
        )
        self._building_id = building_parameters.get("building_id")
        self._topic_building_mapping = building_parameters.get(
            "topic_building_mapping", {}
        )

        if self._building_id is not None and self._topic_building_mapping:
            _log.warning(
                "Building ID is {}, topic to building_id mapping is ignored"
                .format(self._building_id)
            )
            self._topic_building_mapping = {}

        if self._building_id is None and not self._topic_building_mapping:
            _log.warning(
                "Topic to building ID mapping is empty."
                " Nothing will be published. Check your configuration!"
            )

    def publish_to_historian(self, to_publish_list):
        # Called automatically by the BaseHistorian class when data is
        # available to be published.

        # This is run in a separate thread from the main agent thread.
        # This means that this function may block for a short period of time
        # without fear of blocking the main agent gevent loop.

        # Historians may not interact with the VOLTTRON platform directly from
        # this function unless kwargs["process_loop_in_greenlet"] is set to
        # True in __init__ which will cause this function to be run in the
        # main Agent thread.

        # to_publish_list is a list of dictionaries of the form:
        # {'timestamp': <datetime object>,
        #  'source': <"scrape", "record", "log", or "analysis">,
        # "scrape" is device data
        #  'topic': <str>,
        #  'value': <value>, # may be any JSON value.
        #  'headers': <headers dictionary>,
        #  'meta': <meta data dictionary>}

        _log.debug("Number of items to publish: {}"
                   .format(len(to_publish_list)))

        if not self._db_is_alive:
            self.historian_setup()

        # If our connection is down leave without attempting to publish.
        # Publish failure will automatically trigger the BaseHistorian to
        # set the health of the agent accordingly.
        if self._db_connection is None:
            return

        to_send = {}
        to_report_as_handled = {}
        local_tz = get_localzone()
        unmapped_topics = []
        for x in to_publish_list:
            ts_datetime = x["timestamp"].replace(tzinfo=pytz.utc)\
                .astimezone(local_tz)
            ts = ts_datetime.strftime("%Y-%m-%d %H:%M")
            topic = x["topic"]
            value = x["value"]
            if self._building_id is None \
                    and topic not in self._topic_building_mapping:
                unmapped_topics.append({
                    "topic": topic,
                    "ts": ts_datetime.replace(tzinfo=None).isoformat()
                })
                self.report_handled(x)
            else:
                if isinstance(value, bool):
                    value = int(value)
                building_id = self._topic_building_mapping.get(topic) \
                    if self._building_id is None else self._building_id
                if building_id is not None:
                    data = {
                        'fact_time': ts,
                        'native_name': topic,
                        'fact_value': value
                    }
                    to_send[building_id] = to_send[building_id] + [data] \
                        if building_id in to_send else [data]
                    to_report_as_handled[building_id] = \
                        to_report_as_handled[building_id] + [x] \
                        if building_id in to_report_as_handled else [x]

        _log.debug('Sending data to Facts Service')
        for building_id, data in to_send.items():
            try:
                requests.put(
                    '{}/building/{}/facts'
                    .format(self._facts_service_base_api_url, building_id),
                    json=data,
                    auth=(
                        self._facts_service_username,
                        self._facts_service_password
                    )
                ).raise_for_status()
                self.report_handled(to_report_as_handled[building_id])
                _log.debug('Data successfully published to building {}!'
                           .format(building_id))
            except requests.exceptions.RequestException as e:
                _log.error('Error when attempting to publish to target: {}'
                           .format(repr(e)))

        if unmapped_topics:
            try:
                _log.debug('Saving {} unmapped topics to the database'
                           .format(len(unmapped_topics)))
                with self._db_connection:
                    self._db_connection.executemany(
                        "INSERT OR REPLACE INTO "
                        "unmapped_topics(topic, created_at, updated_at) "
                        "VALUES (:topic, COALESCE((SELECT created_at FROM "
                        "unmapped_topics WHERE topic = :topic), :ts), :ts);",
                        unmapped_topics
                    )
            except sqlite3.Error as e:
                _log.error('Error when saving unmapped topics: {}'
                           .format(repr(e)))

    def manage_db_size(self, history_limit_timestamp, storage_limit_gb):
        """
        Called in the process thread after data is published.
        Implement this to apply the storage_limit_gb and history_limit_days
        settings to the storage medium.

        Typically only support for history_limit_timestamp will be implemented.
        The documentation should note which of the two settings (if any)
        are supported.

        :param history_limit_timestamp:
            remove all data older than this timestamp
        :param storage_limit_gb:
            remove oldest data until database is smaller than this value.
        """
        pass

    def version(self):
        """
        Return the current version number of the historian
        :return: version number
        """
        return __version__

    def historian_setup(self):
        # Setup any connection needed for this historian.
        # This is called from the same thread as publish_to_historian.

        # It is called after configure is called at startup
        # and every time the Historian is reconfigured.

        # If the connection is lost it is up to the Historian to
        # recreate it if needed, often by calling this function to
        # restore connectivity.

        # This is a convenience to allow us to call this any time we like to
        # restore a connection.
        _log.info("Setting up unmapped topics database connection")
        self.historian_teardown()
        try:
            self._db_connection = sqlite3.connect(self._db_path)
            with self._db_connection:
                self._db_connection.execute(
                    "CREATE TABLE IF NOT EXISTS unmapped_topics ("
                    "topic TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT)"
                )
            self._db_is_alive = True
        except Exception as e:
            _log.error("Failed to create database connection: {}"
                       .format(repr(e)))

    def historian_teardown(self):
        # Kill the connection if needed.
        # This is called to shut down the connection before reconfiguration.
        if self._db_connection is not None:
            self._db_connection.close()
            self._db_connection = None
            self._db_is_alive = False

    # The following methods are for adding query support. This will allow other
    # agents to get data from the store and will allow this historian to act as
    # the platform.historian for VOLTTRON.

    def query_topic_list(self):
        """
        This function is called by
        :py:meth:`BaseQueryHistorianAgent.get_topic_list`
        to get the topic list from the data store.

        :return: List of topics in the data store.
        :rtype: list
        """
        raise NotImplementedError()

    def query_topics_metadata(self, topics):
        """
        This function is called by
        :py:meth:`BaseQueryHistorianAgent.get_topics_metadata`
        to find out the metadata for the given topics

        :param topics: single topic or list of topics
        :type topics: str or list
        :return: dictionary with the format

        .. code-block:: python

                 {topic_name: {metadata_key:metadata_value, ...},
                 topic_name: {metadata_key:metadata_value, ...} ...}

        :rtype: dict

        """
        raise NotImplementedError()

    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None, order=None):
        """
        This function is called by :py:meth:`BaseQueryHistorianAgent.query`
        to actually query the data store and must return the results of a
        query in the following format:

        **Single topic query:**

        .. code-block:: python

            {
            "values": [(timestamp1, value1),
                        (timestamp2:,value2),
                        ...],
             "metadata": {"key1": value1,
                          "key2": value2,
                          ...}
            }

        **Multiple topics query:**

        .. code-block:: python

            {
            "values": {topic_name:[(timestamp1, value1),
                        (timestamp2:,value2),
                        ...],
                       topic_name:[(timestamp1, value1),
                        (timestamp2:,value2),
                        ...],
                        ...}
             "metadata": {} #empty metadata
            }

        Timestamps must be strings formatted by
        :py:func:`volttron.platform.agent.utils.format_timestamp`.

        "metadata" is not required. The caller will normalize this to {} for
        you if it is missing.

        :param topic: Topic or list of topics to query for.
        :param start: Start of query timestamp as a datetime.
        :param end: End of query timestamp as a datetime.
        :param agg_type: If this is a query for aggregate data, the type of
                         aggregation ( for example, sum, avg)
        :param agg_period: If this is a query for aggregate data, the time
                           period of aggregation
        :param skip: Skip this number of results.
        :param count: Limit results to this value. When the query is for
                      multiple topics, count applies to individual topics. For
                      example, a query on 2 topics with count=5 will return 5
                      records for each topic
        :param order: How to order the results, either "FIRST_TO_LAST" or
                      "LAST_TO_FIRST"
        :type topic: str or list
        :type start: datetime
        :type end: datetime
        :type skip: int
        :type count: int
        :type order: str

        :return: Results of the query
        :rtype: dict

        """
        raise NotImplementedError()

    def query_aggregate_topics(self):
        """
        This function is called by
        :py:meth:`BaseQueryHistorianAgent.get_aggregate_topics`
        to find out the available aggregates in the data store

        :return: List of tuples containing (topic_name, aggregation_type,
                 aggregation_time_period, metadata)
        :rtype: list

        """
        raise NotImplementedError()

    def query_topics_by_pattern(self, topic_pattern):
        """ Find the list of topics and its id for a given topic_pattern

            :return: returns list of dictionary object {topic_name:id}"""
        raise NotImplementedError()


def main():
    """Main method called to start the agent."""
    utils.vip_main(historian, identity="facts_service",
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
