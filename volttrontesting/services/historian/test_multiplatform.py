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

import os
import random
from datetime import datetime

import gevent
import pytest

from volttron.platform import get_services_core, jsonapi
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper
from volttrontesting.utils.utils import get_rand_vip, get_hostname_and_random_port
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip, \
    get_rand_ip_and_port
from volttron.utils.rmq_setup import start_rabbit, stop_rabbit
from volttron.platform.agent.utils import execute_command


@pytest.fixture(scope="module")
def federated_rmq_instances(request, **kwargs):
    """
    Create two rmq based volttron instances. One to act as producer of data and one to act as consumer of data

    :return: 2 volttron instances - (producer, consumer) that are federated
    """
    upstream_vip = get_rand_vip()
    upstream = build_wrapper(upstream_vip,
                             ssl_auth=True,
                             messagebus='rmq',
                             should_start=False,
                             **kwargs)

    downstream_vip = get_rand_vip()
    downstream = build_wrapper(downstream_vip,
                               ssl_auth=True,
                               messagebus='rmq',
                               should_start=False,
                               **kwargs)

    # exchange CA certs
    stop_rabbit(rmq_home=upstream.rabbitmq_config_obj.rmq_home, env=upstream.env, quite=True)
    stop_rabbit(rmq_home=downstream.rabbitmq_config_obj.rmq_home, env=downstream.env, quite=True)

    with open(os.path.join(upstream.certsobj.cert_dir, upstream.instance_name + "-root-ca.crt"), "r") as uf:
        with open(os.path.join(downstream.certsobj.cert_dir, downstream.instance_name + "-trusted-cas.crt"), "a") as df:
            df.write(uf.read())

    with open(os.path.join(downstream.certsobj.cert_dir, downstream.instance_name + "-root-ca.crt"), "r") as df:
        with open(os.path.join(upstream.certsobj.cert_dir, upstream.instance_name + "-trusted-cas.crt"), "a") as uf:
            uf.write(df.read())

    start_rabbit(rmq_home=downstream.rabbitmq_config_obj.rmq_home, env=downstream.env)
    gevent.sleep(1)
    start_rabbit(rmq_home=upstream.rabbitmq_config_obj.rmq_home, env=upstream.env)
    gevent.sleep(1)

    try:

        # add downstream user ON UPSTREAM and give permissions
        # ~/rabbitmq_server/rabbitmq_server-3.7.7/sbin/rabbitmqctl add_user <user> <password>
        # ~/rabbitmq_server/rabbitmq_server-3.7.7/sbin/rabbitmqctl set_permissions -p <vhost> <user> ".*" ".*" ".*"
        cmd = [os.path.join(upstream.rabbitmq_config_obj.rmq_home, "sbin/rabbitmqctl")]
        cmd.extend(['add_user', downstream.instance_name + "-admin", "test"])
        execute_command(cmd, env=upstream.env, err_prefix="Error creating user in upstream server")

        cmd = [os.path.join(upstream.rabbitmq_config_obj.rabbitmq_config['rmq-home'], "sbin/rabbitmqctl")]
        cmd.extend(['set_permissions', "-p", upstream.rabbitmq_config_obj.rabbitmq_config["virtual-host"]])
        cmd.extend([downstream.instance_name + "-admin", ".*", ".*", ".*"])
        execute_command(cmd, env=upstream.env, err_prefix="Error setting user permission in upstream server")
        gevent.sleep(1)

        upstream.startup_platform(upstream_vip)
        gevent.sleep(2)
        print("After upstream start")
        downstream.startup_platform(downstream_vip)
        gevent.sleep(2)

        # create federation config and setup federation
        content = """federation-upstream:
        {host}:
            port: {port}
            virtual-host: {vhost}
        """

        config_path = os.path.join(downstream.volttron_home, "federation.config")
        with open(config_path, 'w') as conf:
            conf.write(content.format(host=upstream.rabbitmq_config_obj.rabbitmq_config["host"],
                                      port=upstream.rabbitmq_config_obj.rabbitmq_config["amqp-port-ssl"],
                                      vhost=upstream.rabbitmq_config_obj.rabbitmq_config["virtual-host"]))
        downstream.setup_federation(config_path)

    except Exception as e:
        print("Exception setting up federation: {}".format(e))
        upstream.shutdown_platform()
        downstream.shutdown_platform()
        raise e

    yield upstream, downstream

    upstream.shutdown_platform()
    downstream.shutdown_platform()


