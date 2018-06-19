# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
"""
pytest test cases for tagging service
"""
import copy
import sqlite3
from datetime import datetime

import gevent
import pytest
from mock import MagicMock

from volttron.platform import get_services_core
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False
pymongo_skipif = pytest.mark.skipif(not HAS_PYMONGO,
                                    reason='No pymongo client available.')
connection_type = ""
db_connection = None
tagging_service_id = None
sqlite_config = {"connection": {"type": "sqlite",
                                "params": {"database": ""}},
                 "source": get_services_core("SQLiteTaggingService")}

mongodb_config = {"source": get_services_core("MongodbTaggingService"),
                  "connection": {"type": "mongodb",
                                 "params": {"host": "localhost", "port": 27017,
                                            "database": "mongo_test",
                                            "user": "test",
                                            "passwd": "test",
                                            "authSource": "admin"}}}

sqlite_historian = {
    "source": get_services_core("SQLHistorian"),
    "connection": {"type": "sqlite"}}
mysql_historian = {
    "source": get_services_core("SQLHistorian"),
    "connection": {
        "type": "mysql",
        "params": {
            "host": "localhost",
            "port": 3306,
            "database": "test_historian",
            "user": "historian",
            "passwd": "historian"
        }
    }
}
mongo_historian = {
    "source": get_services_core("MongodbHistorian"),
    "connection": {"type": "mongodb",
                   "params": {"host": "localhost",
                              "port": 27017,
                              "database": "mongo_test",
                              "user": "test",
                              "passwd": "test",
                              "authSource": "admin"}
                   }
}
crate_historian = {
    "source": get_services_core("CrateHistorian"),
    "connection": {
        "type": "crate",
        "schema": "testing",
        "params": {
            "host": "localhost:4200"
        }
    }
}

historians = [
    None,
    sqlite_historian,
    mysql_historian,
    mongo_historian,
    crate_historian
]


def setup_sqlite(config):
    print ("setup sqlite")
    connection_params = config['connection']['params']
    database_path = connection_params['database']
    print ("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print ("successfully connected to sqlite")
    return db_connection


def setup_mongodb(config):
    print ("setup mongodb")
    connection_params = config['connection']['params']
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    params = connection_params
    mongo_conn_str = mongo_conn_str.format(**params)
    mongo_client = pymongo.MongoClient(mongo_conn_str)
    db = mongo_client[connection_params['database']]
    db['topic_tags'].drop()
    db['tags'].drop()
    db['categories'].drop()
    db['tag_refs'].drop()
    return db


def cleanup_sqlite(db_connection, truncate_tables):
    cursor = db_connection.cursor()
    for table in truncate_tables:
        try:
            cursor.execute("DELETE FROM " + table)
        except sqlite3.OperationalError as e:
            print("Unable to truncate table {}. {}".format(table, e))

    db_connection.commit()
    pass


def cleanup_mongodb(db_connection, truncate_tables):
    for collection in truncate_tables:
        db_connection[collection].remove()
    print("Finished removing {}".format(truncate_tables))


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance2
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


# Fixtures for setup and teardown of historian agent
@pytest.fixture(scope="module",
                params=[
                    sqlite_config,
                    pymongo_skipif(mongodb_config)
                ])
def tagging_service(request, volttron_instance):
    global connection_type, db_connection, tagging_service_id
    connection_type = request.param['connection']['type']
    if connection_type == 'sqlite':
        request.param['connection']['params'][
            'database'] = volttron_instance.volttron_home + \
                          "/test_tagging.sqlite"
    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables, clean up records from previous test runs
    function_name = "setup_" + connection_type
    try:
        setup_function = globals()[function_name]
        db_connection = setup_function(request.param)
    except NameError:
        pytest.fail(
            msg="No setup method({}) found for connection type {} ".format(
                function_name, connection_type))

    print ("request.param -- {}".format(request.param))
    # 2. Install agent
    source = request.param.pop('source')
    tagging_service_id = volttron_instance.install_agent(
        vip_identity='platform.tagging', agent_dir=source,
        config_file=request.param, start=False)
    volttron_instance.start_agent(tagging_service_id)
    request.param['source'] = source
    print("agent id: ", tagging_service_id)

    # 3: add a tear down method to stop historian agent
    def stop_agent():
        print("In teardown method of tagging service")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(tagging_service_id)
        volttron_instance.remove_agent(tagging_service_id)

    request.addfinalizer(stop_agent)
    return request.param


@pytest.mark.tagging
def test_init_failure(volttron_instance, tagging_service, query_agent):
    agent_id = None
    global connection_type
    if connection_type == 'sqlite':
        pytest.skip("sqlite init should fail only in case of unexpected "
                    "errors")
    try:
        query_agent.callback = MagicMock(name="callback")
        query_agent.callback.reset_mock()
        # subscribe to schedule response topic
        query_agent.vip.pubsub.subscribe(peer='pubsub',
                                         prefix=topics.ALERTS_BASE,
                                         callback=query_agent.callback).get()
        new_config = copy.copy(tagging_service)
        new_config['connection'] = {"params":
                                        {"host": "localhost",
                                         "port": 27017,
                                         "database": "mongo_test",
                                         "user": "invalid_user",
                                         "passwd": "test",
                                         "authSource": "admin"}}
        source = new_config.pop('source')
        try:
            agent_id = volttron_instance.install_agent(
                vip_identity='test.tagging.init', agent_dir=source,
                config_file=new_config, start=False)
            volttron_instance.start_agent(agent_id)
        except:
            pass
        print ("Call back count {}".format(query_agent.callback.call_count))
        assert query_agent.callback.call_count == 1
        print("Call args {}".format(query_agent.callback.call_args))
        assert query_agent.callback.call_args[0][1] == 'test.tagging.init'

    finally:
        if agent_id:
            volttron_instance.remove_agent(agent_id)


@pytest.mark.tagging
def test_reinstall(volttron_instance, tagging_service,
                   query_agent):
    global connection_type, db_connection, tagging_service_id
    hist_id = None
    try:
        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": volttron_instance.volttron_home +
                                    "/test_tags_by_topic_no_metadata.sqlite"}}

                       }
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(2)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [{'p1': 2, 'p2': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(3)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus1/d2',
                                 tags={'campus': True,
                                       'dis': "Test description",
                                       "geoCountry": "US"}).get(timeout=10)

        result1 = query_agent.vip.rpc.call('platform.tagging',
                                           'get_tags_by_topic',
                                           topic_prefix='campus1/d2', skip=0,
                                           count=3, order="FIRST_TO_LAST").get(
            timeout=10)
        # [['campus', '1'],
        # ['dis', 'Test description'],
        # ['geoCountry', 'US']]
        print result1
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 2
        assert result1[0][0] == 'campus'
        assert result1[0][1]
        assert result1[1][0] == 'dis'
        assert result1[1][1] == 'Test description'
        assert result1[2][0] == 'geoCountry'
        assert result1[2][1] == 'US'

        # Now uninstall tagging service and resinstall with same config
        volttron_instance.remove_agent(tagging_service_id)
        gevent.sleep(2)
        # 2. Install agent
        source = tagging_service.pop('source')
        tagging_service_id = volttron_instance.install_agent(
            vip_identity='platform.tagging', agent_dir=source,
            config_file=tagging_service, start=False)
        volttron_instance.start_agent(tagging_service_id)
        tagging_service['source'] = source
        print("agent id: ", tagging_service_id)

        result1 = query_agent.vip.rpc.call('platform.tagging',
                                           'get_tags_by_topic',
                                           topic_prefix='campus1/d2', skip=0,
                                           count=3, order="FIRST_TO_LAST").get(
            timeout=10)
        # [['campus', '1'],
        # ['dis', 'Test description'],
        # ['geoCountry', 'US']]
        print result1
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 2
        assert result1[0][0] == 'campus'
        assert result1[0][1]
        assert result1[1][0] == 'dis'
        assert result1[1][1] == 'Test description'
        assert result1[2][0] == 'geoCountry'
        assert result1[2][1] == 'US'


    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_get_categories_no_desc(tagging_service, query_agent):
    result = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                      skip=0, count=4,
                                      order="FIRST_TO_LAST").get(timeout=10)
    assert isinstance(result, list)
    assert len(result) == 4
    print ("Categories returned: {}".format(result))
    result2 = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                       skip=1, count=4,
                                       order="FIRST_TO_LAST").get(timeout=10)
    assert isinstance(result2, list)
    print ("result2 returned: {}".format(result2))
    assert len(result2) == 4
    assert isinstance(result, list)
    assert isinstance(result[0], str)
    assert result[1] == result2[0]  # verify skip


