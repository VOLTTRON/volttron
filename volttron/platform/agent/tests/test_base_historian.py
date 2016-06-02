import os
import shutil
import sqlite3
import json

import gevent
from zmq.utils import jsonapi

from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.base_historian import BaseHistorian
import pytest

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
    master_uuid = v1.install_agent(agent_dir="services/core/MasterDriverAgent",
                                   config_file=master_config)
    gevent.sleep(2)

    db = Historian(address=v1.vip_address[0],
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
