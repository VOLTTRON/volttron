import datetime as dt
import logging
import mock
import os
import pytest
import pytz
import requests
import sqlite3
from facts_service.agent import historian
from facts_service.agent import FactsService
from facts_service.agent import __version__


@pytest.mark.ecorithm
class TestHistorian:

    def test_config_path_is_dict(self):
        # arrange
        config = {
            "facts-service-parameters": {},
            "building-parameters": {"building_id": 42},
            "submit_size_limit": 500
        }
        # act
        object = historian(config)
        # assert
        assert isinstance(object, FactsService)
        assert hasattr(object, '_facts_service_base_api_url')
        assert hasattr(object, '_facts_service_username')
        assert hasattr(object, '_facts_service_password')
        assert hasattr(object, '_building_id')
        assert hasattr(object, '_topic_building_mapping')
        assert hasattr(object, '_db_path')
        assert hasattr(object, '_db_connection')
        assert hasattr(object, '_db_is_alive')
        assert object._default_config.get('building_parameters')\
            .get('building_id') == 42
        assert object._default_config.get('facts_service_parameters') == dict()
        assert object._default_config.get('submit_size_limit') == 500

    def test_config_path_is_path(self):
        # arrange
        config = os.path.join(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.pardir)
            ), 'config'
        )
        # act
        object = historian(config)
        # assert
        assert isinstance(object, FactsService)
        assert hasattr(object, '_facts_service_base_api_url')
        assert hasattr(object, '_facts_service_username')
        assert hasattr(object, '_facts_service_password')
        assert hasattr(object, '_building_id')
        assert hasattr(object, '_topic_building_mapping')
        assert hasattr(object, '_db_path')
        assert hasattr(object, '_db_connection')
        assert hasattr(object, '_db_is_alive')
        assert object._default_config.get('facts_service_parameters')\
            .get('base_api_url') == 'https://facts.prod.ecorithm.com/api/v1'
        assert object._default_config.get('capture_analysis_data') is False


@pytest.mark.ecorithm
class TestFactsServiceInit:

    def test_with_args(self):
        # arrange
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "",
            "password": "",
            "unmapped_topics_database": "trends.db"
        }
        building_parameters = {
            "building_id": None,
            "topic_building_mapping": {}
        }
        kwargs = {"submit_size_limit": 500}
        # act
        object = FactsService(
            facts_service_parameters,
            building_parameters,
            **kwargs
        )
        # assert
        assert hasattr(object, '_facts_service_base_api_url')
        assert hasattr(object, '_facts_service_username')
        assert hasattr(object, '_facts_service_password')
        assert hasattr(object, '_building_id')
        assert hasattr(object, '_topic_building_mapping')
        assert hasattr(object, '_db_path')
        assert hasattr(object, '_db_connection')
        assert hasattr(object, '_db_is_alive')
        assert object._default_config.get('facts_service_parameters')\
            == facts_service_parameters
        assert object._default_config.get('building_parameters')\
            == building_parameters
        assert object._default_config.get('submit_size_limit') == 500
        assert object._process_loop_in_greenlet is False

    def test_with_defaults(self):
        # arrange
        # act
        object = FactsService()
        # assert
        assert hasattr(object, '_facts_service_base_api_url')
        assert hasattr(object, '_facts_service_username')
        assert hasattr(object, '_facts_service_password')
        assert hasattr(object, '_building_id')
        assert hasattr(object, '_topic_building_mapping')
        assert hasattr(object, '_db_path')
        assert hasattr(object, '_db_connection')
        assert hasattr(object, '_db_is_alive')
        assert object._default_config.get('facts_service_parameters') == dict()
        assert object._default_config.get('building_parameters') == dict()
        assert object._default_config.get('submit_size_limit') == 1000
        assert object._process_loop_in_greenlet is False


