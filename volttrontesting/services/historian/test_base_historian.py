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

import shutil

from volttron.platform import get_services_core, jsonapi

from volttron.platform.agent.base_historian import (BaseHistorian,
                                                    STATUS_KEY_BACKLOGGED,
                                                    STATUS_KEY_CACHE_COUNT,
                                                    STATUS_KEY_PUBLISHING,
                                                    STATUS_KEY_CACHE_FULL)
import pytest

from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.health import *
from time import sleep
from datetime import datetime
import random
import gevent
import os


class Historian(BaseHistorian):
    def publish_to_historian(self, _):
        pass

    def query_topic_list(self):
        pass

    def query_historian(self, **kwargs):
        pass


def prep_config(volttron_home):
    src_driver = os.getcwd() + '/services/core/MasterDriverAgent/example_configurations/test_fakedriver.config'
    new_driver = volttron_home + '/test_fakedriver.config'
    shutil.copy(src_driver, new_driver)

    with open(new_driver, 'r+') as f:
        config = jsonapi.load(f)
        config['registry_config'] = os.getcwd() + '/services/core/MasterDriverAgent/example_configurations/fake.csv'
        f.seek(0)
        f.truncate()
        jsonapi.dump(config, f)

    master_config = {
        "agentid": "master_driver",
        "driver_config_list": [new_driver]
    }

    return master_config


foundtopic = False


def listener(peer, sender, bus, topic, headers, message):
    global foundtopic
    foundtopic = True


@pytest.mark.xfail(reason="This won't work on all machines because of "
                          "hardcoded paths.")
def test_base_historian(volttron_instance):
    global foundtopic
    v1 = volttron_instance
    assert v1.is_running()

    master_config = prep_config(v1.volttron_home)
    master_uuid = v1.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                   config_file=master_config)
    gevent.sleep(2)
    assert v1.is_agent_running(master_uuid)
    db = Historian(address=v1.vip_address[0],
                   backup_storage_limit_gb=0.00002)
    gevent.spawn(db.core.run).join(0)

    agent = v1.dynamic_agent
    gevent.sleep(2)
    agent.vip.pubsub.subscribe('pubsub', 'backupdb/nomore', callback=listener)

    for _ in range(0, 60):
        gevent.sleep(1)
        if foundtopic:
            break

    assert foundtopic


class BasicHistorian(BaseHistorian):
    def __init__(self, **kwargs):
        super(BasicHistorian, self).__init__(**kwargs)
        self.publish_fail = False
        self.publish_sleep = 0
        self.seen = []

    def publish_to_historian(self, to_publish_list):
        self.seen.extend(to_publish_list)

        if self.publish_sleep:
            sleep(self.publish_sleep)

        if not self.publish_fail:
            self.report_all_handled()

    def reset(self):
        self.seen = []

    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None, order="FIRST_TO_LAST"):
        """Not implemented
        """
        raise NotImplemented("query_historian not implimented for null historian")


@pytest.fixture(scope="module")
def client_agent(request, volttron_instance):
    agent = volttron_instance.build_agent()
    yield agent
    agent.core.stop()

alert_publishes = []

def message_handler(peer, sender, bus, topic, headers, message):
    alert_publishes.append(Status.from_json(message))


