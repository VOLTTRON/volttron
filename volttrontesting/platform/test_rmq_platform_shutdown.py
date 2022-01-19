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

import psutil
import gevent
import pytest
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip, build_wrapper
from volttron.platform import get_examples
from volttron.platform.agent.utils import execute_command
from volttron.utils.rmq_setup import stop_rabbit
from volttron.utils.rmq_config_params import RMQConfig

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