@pytest.mark.ecorithm
class TestFactsServiceConfigure:

    def test_facts_service_parameters_not_dict(self, caplog):
        # arrange
        facts_service_parameters = None
        building_parameters = {
            "building_id": 42,
            "topic_building_mapping": {}
        }
        object = FactsService(facts_service_parameters, building_parameters)
        caplog.clear()
        # act
        object.configure(object._default_config)
        # assert
        assert len(caplog.records) == 1
        assert (
            'facts_service.agent', logging.WARNING,
            'Supplied facts_service_parameters is not a dict, ignored'
        ) in caplog.record_tuples
        assert object._facts_service_base_api_url is None
        assert object._facts_service_username is None
        assert object._facts_service_password is None
        assert object._db_path == "unmapped_topics.db"
        assert object._building_id is 42
        assert object._topic_building_mapping == dict()

    def test_building_parameters_not_dict(self, caplog):
        # arrange
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "trends.db"
        }
        building_parameters = None
        object = FactsService(facts_service_parameters, building_parameters)
        caplog.clear()
        # act
        object.configure(object._default_config)
        # assert
        assert len(caplog.records) == 2
        assert (
            'facts_service.agent', logging.WARNING,
            'Supplied building_parameters is not a dict, ignored'
        ) in caplog.record_tuples
        assert (
            'facts_service.agent', logging.WARNING,
            'Topic to building ID mapping is empty. Nothing will be published.'
            ' Check your configuration!'
        ) in caplog.record_tuples
        assert object._facts_service_base_api_url\
            == 'https://facts.prod.ecorithm.com/api/v1'
        assert object._facts_service_username == 'foo'
        assert object._facts_service_password == 'bar'
        assert object._db_path == 'trends.db'
        assert object._building_id is None
        assert object._topic_building_mapping == dict()

    def test_ignored_topic_building_mapping(self, caplog):
        # arrange
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "unmapped_topics.db"
        }
        building_parameters = {
            "building_id": 42,
            "topic_building_mapping": {
                "campus/fake_device_#1/fake_point": 42,
                "campus/fake_device_#2/fake_point": 1337
            }
        }
        object = FactsService(facts_service_parameters, building_parameters)
        # act
        caplog.clear()
        object.configure(object._default_config)
        # assert
        assert len(caplog.records) == 1
        assert (
            'facts_service.agent', logging.WARNING,
            'Building ID is 42, topic to building_id mapping is ignored'
        ) in caplog.record_tuples
        assert object._facts_service_base_api_url\
            == 'https://facts.prod.ecorithm.com/api/v1'
        assert object._facts_service_username == 'foo'
        assert object._facts_service_password == 'bar'
        assert object._db_path == 'unmapped_topics.db'
        assert object._building_id is 42
        assert object._topic_building_mapping == dict()

    def test_invalid_configuration(self, caplog):
        # arrange
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "unmapped_topics.db"
        }
        building_parameters = {
            "building_id": None,
            "topic_building_mapping": {}
        }
        object = FactsService(facts_service_parameters, building_parameters)
        caplog.clear()
        # act
        object.configure(object._default_config)
        # assert
        assert len(caplog.records) == 1
        assert (
            'facts_service.agent', logging.WARNING,
            'Topic to building ID mapping is empty. Nothing will be published.'
            ' Check your configuration!'
        ) in caplog.record_tuples
        assert object._facts_service_base_api_url\
            == 'https://facts.prod.ecorithm.com/api/v1'
        assert object._facts_service_username == 'foo'
        assert object._facts_service_password == 'bar'
        assert object._db_path == 'unmapped_topics.db'
        assert object._building_id is None
        assert object._topic_building_mapping == dict()

    def test_valid_configuration(self, caplog):
        # arrange
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "unmapped_topics.db"
        }
        building_parameters = {
            "building_id": 42,
            "topic_building_mapping": {}
        }
        object = FactsService(facts_service_parameters, building_parameters)
        caplog.clear()
        # act
        object.configure(object._default_config)
        # assert
        assert len(caplog.records) == 0
        assert object._facts_service_base_api_url\
            == 'https://facts.prod.ecorithm.com/api/v1'
        assert object._facts_service_username == 'foo'
        assert object._facts_service_password == 'bar'
        assert object._db_path == 'unmapped_topics.db'
        assert object._building_id is 42
        assert object._topic_building_mapping == dict()