@pytest.mark.historian
def test_cache_backlog(request, volttron_instance, client_agent):
    """
    Test basic use of health subsystem in the base historian.
    """
    global alert_publishes
    historian = None
    alert_publishes = []
    try:
        # subscribe to alerts
        client_agent.vip.pubsub.subscribe("pubsub", "alerts/BasicHistorian", message_handler)

        identity = 'platform.historian'
        historian = volttron_instance.build_agent(agent_class=BasicHistorian,
                                              identity=identity,
                                              submit_size_limit=2,
                                              max_time_publishing=1,
                                              retry_period=1.0,
                                              backup_storage_limit_gb=0.0001)  # 100K
        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"
        gevent.sleep(5) #wait for historian to be fully up
        print("\n** test_basic_function for {}**".format(
            request.keywords.node.name))

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings.  Randome readings are going to be
        # within the tolerance here.
        format_spec = "{0:.13f}"
        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)
        damper_reading = random.uniform(0, 100)

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
        percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Test publish slow or backlogged
        historian.publish_sleep = 1.5
        d_now = datetime.utcnow()
        now = utils.format_timestamp(d_now)
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        # d_now = d_now + timedelta(seconds=1)
        from datetime import timedelta
        for i in range(500):
            client_agent.vip.pubsub.publish('pubsub',
                                            DEVICES_ALL_TOPIC,
                                            headers=headers,
                                            message=all_message)
            if i % 10 == 0:
                # So that we don't send a huge batch to only get deleted from cache right after
                # inserting. Dumping a big batch in one go will make the the cache size to be
                # over the limit so right after insert, cache size will be checked and cleanup
                # will be delete records
                gevent.sleep(0.5)
            gevent.sleep(0.00001)  # yield to historian thread to do the publishing

        gevent.sleep(4)
        status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)
        print(f"STATUS: {status}")
        assert status["status"] == STATUS_BAD
        assert status["context"][STATUS_KEY_BACKLOGGED]

        # Cache count can be 0 even if we are backlogged and cache is full because
        # cache might have just got deleted
        #assert status["context"][STATUS_KEY_CACHE_COUNT] > 0

        # Cache need not be full if it is backlogged. but if cache is full backlogged should be true
        # and alert should be sent
        if status["context"][STATUS_KEY_CACHE_FULL] :
            gevent.sleep(1)
            print(alert_publishes)
            alert_publish = alert_publishes[-1]
            assert alert_publish.status == STATUS_BAD
            context = alert_publish.context
            assert context[STATUS_KEY_CACHE_FULL]
            assert STATUS_KEY_CACHE_FULL in status["context"]
        else:
            print("cache is not full")

        historian.publish_sleep = 0
        gevent.sleep(10)
        status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)
        print(f"current time: {utils.format_timestamp(datetime.utcnow())}")
        print(f"status is {status}")
        assert status["status"] == STATUS_GOOD
        assert status["context"][STATUS_KEY_PUBLISHING]
        assert not status["context"][STATUS_KEY_BACKLOGGED]
        assert not status["context"][STATUS_KEY_CACHE_FULL]
        assert not bool(status["context"][STATUS_KEY_CACHE_COUNT])
    finally:
        if historian:
            historian.core.stop()
        # wait for cleanup to complete
        gevent.sleep(2)


