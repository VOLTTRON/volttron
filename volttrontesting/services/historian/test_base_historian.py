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

import shutil
import json


from volttron.platform import get_services_core

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

class Historian(BaseHistorian):
    def publish_to_historian(self,_):
        pass
    def query_topic_list(self):
        pass
    def query_historian(self):
        pass


def prep_config(volttron_home):
    src_driver = os.getcwd() + '/services/core/MasterDriverAgent/master_driver/test_fakedriver.config'
    new_driver = volttron_home + '/test_fakedriver.config'
    shutil.copy(src_driver, new_driver)

    with open(new_driver, 'r+') as f:
        config = json.load(f)
        config['registry_config'] = os.getcwd() + '/services/core/MasterDriverAgent/master_driver/fake.csv'
        f.seek(0)
        f.truncate()
        json.dump(config, f)

    master_config = {
        "agentid": "master_driver",
        "driver_config_list": [new_driver]
    }

    return master_config


foundtopic = False
def listener(peer, sender, bus, topic, headers, message):
    global foundtopic
    foundtopic = True


@pytest.mark.xfail(reason="This won't work on all machines because of hardcoded paths.")
def test_base_historian(volttron_instance):
    global foundtopic
    v1 = volttron_instance
    assert v1.is_running()

    master_config = prep_config(v1.volttron_home)
    master_uuid = v1.install_agent(agent_dir=get_services_core("MasterDriverAgent"),
                                   config_file=master_config)
    gevent.sleep(2)

    db = Historian({}, address=v1.vip_address[0],
                   backup_storage_limit_gb=0.00002)
    gevent.spawn(db.core.run).join(0)

    agent = v1.build_agent()
    gevent.sleep(2)
    agent.vip.pubsub.subscribe('pubsub' ,'backupdb/nomore', callback=listener)

    for _ in range(0, 60):
        gevent.sleep(1)
        if foundtopic:
            break

    assert foundtopic


class BasicHistorian(BaseHistorian):
    '''
    This historian forwards data to another platform.
    '''
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

@pytest.fixture(scope="module")
def historian(request, volttron_instance):
    identity = 'platform.historian'
    agent = volttron_instance.build_agent(agent_class=BasicHistorian,
                                          identity=identity,
                                          submit_size_limit=2,
                                          max_time_publishing=0.5,
                                          retry_period=1.0,
                                          backup_storage_limit_gb=0.0001)  # 100K
    yield agent
    agent.core.stop()

alert_publishes = []

def message_handler(peer, sender, bus,  topic, headers, message):
    alert_publishes.append(Status.from_json(message))

@pytest.mark.historian
def test_health_stuff(request, historian, client_agent):
    """
    Test basic use of health subsystem in the base historian.
    """
    global alert_publishes

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
    now = utils.format_timestamp( datetime.utcnow() )

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


    gevent.sleep(0.2)

    status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

    alert_publish = alert_publishes[0]

    alert_publishes = []

    assert status["status"] == STATUS_BAD
    assert not status["context"][STATUS_KEY_PUBLISHING]

    assert alert_publish.status == STATUS_BAD

    historian.publish_fail = False

    gevent.sleep(1.0)

    status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

    assert status["status"] == STATUS_GOOD
    assert status["context"][STATUS_KEY_PUBLISHING]
    assert not status["context"][STATUS_KEY_BACKLOGGED]
    assert not status["context"][STATUS_KEY_CACHE_FULL]
    assert not bool(status["context"][STATUS_KEY_CACHE_COUNT])

    #Test publish slow or backlogged

    historian.publish_sleep = 0.75

    for _ in range(1000):
        client_agent.vip.pubsub.publish('pubsub',
                                        DEVICES_ALL_TOPIC,
                                        headers=headers,
                                        message=all_message).get(timeout=10)

    gevent.sleep(2.0)

    status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

    assert status["status"] == STATUS_BAD
    assert status["context"][STATUS_KEY_BACKLOGGED]
    assert status["context"][STATUS_KEY_CACHE_COUNT] > 0
    alert_publish = alert_publishes[-1]
    assert alert_publish.status == STATUS_BAD
    context = alert_publish.context
    assert context[STATUS_KEY_CACHE_FULL]
    assert status["context"][STATUS_KEY_CACHE_FULL]

    historian.publish_sleep = 0

    gevent.sleep(2.0)

    status = client_agent.vip.rpc.call("platform.historian", "health.get_status").get(timeout=10)

    assert status["status"] == STATUS_GOOD
    assert status["context"][STATUS_KEY_PUBLISHING]
    assert not status["context"][STATUS_KEY_BACKLOGGED]
    assert not status["context"][STATUS_KEY_CACHE_FULL]
    assert not bool(status["context"][STATUS_KEY_CACHE_COUNT])