@pytest.mark.ecorithm
class TestFactsServicePublishToHistorian:

    @pytest.fixture
    def agent_bldg(self):
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "unmapped_topics.db"
        }
        building_parameters = {
            "building_id": 42,
            "topic_building_mapping": {}
        }
        agent = FactsService(facts_service_parameters, building_parameters)
        agent.configure(agent._default_config)
        return agent

    @pytest.fixture
    def agent_campus(self):
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "unmapped_topics.db"
        }
        building_parameters = {
            "building_id": None,
            "topic_building_mapping": {
                "campus/building_A/fake_device/point_1": 42,
                "campus/building_A/fake_device/point_2": 42,
                "campus/building_B/fake_device/point": 1337
            }
        }
        agent = FactsService(facts_service_parameters, building_parameters)
        agent.configure(agent._default_config)
        return agent

    @pytest.fixture
    def agent_campus_with_missing_topics(self):
        facts_service_parameters = {
            "base_api_url": "https://facts.prod.ecorithm.com/api/v1",
            "username": "foo",
            "password": "bar",
            "unmapped_topics_database": "unmapped_topics.db"
        }
        building_parameters = {
            "building_id": None,
            "topic_building_mapping": {
                "campus/building_A/fake_device/point_1": 42,
                "campus/building_A/fake_device/point_2": 42
            }
        }
        agent = FactsService(facts_service_parameters, building_parameters)
        agent.configure(agent._default_config)
        return agent

    def test_db_doesnt_exists(self, caplog, agent_bldg):
        # arrange
        caplog.clear()
        publish_list = []
        # act
        agent_bldg.publish_to_historian(publish_list)
        # assert
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.DEBUG,
             'Number of items to publish: 0'),
            ('facts_service.agent', logging.INFO,
             'Setting up unmapped topics database connection'),
            ('facts_service.agent', logging.DEBUG,
             'Sending data to Facts Service')
        ]
        assert agent_bldg._db_is_alive
        rows = agent_bldg._db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='unmapped_topics';"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 'unmapped_topics'

    def test_db_connection_failed(self, caplog, agent_bldg):
        # arrange
        agent_bldg.historian_setup()
        caplog.clear()
        publish_list = []
        agent_bldg._db_connection = None
        # act
        agent_bldg.publish_to_historian(publish_list)
        # assert
        assert caplog.record_tuples == [(
            'facts_service.agent', logging.DEBUG,
            'Number of items to publish: 0'
        )]
        assert agent_bldg._db_is_alive
        assert agent_bldg._db_connection is None

    def test_publish_one_building(self, caplog, agent_bldg):
        # arrange
        agent_bldg.historian_setup()
        caplog.clear()
        mock_requests = mock.patch('requests.put')
        mock_timezone = mock.patch(
            'facts_service.agent.get_localzone', return_value=pytz.utc
        )
        publish_list = [{
            '_id': 1,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building/fake_device/point_A',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 2,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building/fake_device/point_B',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 3,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 43),
            'source': "scrape",
            'topic': 'campus/building/fake_device/point_C',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        mock_requests.start()
        mock_timezone.start()
        # act
        agent_bldg.publish_to_historian(publish_list)
        # assert
        mock_timezone.stop()
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.DEBUG,
             'Number of items to publish: 3'),
            ('facts_service.agent', logging.DEBUG,
             'Sending data to Facts Service'),
            ('facts_service.agent', logging.DEBUG,
             'Data successfully published to building 42!')
        ]
        requests.put.assert_called_once_with(
            'https://facts.prod.ecorithm.com/api/v1/building/42/facts',
            json=[{
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building/fake_device/point_A',
                'fact_value': 24.32
            }, {
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building/fake_device/point_B',
                'fact_value': 1
            }, {
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building/fake_device/point_C',
                'fact_value': 1.0
            }],
            auth=('foo', 'bar')
        )
        mock_requests.stop()
        assert agent_bldg._successful_published == set([1, 2, 3])

    def test_publish_multiple_buildings(self, caplog, agent_campus):
        # arrange
        agent_campus.historian_setup()
        caplog.clear()
        mock_requests = mock.patch('requests.put')
        mock_timezone = mock.patch(
            'facts_service.agent.get_localzone', return_value=pytz.utc
        )
        publish_list = [{
            '_id': 1,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_1',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 2,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_2',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 3,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 43),
            'source': "scrape",
            'topic': 'campus/building_B/fake_device/point',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        mock_requests.start()
        mock_timezone.start()
        # act
        agent_campus.publish_to_historian(publish_list)
        # assert
        mock_timezone.stop()
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.DEBUG,
             'Number of items to publish: 3'),
            ('facts_service.agent', logging.DEBUG,
             'Sending data to Facts Service'),
            ('facts_service.agent', logging.DEBUG,
             'Data successfully published to building 1337!'),
            ('facts_service.agent', logging.DEBUG,
             'Data successfully published to building 42!')
        ]
        requests.put.assert_any_call(
            'https://facts.prod.ecorithm.com/api/v1/building/42/facts',
            json=[{
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_A/fake_device/point_1',
                'fact_value': 24.32
            }, {
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_A/fake_device/point_2',
                'fact_value': 1
            }],
            auth=('foo', 'bar')
        )
        requests.put.assert_any_call(
            'https://facts.prod.ecorithm.com/api/v1/building/1337/facts',
            json=[{
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_B/fake_device/point',
                'fact_value': 1.0
            }],
            auth=('foo', 'bar')
        )
        mock_requests.stop()
        assert agent_campus._successful_published == set([1, 2, 3])

    def test_missing_topics(self, caplog, agent_campus_with_missing_topics):
        # arrange
        agent_campus_with_missing_topics.historian_setup()
        caplog.clear()
        mock_requests = mock.patch('requests.put')
        mock_timezone = mock.patch(
            'facts_service.agent.get_localzone', return_value=pytz.utc
        )
        publish_list = [{
            '_id': 1,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_1',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 2,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_2',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 3,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 43),
            'source': "scrape",
            'topic': 'campus/building_B/fake_device/point',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        mock_requests.start()
        mock_timezone.start()
        # act
        agent_campus_with_missing_topics.publish_to_historian(publish_list)
        # assert
        mock_timezone.stop()
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.DEBUG,
             'Number of items to publish: 3'),
            ('facts_service.agent', logging.DEBUG,
             'Sending data to Facts Service'),
            ('facts_service.agent', logging.DEBUG,
             'Data successfully published to building 42!'),
            ('facts_service.agent', logging.DEBUG,
             'Saving 1 unmapped topics to the database')
        ]
        requests.put.assert_any_call(
            'https://facts.prod.ecorithm.com/api/v1/building/42/facts',
            json=[{
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_A/fake_device/point_1',
                'fact_value': 24.32
            }, {
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_A/fake_device/point_2',
                'fact_value': 1
            }],
            auth=('foo', 'bar')
        )
        mock_requests.stop()
        assert agent_campus_with_missing_topics._successful_published \
            == set([1, 2, 3])
        rows = agent_campus_with_missing_topics._db_connection.execute(
            "SELECT * FROM unmapped_topics"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0] == (
            'campus/building_B/fake_device/point',
            '2018-09-10T18:20:43', '2018-09-10T18:20:43'
        )

    def test_missing_topics_updated(
            self, caplog, agent_campus_with_missing_topics):
        # arrange
        agent_campus_with_missing_topics.historian_setup()
        caplog.clear()
        mock_requests = mock.patch('requests.put')
        mock_timezone = mock.patch(
            'facts_service.agent.get_localzone', return_value=pytz.utc
        )
        publish_list_1 = [{
            '_id': 1,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_1',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 2,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_2',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 3,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 43),
            'source': "scrape",
            'topic': 'campus/building_B/fake_device/point',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        publish_list_2 = [{
            '_id': 4,
            'timestamp': dt.datetime(2018, 9, 10, 18, 25, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_1',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 5,
            'timestamp': dt.datetime(2018, 9, 10, 18, 25, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_2',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 6,
            'timestamp': dt.datetime(2018, 9, 10, 18, 25, 43),
            'source': "scrape",
            'topic': 'campus/building_B/fake_device/point',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        mock_requests.start()
        mock_timezone.start()
        # act
        agent_campus_with_missing_topics.publish_to_historian(publish_list_1)
        agent_campus_with_missing_topics.publish_to_historian(publish_list_2)
        # assert
        mock_timezone.stop()
        mock_requests.stop()
        assert agent_campus_with_missing_topics._successful_published \
            == set([1, 2, 3, 4, 5, 6])
        rows = agent_campus_with_missing_topics._db_connection.execute(
            "SELECT * FROM unmapped_topics"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0] == (
            'campus/building_B/fake_device/point',
            '2018-09-10T18:20:43', '2018-09-10T18:25:43'
        )

    def test_error_during_saving_unmapped_topics(
            self, caplog, agent_campus_with_missing_topics):
        # arrange
        agent_campus_with_missing_topics.historian_setup()
        caplog.clear()
        mock_requests = mock.patch('requests.put')
        mock_timezone = mock.patch(
            'facts_service.agent.get_localzone', return_value=pytz.utc
        )
        publish_list = [{
            '_id': 1,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_1',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 2,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_2',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 3,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 43),
            'source': "scrape",
            'topic': 'campus/building_B/fake_device/point',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        mock_requests.start()
        mock_timezone.start()
        agent_campus_with_missing_topics._db_connection = \
            sqlite3.connect(':memory:')
        # act
        agent_campus_with_missing_topics.publish_to_historian(publish_list)
        # assert
        mock_timezone.stop()
        mock_requests.stop()
        assert agent_campus_with_missing_topics._successful_published \
            == set([1, 2, 3])
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.DEBUG,
             'Number of items to publish: 3'),
            ('facts_service.agent', logging.DEBUG,
             'Sending data to Facts Service'),
            ('facts_service.agent', logging.DEBUG,
             'Data successfully published to building 42!'),
            ('facts_service.agent', logging.DEBUG,
             'Saving 1 unmapped topics to the database'),
            ('facts_service.agent', logging.ERROR,
             "Error when saving unmapped topics: "
             "OperationalError('no such table: unmapped_topics',)"),
        ]

    def test_error_during_publishing_to_facts(self, caplog, agent_campus):
        # arrange
        agent_campus.historian_setup()
        caplog.clear()
        mock_requests = mock.patch(
            'requests.put',
            side_effect=[mock.MagicMock(), requests.exceptions.ConnectTimeout]
        )
        mock_timezone = mock.patch(
            'facts_service.agent.get_localzone', return_value=pytz.utc
        )
        publish_list = [{
            '_id': 1,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_1',
            'value': 24.32,
            'headers': {},
            'meta': {}
        }, {
            '_id': 2,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 42),
            'source': 'scrape',
            'topic': 'campus/building_A/fake_device/point_2',
            'value': True,
            'headers': {},
            'meta': {}
        }, {
            '_id': 3,
            'timestamp': dt.datetime(2018, 9, 10, 18, 20, 43),
            'source': 'scrape',
            'topic': 'campus/building_B/fake_device/point',
            'value': 1.0,
            'headers': {},
            'meta': {}
        }]
        mock_requests.start()
        mock_timezone.start()
        # act
        agent_campus.publish_to_historian(publish_list)
        # assert
        mock_timezone.stop()
        requests.put.assert_any_call(
            'https://facts.prod.ecorithm.com/api/v1/building/42/facts',
            json=[{
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_A/fake_device/point_1',
                'fact_value': 24.32
            }, {
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_A/fake_device/point_2',
                'fact_value': 1
            }],
            auth=('foo', 'bar')
        )
        requests.put.assert_any_call(
            'https://facts.prod.ecorithm.com/api/v1/building/1337/facts',
            json=[{
                'fact_time': '2018-09-10 18:20',
                'native_name': 'campus/building_B/fake_device/point',
                'fact_value': 1.0
            }],
            auth=('foo', 'bar')
        )
        mock_requests.stop()
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.DEBUG,
             'Number of items to publish: 3'),
            ('facts_service.agent', logging.DEBUG,
             'Sending data to Facts Service'),
            ('facts_service.agent', logging.DEBUG,
             'Data successfully published to building 1337!'),
            ('facts_service.agent', logging.ERROR,
             'Error when attempting to publish to target: ConnectTimeout()')
        ]
        assert agent_campus._successful_published == set([3])


@pytest.mark.ecorithm
class TestFactsServiceManageDBSize:

    def test_pass(self):
        # arrange
        # act
        FactsService().manage_db_size(None, None)
        # assert


@pytest.mark.ecorithm
class TestFactsServiceVersion:

    def test_version(self):
        # arrange
        # act
        version = FactsService().version()
        # assert
        assert version == __version__


@pytest.mark.ecorithm
class TestFactsServiceHistorianSetup:

    def test_valid_setup(self, caplog):
        # arrange
        agent = FactsService()
        agent.configure(agent._default_config)
        caplog.clear()
        # act
        agent.historian_setup()
        # assert
        assert isinstance(agent._db_connection, sqlite3.Connection)
        assert agent._db_is_alive is True
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.INFO,
             'Setting up unmapped topics database connection')
        ]

    def test_error_during_setup(self, caplog):
        # arrange
        agent = FactsService()
        agent.configure(agent._default_config)
        caplog.clear()
        mock_db = mock.patch(
            'facts_service.agent.sqlite3.connect',
            side_effect=sqlite3.DatabaseError
        )
        mock_db.start()
        # act
        agent.historian_setup()
        # assert
        mock_db.stop()
        assert caplog.record_tuples == [
            ('facts_service.agent', logging.INFO,
             'Setting up unmapped topics database connection'),
            ('facts_service.agent', logging.ERROR,
             'Failed to create database connection: DatabaseError()')
        ]