@pytest.mark.historian
def test_health_stuff(request, volttron_instance, client_agent):
    """
    Test basic use of health subsystem in the base historian.
    """
    global alert_publishes
    historian = None
    try:
        identity = 'platform.historian'
        historian = volttron_instance.build_agent(agent_class=BasicHistorian,
                                              identity=identity,
                                              submit_size_limit=2,
                                              max_time_publishing=0.5,
                                              retry_period=1.0,
                                              backup_storage_limit_gb=0.0001)  # 100K
        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

        print("\n** test_basic_function for {}**".format(
            request.keywords.node.name))

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings.  Randome readings are going to be
        # within the tolerance here.
        format_spec = "{0:.13f}"
        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)
        damper_reading = random.uniform(0, 100)

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
        percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Create timestamp
        now = utils.format_timestamp(datetime.utcnow())

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        for _ in range(10):
            client_agent.vip.pubsub.publish('pubsub',
                                             DEVICES_ALL_TOPIC,
                                             headers=headers,
                                             message=all_message).get(timeout=10)

        gevent.sleep(2.0)

        status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

        assert status["status"] == STATUS_GOOD
        assert status["context"][STATUS_KEY_PUBLISHING]
        assert not status["context"][STATUS_KEY_BACKLOGGED]
        assert not status["context"][STATUS_KEY_CACHE_FULL]
        assert not bool(status["context"][STATUS_KEY_CACHE_COUNT])

        # Test publish failure
        client_agent.vip.pubsub.subscribe("pubsub", "alerts/BasicHistorian", message_handler)

        historian.publish_fail = True

        for _ in range(10):
            client_agent.vip.pubsub.publish('pubsub',
                                             DEVICES_ALL_TOPIC,
                                             headers=headers,
                                             message=all_message).get(timeout=10)
        gevent.sleep(2)
        status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

        alert_publish = alert_publishes[0]

        alert_publishes = []

        assert status["status"] == STATUS_BAD
        assert not status["context"][STATUS_KEY_PUBLISHING]

        assert alert_publish.status == STATUS_BAD

        historian.publish_fail = False

        gevent.sleep(2.0)

        status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

        assert status["status"] == STATUS_GOOD
        assert status["context"][STATUS_KEY_PUBLISHING]
        assert not status["context"][STATUS_KEY_BACKLOGGED]
        assert not status["context"][STATUS_KEY_CACHE_FULL]
        assert not bool(status["context"][STATUS_KEY_CACHE_COUNT])
    finally:
        if historian:
            historian.core.stop()
        # wait for cleanup to complete
        gevent.sleep(2)


class FailureHistorian(BaseHistorian):
    def __init__(self, **kwargs):
        super(FailureHistorian, self).__init__(**kwargs)
        self.publish_fail = False
        self.setup_fail = False
        self.record_fail = False
        self.teardown_fail = False
        self.setup_run = False
        self.record_run = False
        self.teardown_run = False
        self.seen = []

    def publish_to_historian(self, to_publish_list):
        if self.publish_fail:
            raise Exception("Failed to publish.")

        self.seen.extend(to_publish_list)
        self.report_all_handled()

    def query_topic_list(self):
        pass

    def query_historian(self):
        pass

    def reset(self):
        self.seen = []
        self.setup_run = False
        self.record_run = False
        self.teardown_run = False
        self.setup_fail = False
        self.record_fail = False
        self.teardown_fail = False
        self.publish_fail = False

    def historian_setup(self):
        if self.setup_fail:
            raise Exception("Failed to setup.")

        self.setup_run = True

    def record_table_definitions(self, meta_table_name):
        if self.record_fail:
            raise Exception("Failed to record table definitions")
        self.record_run = True

    def historian_teardown(self):
        if self.teardown_fail:
            raise Exception("Failed to teardown.")

        self.teardown_run = True


