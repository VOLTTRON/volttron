# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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
# Government nor the United States Department of Energy, nor Battelle,
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
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
"""
pytest test cases for tagging service
"""
import copy
import pytest
import sqlite3

import sys
from mock import MagicMock

from volttron.platform.messaging import topics
from volttron.platform.agent.base_tagging import TagInsertionError

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False
pymongo_skipif = pytest.mark.skipif(not HAS_PYMONGO,
                                    reason='No pymongo client available.')

sqlite_config= {
    "connection": {
        "type": "sqlite",
        "params": {
            "database": "~/.volttron/data/volttron.tags.sqlite"
        }
    },
    "source":"services/core/SQLiteTaggingService"
}

mongodb_config = {
    "source": "services/core/MongodbTaggingService",
    "connection": {
        "type": "mongodb",
        "params": {
            "host": "localhost",
            "port": 27017,
            "database": "mongo_test",
            "user": "test",
            "passwd": "test"
        }
    }
}

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
    return db

def cleanup_sqlite(db_connection, truncate_tables):
    cursor = db_connection.cursor()
    # for table in truncate_tables:
    #     cursor.execute("DELETE FROM " + table)
    db_connection.commit()

def cleanup_mongodb(db_connection, truncate_tables):
    for collection in truncate_tables:
        db_connection[collection].remove()

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
                    #pymongo_skipif(mongodb_config)
                ])
def tagging_service(request, volttron_instance):
    connection_type = request.param['connection']['type']
    if connection_type == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance.volttron_home + "/test_tagging.sqlite"
    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables
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
        vip_identity='platform.tagging',
        agent_dir=source, config_file=request.param,
        start=False)
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
    try:
        query_agent.callback = MagicMock(name="callback")
        query_agent.callback.reset_mock()
        # subscribe to schedule response topic
        query_agent.vip.pubsub.subscribe(peer='pubsub',
                                         prefix=topics.ALERTS_BASE,
                                         callback=query_agent.callback).get()
        new_config = copy.copy(tagging_service)
        new_config["resource_sub_dir"] = "bad_dir"
        source = new_config.pop('source')
        try:
            agent_id = volttron_instance.install_agent(
                vip_identity='test.tagging.init',
                agent_dir=source, config_file=new_config, start=False)
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
def test_get_categories_no_desc(tagging_service, query_agent):
    result = query_agent.vip.rpc.call('platform.tagging',
                                      'get_categories',
                                      skip=0,
                                      count=4,
                                      order="FIRST_TO_LAST").get(timeout=10)
    assert isinstance(result, list)
    assert len(result) == 4
    print ("Categories returned: {}".format(result))
    result2 = query_agent.vip.rpc.call('platform.tagging',
                                       'get_categories',
                                       skip=1,
                                       count=4,
                                       order="FIRST_TO_LAST").get(timeout=10)
    assert isinstance(result2, list)
    print ("result2 returned: {}".format(result2))
    assert len(result2) == 4
    assert isinstance(result, list)
    assert isinstance(result[0], str)
    assert result[1] == result2[0] #verify skip


@pytest.mark.tagging
def test_get_categories_with_desc(tagging_service, query_agent):

    result1 = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                      include_description=True,
                                      skip=0, count=4,
                                      order="LAST_TO_FIRST").get(timeout=10)
    assert isinstance(result1, list)
    assert isinstance(result1[0],list)
    assert len(result1) == 4
    assert len(result1[0]) == 2
    print ("Categories returned: {}".format(result1))
    result2 = query_agent.vip.rpc.call('platform.tagging', 'get_categories',
                                       include_description=True,
                                       skip=1, count=4,
                                       order="LAST_TO_FIRST").get(timeout=10)
    assert isinstance(result2, list)
    assert len(result2) == 4
    assert isinstance(result2[0], list)
    print ("result2 returned: {}".format(result2))

    #Verify skip param
    assert result1[1][0] == result2[0][0]
    assert result1[1][1] == result2[0][1]

    #verify order
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
        'platform.tagging',
        'get_tags_by_category',
        category='AHU',
        skip=0,
        count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result1))
    assert isinstance(result1, list)
    assert len(result1) == 3
    assert isinstance(result1[0], str)

    result2 = query_agent.vip.rpc.call('platform.tagging',
                                       'get_tags_by_category',
                                       category='AHU', skip=2, count=3,
                                       order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result2))
    assert isinstance(result2, list)
    assert len(result2) == 3  # verify count
    assert isinstance(result2[0], str)
    assert result1[2] == result2[0]  # verify skip