@pytest.mark.tagging
def test_get_categories_with_desc(tagging_service, query_agent):
    result1 = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                       include_description=True, skip=0,
                                       count=4, order="LAST_TO_FIRST").get(
        timeout=10)
    assert isinstance(result1, list)
    assert isinstance(result1[0], list)
    assert len(result1) == 4
    assert len(result1[0]) == 2
    print ("Categories returned: {}".format(result1))
    result2 = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                       include_description=True, skip=1,
                                       count=4, order="LAST_TO_FIRST").get(
        timeout=10)
    assert isinstance(result2, list)
    assert len(result2) == 4
    assert isinstance(result2[0], list)
    print ("result2 returned: {}".format(result2))

    # Verify skip param
    assert result1[1][0] == result2[0][0]
    assert result1[1][1] == result2[0][1]

    # verify order
    result3 = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                       include_description=True, skip=0,
                                       count=4, order="FIRST_TO_LAST").get(
        timeout=10)
    assert isinstance(result3, list)
    assert len(result3) == 4
    assert isinstance(result3[0], list)
    assert result3[0][0] != result1[0][0]
    assert result3[0][1] != result1[0][1]


@pytest.mark.tagging
def test_tags_by_category_no_metadata(tagging_service, query_agent):
    result1 = query_agent.vip.rpc.call(
        'platform.tagging', 'get_tags_by_category', category='AHU', skip=0,
        count=3, order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result1))
    assert isinstance(result1, list)
    assert len(result1) == 3
    assert isinstance(result1[0], str)

    result2 = query_agent.vip.rpc.call('platform.tagging',
                                       'get_tags_by_category', category='AHU',
                                       skip=2, count=3,
                                       order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result2))
    assert isinstance(result2, list)
    assert len(result2) == 3  # verify count
    assert isinstance(result2[0], str)
    assert result1[2] == result2[0]  # verify skip


@pytest.mark.tagging
def test_tags_by_category_with_metadata(tagging_service, query_agent):
    result1 = query_agent.vip.rpc.call(
        'platform.tagging', 'get_tags_by_category', category='AHU',
        include_kind=True, skip=0, count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result1))
    assert isinstance(result1, list)
    assert len(result1) == 3
    assert isinstance(result1[0], list)
    assert len(result1[0]) == 2

    result2 = query_agent.vip.rpc.call(
        'platform.tagging', 'get_tags_by_category',
        category='AHU', include_description=True,
        skip=0, count=3, order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result2))
    assert isinstance(result2, list)
    assert len(result2) == 3
    assert isinstance(result2[0], list)
    assert len(result2[0]) == 2

    result3 = query_agent.vip.rpc.call(
        'platform.tagging', 'get_tags_by_category', category='AHU',
        include_kind=True, include_description=True, skip=0,
        count=3, order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result3))
    assert isinstance(result3, list)
    assert len(result3) == 3
    assert isinstance(result3[0], list)
    assert len(result3[0]) == 3