@pytest.mark.historian
def test_failing_historian(request, volttron_instance, client_agent):
    """
    Test basic use of health subsystem in the base historian.
    """
    fail_historian = None

    try:
        identity = 'platform.historian'
        fail_historian = volttron_instance.build_agent(agent_class=FailureHistorian,
                                              identity=identity,
                                              submit_size_limit=2,
                                              max_time_publishing=0.5,
                                              retry_period=1.0,
                                              backup_storage_limit_gb=0.0001)  # 100K

        assert fail_historian.setup_run
        assert not fail_historian.teardown_run
        assert fail_historian._process_thread.is_alive()

        fail_historian.stop_process_thread()
        gevent.sleep(1)
        assert fail_historian.teardown_run
        assert fail_historian.setup_run
        assert fail_historian._process_thread is None
        ###
        # Test setup failure case
        ###
        fail_historian.reset()
        fail_historian.setup_fail = True
        fail_historian.start_process_thread()
        gevent.sleep(0.2)

        assert fail_historian._process_thread.is_alive()
        assert not fail_historian.setup_run
        assert not fail_historian.teardown_run

        fail_historian.stop_process_thread()

        assert fail_historian.teardown_run
        assert not fail_historian.setup_run
        assert fail_historian._process_thread is None
        ###
        # Test failure to record intial table names in db
        ###
        fail_historian.reset()
        fail_historian.record_fail = True
        fail_historian.start_process_thread()

        gevent.sleep(0.2)

        assert fail_historian._process_thread.is_alive()
        assert fail_historian.setup_run
        assert not fail_historian.record_run
        assert not fail_historian.teardown_run

        fail_historian.stop_process_thread()

        assert fail_historian.teardown_run
        assert fail_historian.setup_run
        assert not fail_historian.record_run
        assert fail_historian._process_thread is None
        ###
        # Test failure during teardown
        ###
        fail_historian.reset()
        fail_historian.teardown_fail = True
        fail_historian.start_process_thread()

        gevent.sleep(0.2)

        assert fail_historian._process_thread.is_alive()
        assert fail_historian.setup_run
        assert not fail_historian.teardown_run

        fail_historian.stop_process_thread()

        assert not fail_historian.teardown_run
        assert fail_historian.setup_run
        assert fail_historian._process_thread is None

        fail_historian.reset()
        fail_historian.publish_fail = True
        fail_historian.start_process_thread()

        gevent.sleep(0.2)

        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

        print("\n** test_basic_function for {}**".format(
            request.keywords.node.name))

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': 32},
                       {'OutsideAirTemperature': float_meta}]

        # Create timestamp
        now = utils.format_timestamp( datetime.utcnow() )

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        client_agent.vip.pubsub.publish('pubsub',
                                         DEVICES_ALL_TOPIC,
                                         headers=headers,
                                         message=all_message).get(timeout=10)

        gevent.sleep(2.0)
        assert fail_historian._process_thread.is_alive()
        assert not fail_historian.seen
        ###
        # Test if historian recovers when setup fails initially but is successful
        # after sometime. This is to test case where db is down when historian
        # is first started and db is brought back up. Historian should recover
        # without restart.
        ###
        fail_historian.stop_process_thread()
        fail_historian.reset()
        fail_historian.setup_fail = True
        fail_historian.start_process_thread()

        gevent.sleep(0.2)

        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

        print("\n** test_basic_function for {}**".format(
            request.keywords.node.name))

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': 32},
                       {'OutsideAirTemperature': float_meta}]

        # Create timestamp
        now = utils.format_timestamp(datetime.utcnow())

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        client_agent.vip.pubsub.publish('pubsub',
                                        DEVICES_ALL_TOPIC,
                                        headers=headers,
                                        message=all_message).get(timeout=10)

        gevent.sleep(6.0)
        assert fail_historian._process_thread.is_alive()
        assert not fail_historian.seen

        # now setup fail is false. publish again and see if we recover
        fail_historian.setup_fail = False

        # Create timestamp
        now = utils.format_timestamp(datetime.utcnow())

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        client_agent.vip.pubsub.publish('pubsub',
                                        DEVICES_ALL_TOPIC,
                                        headers=headers,
                                        message=all_message).get(timeout=20)

        gevent.sleep(2.0)
        assert fail_historian._process_thread.is_alive()
        assert fail_historian.setup_run
        assert fail_historian.record_run
        assert len(fail_historian.seen)
        print(fail_historian.seen)
    finally:
        # Stop agent as this might keep publishing backlogged message if left running.
        # This may cause test case right after this to timeout
        if fail_historian:
            fail_historian.core.stop()
        # wait for cleanup to complete
        gevent.sleep(2)