@pytest.mark.tagging
def test_tags_by_category_with_metadata(tagging_service, query_agent):

    result1 = query_agent.vip.rpc.call(
        'platform.tagging',
        'get_tags_by_category',
        category='AHU',
        include_kind=True,
        skip=0,
        count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result1))
    assert isinstance(result1, list)
    assert len(result1) == 3
    assert isinstance(result1[0], list)
    assert len(result1[0]) == 2

    result2 = query_agent.vip.rpc.call(
        'platform.tagging',
        'get_tags_by_category',
        category='AHU',
        include_description=True,
        skip=0,
        count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result2))
    assert isinstance(result2, list)
    assert len(result2) == 3
    assert isinstance(result2[0], list)
    assert len(result2[0]) == 2

    result3 = query_agent.vip.rpc.call('platform.tagging',
                                       'get_tags_by_category', category='AHU',
                                       include_kind=True,
                                       include_description=True,
                                       skip=0, count=3,
                                       order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result3))
    assert isinstance(result3, list)
    assert len(result3) == 3
    assert isinstance(result3[0], list)
    assert len(result3[0]) == 3




@pytest.mark.dev
@pytest.mark.tagging
def test_insert_topic_tags(tagging_service, query_agent):
    try:
        query_agent.vip.rpc.call(
            'platform.tagging', 'add_topic_tags', topic_prefix='test_topic',
            tags={'t1':1, 't2':'val'}).get(timeout=10)
        pytest.fail("Expecting exception for invalid tags but got none")
    except Exception as e:
        assert e.exc_info['exc_type'] == \
               'volttron.platform.agent.base_tagging.TagInsertionError'
        assert e.message == 'Invalid tag name:t2'

    query_agent.vip.rpc.call(
        'platform.tagging', 'add_topic_tags', topic_prefix='test_topic',
        tags={'campus': True, 'dis': "Test description"}).get(timeout=10)

    result1 = query_agent.vip.rpc.call('platform.tagging', 'get_tags_by_topic',
        topic_prefix='test_topic', include_description=True, skip=0, count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    # [['campus', '1', 'Marks a campus that might have one or more site/building'],
    # ['dis', 'Test description', 'Short display name for an entity.']]
    print result1
    assert len(result1) == 2
    assert len(result1[0]) == len(result1[1]) == 3
    assert result1[0][0] == 'campus'
    assert result1[0][1]
    assert result1[0][2] == 'Marks a campus that might have one or more ' \
                            'site/building'
    assert result1[1][0] == 'dis'
    assert result1[1][1] == 'Test description'
    assert result1[1][2] == 'Short display name for an entity.'


    result2 = query_agent.vip.rpc.call('platform.tagging', 'get_tags_by_topic',
                                       topic_prefix='test_topic',
                                       include_kind=True, skip=0,
                                       count=1,
                                       order="LAST_TO_FIRST").get(timeout=10)
    # [['dis', 'Test description', 'Str']]
    print result2
    assert len(result2) == 1
    assert len(result2[0]) == 3
    assert result2[0][0] == 'dis'
    assert result2[0][1] == 'Test description'
    assert result2[0][2] == 'Str'


    result3 = query_agent.vip.rpc.call('platform.tagging', 'get_tags_by_topic',
                                       topic_prefix='test_topic',
                                       include_kind=True,
                                       include_description=True,
                                       skip=0, count=2,
                                       order="LAST_TO_FIRST").get(timeout=10)

    # [['dis', 'Test description', 'Str', 'Short display name for an entity.'],
    #  ['campus', '1', 'Marker',
    #   'Marks a campus that might have one or more site/building']]
    print result3
    assert len(result3) == 2
    assert len(result3[0]) == len(result3[1]) == 4
    assert result3[0][0] == 'dis'
    assert result3[0][1] == 'Test description'
    assert result3[0][2] == 'Str'
    assert result3[0][3] == 'Short display name for an entity.'
    assert result3[1][0] == 'campus'
    assert result3[1][1]
    assert result3[1][2] == 'Marker'
    assert result3[1][3] == \
           'Marks a campus that might have one or more site/building'

    result4 = query_agent.vip.rpc.call('platform.tagging', 'get_tags_by_topic',
                                       topic_prefix='test_topic',
                                       skip=0, count=2,
                                       order="LAST_TO_FIRST").get(timeout=10)
    # [['dis', 'Test description'],['campus', '1']]
    assert len(result4) == 2
    assert len(result4[0]) == len(result4[1]) == 2
    assert result4[0][0] == 'dis'
    assert result4[0][1] == 'Test description'
    assert result4[1][0] == 'campus'
    assert result4[1][1]





@pytest.mark.tagging
def test_tags_by_topic_no_metadata(tagging_service, query_agent):

    result1 = query_agent.vip.rpc.call(
        'platform.tagging',
        'get_tags_by_topic',
        topic_prefix='PNNL-SEQUIM',
        skip=0,
        count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result1))
    assert isinstance(result1, list)
    assert len(result1) == 3
    assert isinstance(result1[0], list)
    assert len(result1[0]) == 2

    # verify skip
    result2 = query_agent.vip.rpc.call('platform.tagging',
                                       'get_tags_by_topic',
                                       topic_prefix='PNNL-SEQUIM',
                                       skip=2,
                                       count=3,
                                       order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result2))
    assert isinstance(result2, list)
    assert len(result2) == 3  # verify count
    assert isinstance(result2[0], list)
    assert len(result2[0]) == 2
    assert result1[2] == result2[0]  # verify skip

    # query without count
    result3 = query_agent.vip.rpc.call(
        'platform.tagging', 'get_tags_by_topic', topic_prefix='PNNL-SEQUIM',
        skip=2, order="FIRST_TO_LAST").get(timeout=10)
    assert isinstance(result2, list)
    assert isinstance(result2[0], list)
    assert len(result2[0]) == 2
    assert result1[2] == result2[0] == result3[0]  # verify skip

    # verify sort
    result4 = query_agent.vip.rpc.call('platform.tagging', 'get_tags_by_topic',
        topic_prefix='PNNL-SEQUIM', order="LAST_TO_FIRST").get(timeout=10)
    assert isinstance(result4, list)
    assert isinstance(result4[0], list)
    assert len(result4[0]) == 2
    assert result3[0] == result4[-3]  # verify reverse order