@pytest.mark.parametrize("historian_config", historians)
@pytest.mark.tagging
def test_insert_topic_tags(volttron_instance, tagging_service, query_agent,
                           historian_config):
    global connection_type, db_connection
    historian_id = None
    new_tagging_id = None
    tag_table_prefix = "insert"
    try:
        historian_id, historian_vip_identity, new_tagging_id, \
        new_tagging_vip_id = \
            setup_test_specific_agents(volttron_instance,
                                       historian_config,
                                       tagging_service,
                                       tag_table_prefix)

        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d1/all', 'headers': headers,
                    'message': [{'p1': 2, 'p2': 2}]}]
        query_agent.vip.rpc.call(historian_vip_identity, 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        query_agent.vip.rpc.call(
            new_tagging_vip_id,
            'add_topic_tags',
            topic_prefix='campus1/d1',
            tags={'campus': True, 'dis': "Test description"}).get(timeout=10)

        result3 = query_agent.vip.rpc.call(
            new_tagging_vip_id, 'get_tags_by_topic',
            topic_prefix='campus1/d1', include_kind=True,
            include_description=True, skip=0, count=3,
            order="LAST_TO_FIRST").get(timeout=10)

        # [['dis', 'Test description', 'Str', 'Short display name for an
        # entity.'],
        #  ['campus', '1', 'Marker',
        #   'Marks a campus that might have one or more site/building']]
        print result3
        assert len(result3) == 3
        assert len(result3[0]) == len(result3[1]) == 4
        assert result3[0][0] == 'id'
        assert result3[0][1] == 'campus1/d1'
        assert result3[0][2] == 'Ref'
        assert result3[0][3] == 'Unique identifier for an entity.'

        assert result3[1][0] == 'dis'
        assert result3[1][1] == 'Test description'
        assert result3[1][2] == 'Str'
        assert result3[1][3] == 'Short display name for an entity.'

        assert result3[2][0] == 'campus'
        assert result3[2][1]
        assert result3[2][2] == 'Marker'
        assert result3[2][
                   3] == 'Marks a campus that might have one or more ' \
                         'site/building'
    finally:
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, [tag_table_prefix + '_topic_tags'])
        if historian_id:
            volttron_instance.remove_agent(historian_id)
        if new_tagging_id:
            volttron_instance.remove_agent(new_tagging_id)


@pytest.mark.parametrize("historian_config", historians)
@pytest.mark.tagging
def test_insert_topic_pattern_tags(volttron_instance, tagging_service,
                                   query_agent, historian_config):
    global connection_type, db_connection

    historian_id = None
    new_tagging_id = None
    tag_table_prefix = "insert"
    try:

        historian_id, historian_vip_identity, new_tagging_id, \
        new_tagging_vip_id = \
            setup_test_specific_agents(volttron_instance,
                                       historian_config,
                                       tagging_service,
                                       tag_table_prefix)

        to_send = []
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send.append({'topic': 'devices/campus1/d1/all', 'headers': headers,
                        'message': [{'p1': 2, 'p2': 2}]})
        to_send.append({'topic': 'devices/campus2/d1/all', 'headers': headers,
                        'message': [{'p1': 2, 'p2': 2}]})
        to_send.append({'topic': 'devices/campus1/d2/all', 'headers': headers,
                        'message': [{'p1': 2, 'p2': 2}]})
        to_send.append({'topic': 'devices/campus2/d2/all', 'headers': headers,
                        'message': [{'p1': 2, 'p2': 2}]})

        query_agent.vip.rpc.call(historian_vip_identity, 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        # specific campus
        tags = {'campus1': {'geoCity': 'Richland', 'id': 'overwrite'},
                'campus*': {'campus': True, 'dis': "Test description"},
                'campus*/d*': {'device': True, 'dis': "Test description"},
                'campus*/d*/p*': {'point': True},
                'campus*/d1/p*': {'dis': 'd1 points'},
                'campus*/d*/p2': {'air': True},
                'asbaskuhdf/asdfasdf': {'equip': True}}
        # all campus
        # all device
        # all points
        # all device1 points
        # all points p2 points in d1 and d2
        # invalid topic

        result = query_agent.vip.rpc.call(new_tagging_vip_id, 'add_tags',
                                          tags=tags).get(timeout=10)
        print(result)

        exepected_info = {'campus*': ['campus2', 'campus1'],
                          'campus*/d*/p*': ['campus2/d2/p1', 'campus2/d1/p2',
                                            'campus2/d1/p1', 'campus2/d2/p2',
                                            'campus1/d1/p1', 'campus1/d1/p2',
                                            'campus1/d2/p1', 'campus1/d2/p2'],
                          'campus*/d1/p*': ['campus2/d1/p2', 'campus2/d1/p1',
                                            'campus1/d1/p1', 'campus1/d1/p2'],
                          'campus*/d*': ['campus1/d1', 'campus2/d1',
                                         'campus2/d2', 'campus1/d2'],
                          'campus*/d*/p2': ['campus2/d2/p2', 'campus2/d1/p2',
                                            'campus1/d2/p2', 'campus1/d1/p2']}
        expected_err = {'asbaskuhdf/asdfasdf': 'No matching topic found'}
        assert cmp(expected_err, result['error']) == 0
        assert cmp(exepected_info, result['info']) == 0

        result1 = query_agent.vip.rpc.call(new_tagging_vip_id,
                                           'get_tags_by_topic',
                                           topic_prefix='campus2/d2/p2',
                                           skip=0, count=3,
                                           order="FIRST_TO_LAST").get()
        print result1
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 2
        assert result1[0][0] == 'air'
        assert result1[0][1]
        assert result1[1][0] == 'id'
        assert result1[1][1] == 'campus2/d2/p2'
        assert result1[2][0] == 'point'
        assert result1[2][1]

        result1 = query_agent.vip.rpc.call(new_tagging_vip_id,
                                           'get_tags_by_topic',
                                           topic_prefix='campus2', skip=0,
                                           count=3,
                                           order="FIRST_TO_LAST").get()
        print ("Result1: {} ".format(result1))
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 2
        assert result1[0][0] == 'campus'
        assert result1[0][1]
        assert result1[1][0] == 'dis'
        assert result1[1][1] == "Test description"
        assert result1[2][0] == 'id'
        assert result1[2][1] == "campus2"

        result2 = query_agent.vip.rpc.call(new_tagging_vip_id,
                                           'get_tags_by_topic',
                                           topic_prefix='campus1', skip=0,
                                           count=3,
                                           order="LAST_TO_FIRST").get()
        print ("Result2:{}".format(result2))
        assert len(result2) == 3
        assert len(result2[0]) == len(result2[1]) == 2
        assert result2[2][0] == 'dis'
        assert result2[2][1] == "Test description"
        assert result2[1][0] == 'geoCity'
        assert result2[1][1] == "Richland"
        assert result2[0][0] == 'id'
        assert result2[0][1] == "campus1"

    finally:
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, [tag_table_prefix + '_topic_tags'])
        if historian_id:
            volttron_instance.remove_agent(historian_id)
        if new_tagging_id:
            volttron_instance.remove_agent(new_tagging_id)