@pytest.mark.historian
def test_additional_custom_topics(request, volttron_instance, client_agent):
    """
    Test subscription to custom topics. Test --
     1. add additional topics
     2. restricting topics
    """
    global alert_publishes
    historian = None
    try:
        identity = 'platform.historian'
        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"
        CUSTOM_TOPIC = 'special_devices/device1/unit/all'
        CUSTOM_QUERY_TOPIC = "device1/unit"
        DEVICES_QUERY_TOPIC = "Building/LAB/Device"

        historian = volttron_instance.build_agent(agent_class=BasicHistorian,
                                              identity=identity,
                                              submit_size_limit=2,
                                              max_time_publishing=0.5,
                                              retry_period=1.0,
                                              backup_storage_limit_gb=0.0001,
                                              custom_topics={'capture_device_data': [CUSTOM_TOPIC]})  # 100K


        print("\n** test_basic_function for {}**".format(
            request.keywords.node.name))

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings.  Randome readings are going to be
        # within the tolerance here.
        format_spec = "{0:.13f}"
        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)
        damper_reading = random.uniform(0, 100)

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
        percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Create timestamp
        now = utils.format_timestamp( datetime.utcnow() )

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        for _ in range(2):
            client_agent.vip.pubsub.publish('pubsub',
                                             DEVICES_ALL_TOPIC,
                                             headers=headers,
                                             message=all_message).get(timeout=10)
        for _ in range(2):
            client_agent.vip.pubsub.publish('pubsub',
                                            CUSTOM_TOPIC,
                                            headers=headers,
                                            message=all_message).get(timeout=10)

        gevent.sleep(1.0)

        assert len(historian.seen) == 12
        found_device_topic = 0
        found_custom_topic = 0
        for item in historian.seen:
            if item["topic"].startswith(DEVICES_QUERY_TOPIC) :
                found_device_topic += 1
            elif item["topic"].startswith(CUSTOM_QUERY_TOPIC):
                found_custom_topic += 1
        assert found_custom_topic == 6
        assert found_device_topic == 6
    finally:
        if historian:
            historian.core.stop()
        # wait for cleanup to complete
        gevent.sleep(2)


@pytest.mark.historian
def test_restricting_topics(request, volttron_instance, client_agent):
    """
    Test subscription to custom topics. Test --
     1. add additional topics
     2. restricting topics
    """
    global alert_publishes
    historian = None
    try:
        identity = 'platform.historian'
        CUSTOM_TOPIC = 'devices/device1/unit/all'
        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"
        CUSTOM_QUERY_TOPIC  = "device1/unit"
        DEVICES_QUERY_TOPIC = "Building/LAB/Device"

        historian = volttron_instance.build_agent(agent_class=BasicHistorian,
                                              identity=identity,
                                              submit_size_limit=2,
                                              max_time_publishing=0.5,
                                              retry_period=1.0,
                                              backup_storage_limit_gb=0.0001,
                                              capture_device_data=False,
                                              capture_log_data=False,
                                              capture_analysis_data=False,
                                              capture_record_data=False,
                                              custom_topics={'capture_device_data': [CUSTOM_TOPIC]})  # 100K

        print("\n** test_basic_function for {}**".format(
            request.keywords.node.name))

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings.  Randome readings are going to be
        # within the tolerance here.
        format_spec = "{0:.13f}"
        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)
        damper_reading = random.uniform(0, 100)

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
        percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Create timestamp
        now = utils.format_timestamp( datetime.utcnow() )

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        for _ in range(2):
            client_agent.vip.pubsub.publish('pubsub',
                                             DEVICES_ALL_TOPIC,
                                             headers=headers,
                                             message=all_message).get(timeout=10)
        for _ in range(2):
            client_agent.vip.pubsub.publish('pubsub',
                                            CUSTOM_TOPIC,
                                            headers=headers,
                                            message=all_message).get(timeout=10)

        gevent.sleep(2.0)

        assert len(historian.seen) == 6  # only records published to custom topic
        found_device_topic = 0
        found_custom_topic = 0
        for item in historian.seen:
            if item["topic"].startswith(DEVICES_QUERY_TOPIC):
                found_device_topic += 1
            elif item["topic"].startswith(CUSTOM_QUERY_TOPIC):
                found_custom_topic += 1
        assert found_custom_topic == 6
        assert found_device_topic == 0
    finally:
        if historian:
            historian.core.stop()
        # wait for cleanup to complete
        gevent.sleep(2)
