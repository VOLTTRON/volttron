from datetime import datetime
import random
import tempfile

import gevent
import pytest
from zmq.utils import jsonapi

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore

FORWARDER_1 = {
    "agentid": "forwarder",
    "destination-vip": {},
    "custom_topic_list": [],
    "services_topic_list": [
        "devices", "analysis", "record", "datalogger", "actuators"
    ],
    "topic_replace_list": [
        {"from": "PNNL/BUILDING_1", "to": "PNNL/BUILDING1_ANON"}
    ]
}

# Module level variables
ALL_TOPIC = "devices/Building/LAB/Device/all"
query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}


allforwardedmessage = None


def do_publish(agent1):
    # Publish fake data. The format mimics the format used by VOLTTRON
    # drivers.
    # Make some random readings
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
    now = datetime.utcnow().isoformat(' ')

    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }
    print("Published time in header: " + now)
    # Publish messages
    agent1.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(1)


def onmessage(peer, sender, bus, topic, headers, message):
    global allforwardedmessage
    allforwardedmessage = message
    # print('received: peer=%r, sender=%r, bus=%r, topic=%r, headers=%r, message=%r' % (
    #         peer, sender, bus, topic, headers, message))


@pytest.mark.historian
def test_forwarding(volttron_instance1_encrypt, volttron_instance2_encrypt):
    global FORWARDER_1
    tf = tempfile.NamedTemporaryFile()
    tf2 = tempfile.NamedTemporaryFile()
    tf3 = tempfile.NamedTemporaryFile()
    ks = KeyStore(tf.name)
    ks.generate()
    ks2 = KeyStore(tf2.name)
    ks2.generate()
    ks3 = KeyStore(tf2.name)
    ks3.generate()

    wrap1 = volttron_instance1_encrypt
    wrap2 = volttron_instance2_encrypt

    authfile1 = AuthFile(wrap1.volttron_home+"/auth.json")
    entry1 = AuthEntry(
        credentials="CURVE:{}".format(ks3.public())
    )
    authfile1.add(entry1)

    authfile = AuthFile(wrap2.volttron_home+"/auth.json")
    entry = AuthEntry(
        credentials="CURVE:{}".format(ks.public()))
    authfile.add(entry)
    entry = AuthEntry(
        credentials="CURVE:{}".format(ks2.public()))
    authfile.add(entry)

    forward_to_vip = "{}?serverkey={}&publickey={}&secretkey={}".format(
        wrap2.vip_address, wrap2.publickey, ks.public(), ks.secret()
    )

    FORWARDER_1["destination-vip"] = forward_to_vip
    forwarder_config = FORWARDER_1
    print("THE CONFIG = {}".format(forwarder_config))

    wrap1.install_agent(
        agent_dir="services/core/ForwardHistorian",
        config_file=forwarder_config
    )

    connect_to_wrap2 = "{}?serverkey={}&publickey={}&secretkey={}".format(
        wrap2.vip_address, wrap2.publickey, ks2.public(), ks2.secret()
    )

    connect_to_wrap1 = "{}?serverkey={}&publickey={}&secretkey={}".format(
        wrap1.vip_address, wrap1.publickey, ks3.public(), ks3.secret()
    )

    agent_connected1 = wrap1.build_agent(address=connect_to_wrap1)
    agent_connected2 = wrap2.build_agent(address=connect_to_wrap2)

    message = ''
    agent_connected2.vip.pubsub.subscribe('pubsub', '', callback=onmessage)
    gevent.sleep(0.2)

    do_publish(agent1=agent_connected1)
    gevent.sleep(1)
    assert allforwardedmessage