@pytest.mark.parametrize("historian_config", historians)
@pytest.mark.tagging
def test_insert_topic_tags_update(volttron_instance, tagging_service,
                                  query_agent, historian_config):
    global connection_type, db_connection
    historian_id = None
    new_tagging_id = None
    tag_table_prefix = "insert"
    try:
        historian_id, historian_vip_identity, new_tagging_id, \
        new_tagging_vip_id = \
            setup_test_specific_agents(volttron_instance,
                                       historian_config,
                                       tagging_service,
                                       tag_table_prefix)
        to_send = []
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send.append({'topic': 'devices/campus1/d1/all', 'headers': headers,
                        'message': [{'p1': 2, 'p2': 2}]})

        query_agent.vip.rpc.call(historian_vip_identity, 'insert', to_send).get(
            timeout=10)
        gevent.sleep(3)

        # specific campus
        tags = {'campus1': {'geoCity': 'Richland', 'id': 'overwrite'}}

        result = query_agent.vip.rpc.call(new_tagging_vip_id, 'add_tags',
                                          tags=tags).get(timeout=10)

        result2 = query_agent.vip.rpc.call(new_tagging_vip_id,
                                           'get_tags_by_topic',
                                           topic_prefix='campus1', skip=0,
                                           count=3,
                                           order="LAST_TO_FIRST").get()
        print result2
        assert len(result2) == 2
        assert len(result2[0]) == len(result2[1]) == 2
        assert result2[1][0] == 'geoCity'
        assert result2[1][1] == "Richland"
        assert result2[0][0] == 'id'
        assert result2[0][1] == "campus1"

        tags = {'campus1': {'geoCity': 'Pasco', 'id': 'overwrite'}}
        result = query_agent.vip.rpc.call(new_tagging_vip_id, 'add_tags',
                                          tags=tags).get(timeout=10)

        result2 = query_agent.vip.rpc.call(new_tagging_vip_id,
                                           'get_tags_by_topic',
                                           topic_prefix='campus1', skip=0,
                                           count=3,
                                           order="LAST_TO_FIRST").get()
        print result2
        assert len(result2) == 2
        assert len(result2[0]) == len(result2[1]) == 2
        assert result2[1][0] == 'geoCity'
        assert result2[1][1] == "Pasco"
        assert result2[0][0] == 'id'
        assert result2[0][1] == "campus1"

    finally:
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, [tag_table_prefix + '_topic_tags'])
        if historian_id:
            volttron_instance.remove_agent(historian_id)
        if new_tagging_id:
            volttron_instance.remove_agent(new_tagging_id)