@pytest.mark.tagging
def test_tags_by_topic_with_metadata(tagging_service, query_agent):

    result1 = query_agent.vip.rpc.call(
        'platform.tagging',
        'get_tags_by_topic',
        topic_prefix='PNNL-SEQUIM',
        include_kind=True,
        skip=0,
        count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result1))
    assert isinstance(result1, list)
    assert isinstance(result1[0], list)
    assert len(result1) == 3
    assert len(result1[0]) == 3

    result2 = query_agent.vip.rpc.call(
        'platform.tagging',
        'get_tags_by_topic',
        topic_prefix='PNNL-SEQUIM',
        include_description=True,
        skip=0,
        count=3,
        order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result2))
    assert isinstance(result2, list)
    assert isinstance(result2[0], list)
    assert len(result2) == 3
    assert len(result2[0]) == 3

    result3 = query_agent.vip.rpc.call('platform.tagging',
                                       'get_tags_by_topic',
                                       topic_prefix='PNNL-SEQUIM',
                                       include_kind=True,
                                       include_description=True,
                                       skip=0, count=3,
                                       order="FIRST_TO_LAST").get(timeout=10)
    print ("tags returned: {}".format(result3))
    assert isinstance(result3, list)
    assert isinstance(result3[0], list)
    assert len(result3) == 3
    assert len(result3[0]) == 4






