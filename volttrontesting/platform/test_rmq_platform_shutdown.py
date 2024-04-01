# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import psutil
import gevent
import pytest
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip, build_wrapper
from volttron.platform import get_examples
from volttron.platform.agent.utils import execute_command
from volttron.platform import is_rabbitmq_available
if is_rabbitmq_available():
    from volttron.utils.rmq_setup import stop_rabbit
    from volttron.utils.rmq_config_params import RMQConfig
else:
    pytest.skip("Pika is not installed", allow_module_level=True)

pytestmark = [pytest.mark.xfail]


pytestmark = [pytest.mark.xfail]


@pytest.mark.rmq_shutdown
def test_vctl_shutdown_on_rmq_stop(request):
    """
    Test for fix issue# 1886
    :param volttron_instance_rmq:
    :return:
    """
    address = get_rand_vip()
    volttron_instance = build_wrapper(address,
                                      messagebus='rmq',
                                      ssl_auth=True)
    agent_uuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=True)
    assert agent_uuid is not None

    agent_pid = volttron_instance.agent_pid(agent_uuid)
    assert agent_pid is not None and agent_pid > 0

    # Stop RabbitMQ server
    rmq_cfg = RMQConfig()
    stop_rabbit(rmq_home=rmq_cfg.rmq_home, env=volttron_instance.env)

    gevent.sleep(5)
    # Shtudown platform
    cmd = ['volttron-ctl', 'shutdown', '--platform']
    execute_command(cmd, env=volttron_instance.env)
    gevent.sleep(2)
    # Check that installed agent and platform is not running
    assert not psutil.pid_exists(agent_pid)
    assert volttron_instance.is_running() == False