@pytest.mark.tagging
def test_update_topic_tags(volttron_instance, tagging_service, query_agent):
    global connection_type, db_connection
    hist_id = None
    try:
        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": volttron_instance.volttron_home +
                                    "/test_update_topic_tags.sqlite"}}

                       }
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(1)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [{'p1': 2, 'p2': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus1/d2',
                                 tags={'campus': True,
                                       'dis': "Test description"}).get(
            timeout=10)

        result3 = query_agent.vip.rpc.call('platform.tagging',
                                           'get_tags_by_topic',
                                           topic_prefix='campus1/d2',
                                           include_kind=True,
                                           include_description=True, skip=0,
                                           count=2, order="LAST_TO_FIRST").get(
            timeout=10)

        # [['dis', 'Test description', 'Str', 'Short display name for an
        # entity.'],
        #  ['campus', '1', 'Marker',
        #   'Marks a campus that might have one or more site/building']]
        print result3
        assert len(result3) == 2
        assert len(result3[0]) == len(result3[1]) == 4
        assert result3[0][0] == 'id'
        assert result3[0][1] == 'campus1/d2'
        assert result3[0][2] == 'Ref'
        assert result3[0][3] == 'Unique identifier for an entity.'

        assert result3[1][0] == 'dis'
        assert result3[1][1] == 'Test description'
        assert result3[1][2] == 'Str'
        assert result3[1][3] == 'Short display name for an entity.'

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus1/d2',
                                 tags={'campus': True,
                                       'dis': "New description",
                                       'geoCountry': "US"}).get(timeout=10)

        result3 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic',
            topic_prefix='campus1/d2', include_kind=True,
            include_description=True, skip=0, count=5,
            order="LAST_TO_FIRST").get(timeout=10)

        # [['geoCountry', 'US', 'Str',
        #   'Geographic country as ISO 3166-1 two letter code.'],
        #  ['dis', 'New description', 'Str', 'Short display name for an
        # entity.'],
        #  ['campus', '1', 'Marker',
        #   'Marks a campus that might have one or more site/building']]
        print result3
        assert len(result3) == 4
        assert len(result3[0]) == len(result3[1]) == 4
        assert result3[0][0] == 'id'
        assert result3[0][1] == 'campus1/d2'
        assert result3[0][2] == 'Ref'
        assert result3[0][3] == 'Unique identifier for an entity.'

        assert result3[1][0] == 'geoCountry'
        assert result3[1][1] == 'US'
        assert result3[1][2] == 'Str'
        assert result3[1][
                   3] == 'Geographic country as ISO 3166-1 two letter code.'

        assert result3[2][0] == 'dis'
        assert result3[2][1] == 'New description'
        assert result3[2][2] == 'Str'
        assert result3[2][3] == 'Short display name for an entity.'

        assert result3[3][0] == 'campus'
        assert result3[3][1]
        assert result3[3][2] == 'Marker'
        assert result3[3][
                   3] == 'Marks a campus that might have one or more ' \
                         'site/building'
    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_insert_tags_invalid_tag_error(tagging_service, query_agent):
    try:
        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags',
            topic_prefix='test_topic',
            tags={'t1': 1, 't2': 'val'}).get(timeout=10)
        pytest.fail("Expecting exception for invalid tags but got none")
    except Exception as e:
        assert e.exc_info['exc_type'] == 'ValueError'
        assert e.message == 'Invalid tag name:t2'