@pytest.fixture(scope="module")
def get_zmq_volttron_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. The fixture also
    takes care of shutting down all the instances at the end

    Example Usage:

    def test_function_that_uses_n_instances(get_volttron_instances):
        instance1, instance2, instance3 = get_volttron_instances(3)

    @param request: pytest request object
    @return: function that can used to get any number of
        volttron instances for testing.
    """
    all_instances = []

    def get_n_volttron_instances(n, should_start=True, address_file=True):
        get_n_volttron_instances.count = n
        vip_addresses = []
        web_addresses = []
        instances = []
        names = []

        for i in range(0, n):
            address = get_rand_vip()
            web_address = "http://{}".format(get_rand_ip_and_port())
            vip_addresses.append(address)
            web_addresses.append(web_address)
            nm = 'platform{}'.format(i + 1)
            names.append(nm)

        for i in range(0, n):
            address = vip_addresses[i]
            web_address = web_addresses[i]
            wrapper = PlatformWrapper(messagebus='zmq', ssl_auth=False)

            addr_file = os.path.join(wrapper.volttron_home, 'external_address.json')
            if address_file:
                with open(addr_file, 'w') as f:
                    jsonapi.dump(web_addresses, f)
                    gevent.sleep(0.5)
            wrapper.startup_platform(address, bind_web_address=web_address, setupmode=True)
            wrapper.skip_cleanup = True
            instances.append(wrapper)

        gevent.sleep(11)
        for i in range(0, n):
            instances[i].shutdown_platform()

        gevent.sleep(1)
        # del instances[:]
        for i in range(0, n):
            address = vip_addresses.pop(0)
            web_address = web_addresses.pop(0)
            print(address, web_address)
            instances[i].startup_platform(address, bind_web_address=web_address)
            instances[i].allow_all_connections()
        gevent.sleep(11)
        instances = instances if n > 1 else instances[0]

        get_n_volttron_instances.instances = instances
        return instances

    return get_n_volttron_instances


@pytest.mark.historian
@pytest.mark.multiplatform
def test_all_platform_subscription_zmq(request, get_zmq_volttron_instances):

    upstream, downstream, downstream2 = get_zmq_volttron_instances(3)

    gevent.sleep(5)

    # setup consumer on downstream1. One with all_platform=True another False

    hist_config = {"connection":
                       {"type": "sqlite",
                        "params": {
                            "database": downstream.volttron_home +
                                        "/historian.sqlite"}},
                   "all_platforms": True
                   }
    hist_id = downstream.install_agent(
        vip_identity='platform.historian',
        agent_dir=get_services_core("SQLHistorian"),
        config_file=hist_config,
        start=True)
    gevent.sleep(3)
    query_agent = downstream.build_agent(identity="query_agent1")
    gevent.sleep(1)

    hist2_config = {"connection":
                        {"type": "sqlite",
                         "params": {
                             "database": downstream2.volttron_home +
                                         "/historian2.sqlite"}},
                    }
    hist2_id = downstream2.install_agent(
        vip_identity='unused.historian',
        agent_dir=get_services_core("SQLHistorian"),
        config_file=hist2_config,
        start=True)
    query_agent2 = downstream2.build_agent(identity="query_agent2")
    gevent.sleep(2)

    print("publish")

    producer = upstream.build_agent(identity="producer")
    gevent.sleep(2)
    DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

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

    producer.vip.pubsub.publish('pubsub',
                                DEVICES_ALL_TOPIC,
                                headers=headers,
                                message=all_message).get(timeout=10)

    gevent.sleep(5)

    ## Query from consumer to verify

    result = query_agent.vip.rpc.call("platform.historian",
                                      'query',
                                      topic="Building/LAB/Device/OutsideAirTemperature",
                                      count=1).get(timeout=100)
    print("QUERY RESULT : {}" .format(result))
    assert (result['values'][0][1] == oat_reading)
    assert set(result['metadata'].items()) == set(float_meta.items())
    gevent.sleep(1)

    result = query_agent2.vip.rpc.call("unused.historian",
                                       'query',
                                       topic="Building/LAB/Device/OutsideAirTemperature",
                                       count=1).get(timeout=100)
    print("QUERY RESULT : {}".format(result))
    assert not result

    downstream.remove_agent(hist_id)
    downstream2.remove_agent(hist2_id)
    query_agent.core.stop()
    query_agent2.core.stop()
    producer.core.stop()
    gevent.sleep(1)
    upstream.shutdown_platform()
    downstream.shutdown_platform()
    downstream2.shutdown_platform()


@pytest.mark.historian
@pytest.mark.multiplatform
def test_all_platform_subscription_rmq(request, federated_rmq_instances):
    try:
        upstream, downstream = federated_rmq_instances
        assert upstream.is_running()
        assert downstream.is_running()

        # setup consumer on downstream1. One with all_platform=True another False

        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": downstream.volttron_home +
                                            "/historian.sqlite"}},
                       "all_platforms": True
                       }
        hist_id = downstream.install_agent(
            vip_identity='platform.historian.rmq',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)

        assert downstream.is_running()
        assert downstream.is_agent_running(hist_id)
        query_agent = downstream.dynamic_agent
        gevent.sleep(2)

        print("publish")
        producer = upstream.dynamic_agent
        gevent.sleep(2)
        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

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

        producer.vip.pubsub.publish('pubsub',
                                    DEVICES_ALL_TOPIC,
                                    headers=headers,
                                    message=all_message).get(timeout=10)
        gevent.sleep(5)

        ## Query from consumer to verify

        result = query_agent.vip.rpc.call("platform.historian.rmq",
                                          'query',
                                          topic="Building/LAB/Device/OutsideAirTemperature",
                                          count=1).get(timeout=100)
        print("QUERY RESULT : {}".format(result))
        assert (result['values'][0][1] == oat_reading)
        assert set(result['metadata'].items()) == set(float_meta.items())
        gevent.sleep(1)
    finally:
        if downstream:
            downstream.remove_agent(hist_id)