@pytest.mark.ecorithm
class TestFactsServiceHistorianTeardown:

    def test_no_connection(self):
        # arrange
        agent = FactsService()
        agent.configure(agent._default_config)
        # act
        agent.historian_teardown()
        # assert
        assert agent._db_connection is None
        assert agent._db_is_alive is False

    def test_with_existing_connection(self):
        # arrange
        agent = FactsService()
        agent.configure(agent._default_config)
        agent.historian_setup()
        # act
        agent.historian_teardown()
        # assert
        assert agent._db_connection is None
        assert agent._db_is_alive is False


@pytest.mark.ecorithm
class TestFactsServiceNotImplemented:

    def test_query_topic_list(self):
        # arrange
        agent = FactsService()
        # act
        with pytest.raises(NotImplementedError):
            agent.query_topic_list()
        # assert

    def test_query_topics_metadata(self):
        # arrange
        agent = FactsService()
        # act
        with pytest.raises(NotImplementedError):
            agent.query_topics_metadata('campus/building/fake_device/point')
        # assert

    def test_query_historian(self):
        # arrange
        agent = FactsService()
        # act
        with pytest.raises(NotImplementedError):
            agent.query_historian('campus/building/fake_device/point')
        # assert

    def test_query_aggregate_topics(self):
        # arrange
        agent = FactsService()
        # act
        with pytest.raises(NotImplementedError):
            agent.query_aggregate_topics()
        # assert

    def test_query_topics_by_pattern(self):
        # arrange
        agent = FactsService()
        # act
        with pytest.raises(NotImplementedError):
            agent.query_topics_by_pattern('campus/building/fake_device.*')
        # assert