@pytest.mark.tagging
def test_tags_by_topic_no_metadata(volttron_instance, tagging_service,
                                   query_agent):
    global connection_type, db_connection
    hist_id = None
    try:
        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": volttron_instance.volttron_home +
                                    "/test_tags_by_topic_no_metadata.sqlite"}}

                       }
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(2)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [{'p1': 2, 'p2': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(3)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus1/d2',
                                 tags={'campus': True,
                                       'dis': "Test description",
                                       "geoCountry": "US"}).get(timeout=10)

        result1 = query_agent.vip.rpc.call('platform.tagging',
                                           'get_tags_by_topic',
                                           topic_prefix='campus1/d2', skip=0,
                                           count=3, order="FIRST_TO_LAST").get(
            timeout=10)
        # [['campus', '1'],
        # ['dis', 'Test description'],
        # ['geoCountry', 'US']]
        print result1
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 2
        assert result1[0][0] == 'campus'
        assert result1[0][1]
        assert result1[1][0] == 'dis'
        assert result1[1][1] == 'Test description'
        assert result1[2][0] == 'geoCountry'
        assert result1[2][1] == 'US'

        # verify skip and count
        result2 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic',
            topic_prefix='campus1/d2', skip=1, count=3,
            order="FIRST_TO_LAST").get(timeout=10)
        # [['dis', 'Test description'],
        # ['geoCountry', 'US']]
        print result2
        assert len(result2) == 3
        assert len(result2[0]) == len(result2[1]) == 2
        assert result2[0][0] == 'dis'
        assert result2[0][1] == 'Test description'
        assert result2[1][0] == 'geoCountry'
        assert result2[1][1] == 'US'
        assert result2[2][0] == 'id'
        assert result2[2][1] == 'campus1/d2'

        # query without count
        # verify skip and count
        result3 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic',
            topic_prefix='campus1/d2', skip=1,
            order="FIRST_TO_LAST").get(timeout=10)
        # [['dis', 'Test description'],
        # ['geoCountry', 'US']]
        print result3
        assert len(result3) == 3
        assert len(result3[0]) == len(result3[1]) == 2
        assert result3[0][0] == 'dis'
        assert result3[0][1] == 'Test description'
        assert result3[1][0] == 'geoCountry'
        assert result3[1][1] == 'US'
        assert result3[2][0] == 'id'
        assert result3[2][1] == 'campus1/d2'

        # verify sort
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic',
            topic_prefix='campus1/d2', skip=0, count=3,
            order="LAST_TO_FIRST").get(timeout=10)

        print result1
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 2
        assert result1[2][0] == 'dis'
        assert result1[2][1] == 'Test description'
        assert result1[1][0] == 'geoCountry'
        assert result1[1][1] == 'US'
        assert result1[0][0] == 'id'
        assert result1[0][1] == 'campus1/d2'
    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_tags_by_topic_with_metadata(volttron_instance, tagging_service,
                                     query_agent):
    global connection_type, db_connection
    hist_id = None
    try:
        hist_config = \
            {"connection":
               {"type": "sqlite",
                "params": {
                    "database": volttron_instance.volttron_home +
                        "/test_tags_by_topic_with_metadata.sqlite"}}}
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(1)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [{'p1': 2, 'p2': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags', topic_prefix='campus1/d2',
            tags={'campus': True, 'dis': "Test description"}).get(timeout=10)

        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic', topic_prefix='campus1/d2',
            include_description=True, skip=0, count=3,
            order="FIRST_TO_LAST").get(timeout=10)
        # [['campus', '1', 'Marks a campus that might have one or more
        # site/building'],
        # ['dis', 'Test description', 'Short display name for an entity.']]
        print result1
        assert len(result1) == 3
        assert len(result1[0]) == len(result1[1]) == 3
        assert result1[0][0] == 'campus'
        assert result1[0][1]
        assert result1[0][2] == 'Marks a campus that might have one or more ' \
                                'site/building'

        assert result1[1][0] == 'dis'
        assert result1[1][1] == 'Test description'
        assert result1[1][2] == 'Short display name for an entity.'

        assert result1[2][0] == 'id'
        assert result1[2][1] == "campus1/d2"
        assert result1[2][2] == 'Unique identifier for an entity.'

        result2 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic',
            topic_prefix='campus1/d2', include_kind=True,
            skip=0, count=1, order="LAST_TO_FIRST").get(timeout=10)
        # [['dis', 'Test description', 'Str']]
        print result2
        assert len(result2) == 1
        assert len(result2[0]) == 3
        assert result2[0][0] == 'id'
        assert result2[0][1] == "campus1/d2"
        assert result2[0][2] == 'Ref'

        result3 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_tags_by_topic',
            topic_prefix='campus1/d2', include_kind=True,
            include_description=True, skip=0, count=2,
            order="LAST_TO_FIRST").get(timeout=10)

        # [['dis', 'Test description', 'Str', 'Short display name for an
        # entity.'],
        #  ['campus', '1', 'Marker',
        #   'Marks a campus that might have one or more site/building']]
        print result3
        assert len(result3) == 2
        assert len(result3[0]) == len(result3[1]) == 4
        assert result3[0][0] == 'id'
        assert result3[0][1] == "campus1/d2"
        assert result3[0][2] == 'Ref'
        assert result3[0][3] == 'Unique identifier for an entity.'
        assert result3[1][0] == 'dis'
        assert result3[1][1] == 'Test description'
        assert result3[1][2] == 'Str'
        assert result3[1][3] == 'Short display name for an entity.'
    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_topic_by_tags_param_and_or(volttron_instance, tagging_service,
                                    query_agent):
    global connection_type, db_connection
    hist_id = None
    try:
        # 1. Start historian to get some valid topics in. tagging service
        # add tag api uses historian to get topic name by pattern
        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": volttron_instance.volttron_home +
                                    "/test_topic_by_tags_param_and_or.sqlite"}}

                       }
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(2)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        to_send = [{'topic': 'devices/campus1/d1/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)

        to_send = [{'topic': 'devices/campus2/d1/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        # 2. Add tags to topics and topic_prefix that can be used for queries
        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus1',
                                 tags={'campus': True,
                                       'dis': "Test campus description",
                                       'geoCountry': "US"}).get(timeout=10)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus2',
                                 tags={'campus': True,
                                       "geoCountry": "UK",
                                       'dis': "United Kingdom"}).get(
            timeout=10)

        query_agent.vip.rpc.call(
            'platform.tagging', 'add_tags',
            tags={
                'campus.*/d.*/p1': {'point': True, 'maxVal': 15, 'minVal': -1},
                'campus.*/d.*/p2': {'point': True, 'maxVal': 10, 'minVal': 0,
                                    'dis': "Test description"},
                'campus.*/d.*/p3': {'point': True, 'maxVal': 5, 'minVal': 1,
                                    'dis': "Test description"},
                'campus.*/d1': {'equip': True, 'elec': True, 'phase': 'p1_1',
                                'dis': "Test description"},
                'campus.*/d2': {'equip': True, 'elec': True,
                                'phase': 'p2'},
                'campus1/d.*': {'campusRef': 'campus1'},
                'campus2/d.*': {'campusRef': 'campus2'}}).get(timeout=10)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus2/d1',
                                 tags={'phase': "p1_2"}).get(timeout=10)
        gevent.sleep(2)

        # 3. Query topic prefix by tags

        # AND condition
        # Dict
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            and_condition={'campus': True, 'geoCountry': 'US'}).get(timeout=10)
        print ("Results of simple AND query: {} ".format(result1))
        assert result1 == ['campus1']

        # Array
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            and_condition=['equip', 'elec']).get(timeout=10)
        assert result1 == ['campus1/d1', 'campus1/d2', 'campus2/d1']

        # OR condition
        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            or_condition={"geoCountry": "UK",
                          'dis': "Test campus description"}).get(timeout=10)
        print ("Results of simple AND query: {} ".format(result1))
        assert result1 == ['campus1', 'campus2']

        # Array
        result1 = query_agent.vip.rpc.call('platform.tagging',
                                           'get_topics_by_tags',
                                           or_condition=['campus',
                                                         'equip']).get(
            timeout=10)
        assert result1 == ['campus1', 'campus1/d1', 'campus1/d2',
                           'campus2', 'campus2/d1']

        # AND AND OR
        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            and_condition={'campus': True,
                           'geoCountry': "US"},
            or_condition=['campus', 'equip']).get(timeout=10)
        assert result1 == ['campus1', 'campus2']

        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            and_condition={'equip': True,
                           'elec': True,
                           'campusRef.geoCountry': "UK",
                           'campusRef.dis': "United Kingdom"}).get(timeout=10)
        print("Result of NOT LIKE query: {}".format(result1))
        assert result1 == ['campus2/d1']

    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_topic_by_tags_custom_condition(volttron_instance, tagging_service,
                                        query_agent):
    global connection_type, db_connection
    hist_id = None
    try:

        # 1. Start historian to get some valid topics in. tagging service
        # add tag api uses historian to get topic name by pattern
        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": volttron_instance.volttron_home +
                                    "/topic_by_tags_custom_condition.sqlite"}}

                       }
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(2)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        to_send = [{'topic': 'devices/campus1/d1/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)

        to_send = [{'topic': 'devices/campus2/d1/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        # 2. Add tags to topics and topic_prefix that can be used for queries
        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags', topic_prefix='campus1',
            tags={'campus': True, 'dis': "Test description",
                  "geoCountry": "US"}).get(timeout=10)

        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags', topic_prefix='campus2',
            tags={'campus': True, "geoCountry": "UK"}).get(timeout=10)

        query_agent.vip.rpc.call(
            'platform.tagging', 'add_tags',
            tags={
                'campus.*/d.*/p1': {'point': True, 'maxVal': 15, 'minVal': -1},
                'campus.*/d.*/p2': {'point': True, 'maxVal': 10, 'minVal': 0,
                                    'dis': "Test description"},
                'campus.*/d.*/p3': {'point': True, 'maxVal': 5, 'minVal': 1,
                                    'dis': "Test description"},
                'campus.*/d1': {'equip': True, 'elec': True, 'phase': 'p1_1',
                                'dis': "Test description"},
                'campus.*/d2': {'equip': True, 'elec': True,
                                'phase': 'p2'},
                'campus1/d.*': {'campusRef': 'campus1'},
                'campus2/d.*': {'campusRef': 'campus2'}}).get(timeout=10)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus2/d1',
                                 tags={'phase': "p1_2"}).get(timeout=10)
        gevent.sleep(2)

        # 3. Query topic prefix by tags
        # Simple AND
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition="campus AND geoCountry='US'").get(timeout=10)
        print ("Results of simple AND query: {} ".format(result1))
        assert len(result1) == 1
        assert result1[0] == 'campus1'

        # AND and OR precedence
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='minVal<0 OR maxVal>=5 AND maxVal<10').get(timeout=10)
        print ("Results of AND and OR query: {} ".format(result1))
        assert len(result1) == 6
        # Check  default order
        assert result1 == ['campus1/d1/p1', 'campus1/d1/p3', 'campus1/d2/p1',
                           'campus1/d2/p3', 'campus2/d1/p1', 'campus2/d1/p3']

        # Change precedence with parenthesis
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='(minVal<0 OR maxVal>=5) AND maxVal<10').get(timeout=10)
        print ("Results of AND and OR query with parenthesis: {} ".format(
            result1))
        assert len(result1) == 3
        assert result1 == ['campus1/d1/p3', 'campus1/d2/p3', 'campus2/d1/p3']

        # Verify skip, count and order
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='(minVal<0 OR maxVal>=5) AND maxVal<10', skip=1,
            count=2, order="LAST_TO_FIRST").get(timeout=10)
        print("Results of query with skip and count: {}".format(result1))
        assert result1 == ['campus1/d2/p3', 'campus1/d1/p3']

        # Verify NOT
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='NOT campus AND NOT point AND dis="Test '
                      'description"').get(timeout=10)
        print("Results of NOT query1: {}".format(result1))
        assert result1 == ['campus1/d1', 'campus2/d1']

        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='point AND NOT(maxVal>=5 AND minVal=1)').get(timeout=10)
        print("Results of NOT query2: {}".format(result1))
        assert result1 == ['campus1/d1/p1', 'campus1/d1/p2', 'campus1/d2/p1',
                           'campus1/d2/p2', 'campus2/d1/p1', 'campus2/d1/p2']

        # Verify unary minus
        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='minVal=-1').get(timeout=10)
        print("Results of unary minus query: {}".format(result1))
        assert result1 == ['campus1/d1/p1', 'campus1/d2/p1', 'campus2/d1/p1']

        # Verify LIKE
        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            condition='equip AND phase LIKE "p1.*"').get(timeout=10)
        print("Results of LIKE query: {}".format(result1))
        assert result1 == ['campus1/d1', 'campus2/d1']

        # NOT LIKE
        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            condition='equip AND NOT (phase LIKE "p1.*")').get(timeout=10)
        print("Result of NOT LIKE query: {}".format(result1))
        assert result1 == ['campus1/d2']


    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_topic_by_tags_parent_topic_query(volttron_instance, tagging_service,
                                          query_agent):
    global connection_type, db_connection
    hist_id = None
    try:

        # 1. Start historian to get some valid topics in. tagging service
        # add tag api uses historian to get topic name by pattern
        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": volttron_instance.volttron_home +
                                    "/topic_by_tags_parent_topic.sqlite"}}

                       }
        hist_id = volttron_instance.install_agent(
            vip_identity='platform.historian',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)
        gevent.sleep(2)
        headers = {headers_mod.DATE: datetime.utcnow().isoformat()}
        to_send = [{'topic': 'devices/campus1/d2/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        to_send = [{'topic': 'devices/campus1/d1/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)

        to_send = [{'topic': 'devices/campus2/d1/all', 'headers': headers,
                    'message': [
                        {'p1': 2, 'p2': 2, 'p3': 1, 'p4': 2, 'p5': 2}]}]
        query_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(
            timeout=10)
        gevent.sleep(2)

        # 2. Add tags to topics and topic_prefix that can be used for queries
        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags', topic_prefix='campus1',
            tags={'campus': True, 'dis': "Test description",
                  "geoCountry": "US"}).get(timeout=10)

        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags', topic_prefix='campus2',
            tags={'campus': True, "geoCountry": "UK",
                  'dis': "United Kingdom"}).get(timeout=10)

        query_agent.vip.rpc.call(
            'platform.tagging', 'add_tags',
            tags={
                'campus.*/d.*/p1': {'point': True, 'maxVal': 15, 'minVal': -1},
                'campus.*/d.*/p2': {'point': True, 'maxVal': 10, 'minVal': 0,
                                    'dis': "Test description"},
                'campus.*/d.*/p3': {'point': True, 'maxVal': 5, 'minVal': 1,
                                    'dis': "Test description"},
                'campus.*/d1': {'equip': True, 'elec': True, 'phase': 'p1_1',
                                'dis': "Test description"},
                'campus.*/d2': {'equip': True, 'elec': True,
                                'phase': 'p2'},
                'campus1/d.*': {'campusRef': 'campus1'},
                'campus2/d.*': {'campusRef': 'campus2'}}).get(timeout=10)

        query_agent.vip.rpc.call('platform.tagging', 'add_topic_tags',
                                 topic_prefix='campus2/d1',
                                 tags={'phase': "p1_2"}).get(timeout=10)
        gevent.sleep(2)

        # 3. Query topic prefix by tags
        # Verify parent topic query
        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            condition='equip AND elec AND campusRef.geoCountry="UK"').get(
            timeout=10)
        print("Result of NOT LIKE query: {}".format(result1))
        assert result1 == ['campus2/d1']

        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            condition='equip AND elec AND campusRef.geoCountry LIKE "UK.*"'
        ).get(timeout=10)
        print("Result of NOT LIKE query: {}".format(result1))
        assert result1 == ['campus2/d1']

        result1 = query_agent.vip.rpc.call(
            'platform.tagging',
            'get_topics_by_tags',
            condition='equip AND elec AND campusRef.geoCountry="UK" AND '
                      'campusRef.dis="United Kingdom"').get(timeout=10)
        print("Result of NOT LIKE query: {}".format(result1))
        assert result1 == ['campus2/d1']

        result1 = query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='equip AND elec AND NOT(campusRef.geoCountry="UK" AND '
                      'campusRef.dis="United Kingdom")').get(timeout=10)
        print("Result of NOT LIKE query: {}".format(result1))
        assert result1 == ['campus1/d1', 'campus1/d2']

    finally:
        if hist_id:
            volttron_instance.remove_agent(hist_id)
        cleanup_function = globals()["cleanup_" + connection_type]
        cleanup_function(db_connection, ['topic_tags'])


