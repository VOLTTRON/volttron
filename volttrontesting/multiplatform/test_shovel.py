# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
pytest test cases base historian to test all_platform configuration.
By default all_platform is set to False and historian subscribes only to topics from local message bus.
When all_platforms=True, historian will subscribe to topics from all connected platforms

"""

import gevent
import pytest
from urllib.parse import urlparse
import os

from volttron.platform import get_examples
from volttron.platform.agent.known_identities import CONTROL
from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper
from volttrontesting.utils.utils import get_hostname_and_random_port, get_rand_vip, get_rand_ip_and_port
from volttron.utils import rmq_mgmt
from volttrontesting.utils.platformwrapper import with_os_environ
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttron.utils.rmq_setup import start_rabbit


@pytest.fixture(scope="module")
def shovel_pubsub_rmq_instances(request, **kwargs):
    """
    Create two rmq based volttron instances. One to act as producer of data and one to act as consumer of data
    Create a shovel to forward data from producer to consumer

    :return: 2 volttron instances - (producer, consumer) that have a shovel connection between them
    """
    source_vip = get_rand_vip()
    source_hostname, source_https_port = get_hostname_and_random_port()
    source_web_address = 'https://{hostname}:{port}'.format(hostname=source_hostname, port=source_https_port)
    source_instance_name = 'volttron1'
    source = build_wrapper(source_vip,
                           ssl_auth=True,
                           messagebus='rmq',
                           should_start=False,
                           bind_web_address=source_web_address,
                           instance_name=source_instance_name,
                           **kwargs)

    sink_vip = get_rand_vip()
    sink_hostname, sink_https_port = get_hostname_and_random_port()
    sink_web_address = 'https://{hostname}:{port}'.format(hostname=sink_hostname, port=sink_https_port)
    sink = build_wrapper(sink_vip,
                         ssl_auth=True,
                         messagebus='rmq',
                         should_start=True,
                         bind_web_address=sink_web_address,
                         instance_name='volttron2',
                         **kwargs)

    sink.enable_auto_csr()
    link_name = None
    try:
        # create shovel config and save in volttron home of 'source' instance
        pubsub_config = dict()
        pubsub_config['dynamic_agent'] = 'test'
        shovel_user = '{source_instance}.shovel{sink_host}'.format(source_instance=source_instance_name,
                                                                   sink_host=sink_hostname)
        config_path = create_shovel_config(source.volttron_home,
                                           sink.rabbitmq_config_obj.rabbitmq_config["host"],
                                           sink.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
                                           sink_https_port,
                                           sink.rabbitmq_config_obj.rabbitmq_config["virtual-host"],
                                           shovel_user,
                                           pubsub_config=pubsub_config)

        # setup shovel from 'source' to 'sink'
        source.setup_shovel(config_path)
        source.startup_platform(vip_address=source_vip, bind_web_address=source_web_address)
        with with_os_environ(source.env):
            rmq_mgmt = RabbitMQMgmt()
            links = rmq_mgmt.get_shovel_links()
            assert links and links[0]['state'] == 'running'
            link_name = links[0]['name']

    except Exception as e:
        print("Exception setting up shovel: {}".format(e))
        source.shutdown_platform()
        sink.shutdown_platform()
        raise e

    yield source, sink
    if link_name:
        rmq_mgmt.delete_multiplatform_parameter('shovel', link_name)
    source.shutdown_platform()
    sink.shutdown_platform()


def create_shovel_config(vhome, host, port, https_port, vhost, shover_user, pubsub_config=None, rpc_config=None):
    content = dict()
    shovel = dict()
    shovel[host] = {'https-port': https_port,
                    'port': port,
                    'shovel-user': shover_user,
                    'virtual-host': vhost,
                    }
    if pubsub_config:
        shovel[host]['pubsub'] = pubsub_config
    if rpc_config:
        shovel[host]['rpc'] = rpc_config
    content['shovel'] = shovel

    import yaml
    config_path = os.path.join(vhome, "rabbitmq_shovel_config.yml")
    print(f"config_path: {config_path}")
    with open(config_path, 'w') as yaml_file:
        yaml.dump(content, yaml_file, default_flow_style=False)
    return config_path


@pytest.fixture(scope="module")
def two_way_shovel_connection(request, **kwargs):
    """
    Create two rmq based volttron instances. Create bi-directional data flow channel
    by adding 2 shovel connections

    :return: 2 volttron instances - connected through shovels
    """
    source_vip = get_rand_vip()
    source_hostname, source_https_port = get_hostname_and_random_port()
    source_web_address = 'https://{hostname}:{port}'.format(hostname=source_hostname, port=source_https_port)
    source_instance_name = 'volttron1'
    source = build_wrapper(source_vip,
                           ssl_auth=True,
                           messagebus='rmq',
                           should_start=False,
                           bind_web_address=source_web_address,
                           instance_name=source_instance_name,
                           **kwargs)

    sink_vip = get_rand_vip()
    sink_hostname, sink_https_port = get_hostname_and_random_port()
    sink_web_address = 'https://{hostname}:{port}'.format(hostname=sink_hostname, port=sink_https_port)
    sink_instance_name = 'volttron2'
    sink = build_wrapper(sink_vip,
                         ssl_auth=True,
                         messagebus='rmq',
                         should_start=True,
                         bind_web_address=sink_web_address,
                         instance_name=sink_instance_name,
                         **kwargs)

    sink.enable_auto_csr()
    source_link_name = None
    try:
        # create shovel config and save in volttron home of 'source' instance
        source_shovel_user = '{source_instance}.shovel{sink_host}'.format(source_instance=source_instance_name,
                                                                          sink_host=sink_hostname)
        rpc_config = dict()
        rpc_config[sink_instance_name] = [['dynamic_agent', CONTROL]]
        config_path = create_shovel_config(source.volttron_home,
                                           sink.rabbitmq_config_obj.rabbitmq_config["host"],
                                           sink.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
                                           sink_https_port,
                                           sink.rabbitmq_config_obj.rabbitmq_config["virtual-host"],
                                           source_shovel_user,
                                           rpc_config=rpc_config)

        # setup shovel from 'source' to 'sink'
        source.setup_shovel(config_path)
        source.startup_platform(vip_address=source_vip, bind_web_address=source_web_address)
        source.enable_auto_csr()

        # Check shovel link status
        with with_os_environ(source.env):
            rmq_mgmt = RabbitMQMgmt()
            links = rmq_mgmt.get_shovel_links()
            assert links and links[0]['state'] == 'running'
            source_link_name = links[0]['name']

        sink.skip_cleanup = True
        sink.shutdown_platform()
        sink.skip_cleanup = False

        # Start RabbitMQ broker to establish shovel link
        start_rabbit(rmq_home=sink.rabbitmq_config_obj.rmq_home, env=sink.env)

        rpc_config = dict()
        rpc_config[source_instance_name] = [[CONTROL, 'dynamic_agent']]
        sink_shovel_user = '{source_instance}.shovel{sink_host}'.format(source_instance=sink_instance_name,
                                                                        sink_host=source_hostname)

        config_path = create_shovel_config(sink.volttron_home,
                                           source.rabbitmq_config_obj.rabbitmq_config["host"],
                                           source.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
                                           source_https_port,
                                           source.rabbitmq_config_obj.rabbitmq_config["virtual-host"],
                                           sink_shovel_user,
                                           rpc_config=rpc_config)

        sink.setup_shovel(config_path)
        sink.startup_platform(vip_address=sink_vip, bind_web_address=sink_web_address)

        # Check shovel link status
        with with_os_environ(sink.env):
            rmq_mgmt = RabbitMQMgmt()
            links = rmq_mgmt.get_shovel_links()
            assert links and links[0]['state'] == 'running'
            sink_link_name = links[0]['name']

    except Exception as e:
        print("Exception setting up shovel: {}".format(e))
        source.shutdown_platform()
        sink.shutdown_platform()
        raise e

    yield source, sink
    if source_link_name:
        with with_os_environ(source.env):
            rmq_mgmt = RabbitMQMgmt()
            rmq_mgmt.delete_multiplatform_parameter('shovel', source_link_name)
    if sink_link_name:
        with with_os_environ(sink.env):
            rmq_mgmt = RabbitMQMgmt()
            rmq_mgmt.delete_multiplatform_parameter('shovel', sink_link_name)
    source.shutdown_platform()
    sink.shutdown_platform()


@pytest.mark.shovel
def test_shovel_pubsub(shovel_pubsub_rmq_instances):
    source, sink = shovel_pubsub_rmq_instances
    assert source.is_running()
    assert sink.is_running()

    subscription_results2 = {}
    publisher = source.dynamic_agent
    subscriber = sink.dynamic_agent

    def callback2(peer, sender, bus, topic, headers, message):
        subscription_results2[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results2[topic]))

    subscriber.vip.pubsub.subscribe(peer='pubsub',
                                    prefix='test/campus/building1',
                                    callback=callback2,
                                    all_platforms=True)

    gevent.sleep(1)
    for i in range(5):
        publisher.vip.pubsub.publish(peer='pubsub', topic='test/campus/building1', message=[{'point': 'value'}])
        gevent.sleep(1)
        message = subscription_results2['test/campus/building1']['message']
        assert message == [{'point': 'value'}]


@pytest.mark.shovel
def test_shovel_rpc(two_way_shovel_connection):
    instance_1, instance_2 = two_way_shovel_connection
    assert instance_1.is_running()
    assert instance_2.is_running()

    auuid = None
    try:
        auuid = instance_2.install_agent(vip_identity='listener',
                                         agent_dir=get_examples("ListenerAgent"),
                                         start=True)

        assert auuid is not None
        test_agent = instance_1.dynamic_agent
        kwargs = {"external_platform": instance_2.instance_name}
        agts = test_agent.vip.rpc.call(CONTROL,
                                       'list_agents',
                                       **kwargs).get(timeout=10)

        assert agts[0]['identity'].startswith('listener')
        listener_uuid = agts[0]['uuid']
        test_agent.vip.rpc.call(CONTROL,
                                'stop_agent',
                                listener_uuid,
                                **kwargs).get(timeout=10)
        agt_status = test_agent.vip.rpc.call(CONTROL,
                                'agent_status',
                                listener_uuid,
                                **kwargs).get(timeout=10)
        assert agt_status[1] == 0
    finally:
        if instance_2 and auuid:
            instance_2.remove_agent(auuid)