@pytest.mark.tagging
def test_topic_by_tags_condition_errors(volttron_instance, tagging_service,
                                        query_agent):
    # Invalid tag name
    try:
        query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='minValue<0 OR maxVal>=5').get(timeout=10)
        pytest.fail("Expected value error. Got none")
    except RemoteError as e:
        assert e.message == 'Invalid tag minValue at line number 1 and ' \
                            'column number 0'
        assert e.exc_info['exc_type'] == 'ValueError'

    # Missing parenthesis
    try:
        query_agent.vip.rpc.call(
            'platform.tagging', 'get_topics_by_tags',
            condition='(equip OR ahu AND maxVal<10').get(timeout=10)
        pytest.fail("Expected value error. Got none")
    except RemoteError as e:
        pass

    # Invalid type after LIKE
    try:
        query_agent.vip.rpc.call('platform.tagging', 'get_topics_by_tags',
                                 condition='maxVal like 10').get(timeout=10)
        pytest.fail("Expected value error. Got none")
    except Exception as e:
        assert e.message == 'Syntax error in query condition. ' \
                            'Invalid token 10 at line ' \
                            'number 1 and column number 12'
        assert e.exc_info['exc_type'] == 'ValueError'


def setup_test_specific_agents(volttron_instance, historian_config,
                               tagging_service, table_prefix):
    new_tag_service = copy.copy(tagging_service)
    if historian_config is None or \
            historian_config["connection"]["type"] == "sqlite":
        historian_config = {
            "source": get_services_core("SQLHistorian"),
            "connection":
                {"type": "sqlite",
                 "params": {
                     "database":
                         volttron_instance.volttron_home +
                         "/for_insert_topic_pattern.sqlite"}
                 }
        }
    historian_vip_identity = "platform.historian"
    historian_source = get_services_core("SQLHistorian")
    if historian_config is not None:
        historian_vip_identity = historian_config["connection"]["type"] \
                                 + ".historian"
        historian_source = historian_config.pop("source")
        new_tag_service['historian_vip_identity'] = historian_vip_identity
        new_tag_service["table_prefix"] = table_prefix

    hist_id = volttron_instance.install_agent(
        vip_identity=historian_vip_identity,
        agent_dir=historian_source, config_file=historian_config,
        start=True)
    gevent.sleep(1)

    # put source back in config after install so that it can be used for next
    # test case
    historian_config["source"] = historian_source

    new_tagging_id = volttron_instance.install_agent(
        vip_identity='new_tagging',
        agent_dir=new_tag_service.pop("source"),
        config_file=new_tag_service,
        start=True)
    gevent.sleep(1)
    return hist_id, historian_vip_identity, new_tagging_id, 'new_tagging'
