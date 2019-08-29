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
Test cases to test volttron platform with rmq and ssl auth.

"""
import datetime
import os
import shutil
from shutil import copy

import gevent
import pytest
from gevent import subprocess

from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttron.platform.certs import Certs
from volttron.platform import get_examples
from volttron.utils.rmq_setup import stop_rabbit, start_rabbit, restart_ssl

fqdn=None
with open('/etc/hostname', 'r') as f:
    fqdn = f.read().strip()


@pytest.fixture(scope="function")
def instance(request):
    instance = PlatformWrapper(messagebus='rmq', ssl_auth=True)
    yield instance

    if instance.is_running():
       instance.shutdown_platform()
    # In case platform was just killed
    stop_rabbit(rmq_home=instance.rabbitmq_config_obj.rmq_home, env=instance.env, quite=True)


@pytest.mark.wrapper
def test_vstart_without_rmq_init(request, instance):
    """
    Test error where volttron is started with message bus as rmq but without
    any certs
    :param request: pytest request object
    :parma instance: volttron instance for testing
    """
    try:
        assert instance.instance_name == os.path.basename(instance.volttron_home), \
            "instance name doesn't match volttron_home basename"
        os.rename(
            os.path.join(instance.volttron_home, "certificates"),
            os.path.join(instance.volttron_home, "certs_backup")
            )
        try:
            instance.startup_platform(vip_address=get_rand_vip())
            pytest.fail("Instance should not start without certs, but it does!")
        except Exception as e:
            assert str(e).startswith("Platform startup failed. Please check volttron.log")
        assert not (instance.is_running())
    except Exception as e:
        pytest.fail("Test failed with exception: {}".format(e))


@pytest.mark.timeout(200)
@pytest.mark.wrapper
def test_vstart_expired_ca_cert(request, instance):
    """
    Test error when volttron is started with expired CA cert when rabbitmq
    server is already running
    :param request: pytest request object
    :parma instance: volttron instance for testing
    """

    crts = instance.certsobj
    try:
        # overwrite certificates with quick expiry certs
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names(instance.instance_name)

        data = {'C': 'US',
                'ST': 'Washington',
                'L': 'Richland',
                'O': 'pnnl',
                'OU': 'volttron',
                'CN': instance.instance_name+"_root_ca"}
        crts.create_root_ca(valid_days=0.0001, **data)
        copy(crts.cert_file(crts.root_ca_name),
             crts.cert_file(crts.trusted_ca_name))

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn=fqdn)

        crts.create_ca_signed_cert(admin_cert_name, type='client')
        gevent.sleep(9)
        print("Attempting to start volttron after cert expiry")
        try:
            # it fails fast. send a timeout instead of waiting for default timeout
            instance.startup_platform(vip_address=get_rand_vip(), timeout=10)
            pytest.fail("platform should not start")
        except Exception as e:
            assert str(e).startswith("Platform startup failed. Please check volttron.log")
        assert not (instance.is_running())
        # Rabbitmq log would show Fatal certificate expired
    except Exception as e:
        pytest.fail("Test failed with exception: {}".format(e))


@pytest.mark.wrapper
def test_vstart_expired_server_cert(request, instance):
    """
    Test error when volttron is started with expired server cert when RMQ
    server is already running
    :param request: pytest request object
    :parma instance: volttron instance for testing
    """
    # replace certs
    crts = instance.certsobj
    try:
        # overwrite certificates with quick expiry certs
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names(instance.instance_name)

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn=fqdn, valid_days=0.0001)
        gevent.sleep(9)
        try:
            instance.startup_platform(vip_address=get_rand_vip(), timeout=10)
        except Exception as e:
            assert str(e).startswith("Platform startup failed. Please check volttron.log")
        assert not (instance.is_running())
        # Rabbitmq log would show
        # "TLS server: In state certify received CLIENT ALERT: Fatal -
        # Certificate Expired"
    except Exception as e:
        pytest.fail("Test failed with exception: {}".format(e))


@pytest.mark.wrapper
def test_vstart_expired_admin_cert(request, instance):
    """
    Test error when volttron is started with expired admin cert when RMQ server
    is already running
    :param request: pytest request object
    :param instance: volttron instance for testing
    """
    # replace certs
    crts = instance.certsobj
    try:
        # overwrite certificates with quick expiry certs
        (root_ca, server_cert_name, admin_cert_name) = Certs.get_admin_cert_names(instance.instance_name)

        crts.create_ca_signed_cert(admin_cert_name, type='client',
                                   fqdn=fqdn, valid_days=0.0001)
        gevent.sleep(20)
        instance.startup_platform(vip_address=get_rand_vip())
        gevent.sleep(5)
        assert instance.is_running()

        # MGMT PLUGIN DOES NOT COMPLAIN ABOUT EXPIRED ADMIN CERT?? May be because we send the password too ?
        cmd = ['volttron-ctl', 'rabbitmq', 'list-users']
        process = subprocess.Popen(cmd, env=instance.env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        pytest.fail("Test failed with exception: {}".format(e))


@pytest.mark.timeout(500)
@pytest.mark.wrapper
def test_expired_ca_cert_after_vstart(request, instance):
    """
    Test error when CA cert expires after volttron has started. Once CA cert expires, can't install agent or can't get
    agent status. CA certificate needs to be recreated and client certs have to
    :param request: pytest request object
    :param instance: instance of volttron using rmq and ssl
    """
    crts = instance.certsobj
    try:
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names(instance.instance_name)

        data = {'C': 'US',
                'ST': 'Washington',
                'L': 'Richland',
                'O': 'pnnl',
                'OU': 'volttron',
                'CN': instance.instance_name + "_root_ca"}
        crts.create_root_ca(valid_days=0.0005, **data)
        print("current time after root ca:{}".format(datetime.datetime.utcnow()))
        copy(crts.cert_file(crts.root_ca_name),
             crts.cert_file(crts.trusted_ca_name))
        crts.create_ca_signed_cert(server_cert_name, type='server', fqdn=fqdn)
        crts.create_ca_signed_cert(admin_cert_name, type='client')

        instance.startup_platform(vip_address=get_rand_vip())
        print("current time after platform start:{}".format(datetime.datetime.utcnow()))
        gevent.sleep(30)  # wait for CA to expire

        # Can't install new agent
        with pytest.raises(RuntimeError, message="Agents install should fail when CA certificate has expired"):
            agent = instance.install_agent(
                agent_dir=get_examples("ListenerAgent"),
                vip_identity="listener2", start=True)

    except Exception as e:
        pytest.fail("Test failed with exception: {}".format(e))
    finally:
        # can't do clean shutdown with expired ca. terminate process
        # and clean up manually
        instance.p_process.terminate()
        stop_rabbit(rmq_home=instance.rabbitmq_config_obj.rmq_home, env=instance.env, quite=True)
        if not instance.skip_cleanup:
            shutil.rmtree(instance.volttron_home)

@pytest.mark.timeout(400)
@pytest.mark.wrapper
def test_expired_server_cert_after_vstart(request, instance):
    """
    Test error when server cert expires after volttron has started
    :param request: pytest request object
    :param instance: instance of volttron using rmq and ssl
    """
    crts = instance.certsobj
    try:
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names(instance.instance_name)

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn=fqdn, valid_days=0.0004)  # 34.5 seconds
        print("current time:{}".format(datetime.datetime.utcnow()))

        instance.startup_platform(vip_address=get_rand_vip())

        print("current time:{}".format(datetime.datetime.utcnow()))

        agent = instance.install_agent(
            agent_dir=get_examples("ListenerAgent"),
            vip_identity="listener1", start=True)
        gevent.sleep(20)
        print("Attempting agent install after server certificate expiry")
        with pytest.raises(RuntimeError, message="Agents install should fail after server certificate expires"):
            agent = instance.install_agent(
                agent_dir=get_examples("ListenerAgent"),
                vip_identity="listener2", start=True)
            pytest.fail("Agent install should fail")

        # Restore server cert and restart rmq ssl, wait for 30 seconds for volttron to reconnect
        crts.create_ca_signed_cert(server_cert_name, type='server', fqdn=fqdn)
        restart_ssl(rmq_home=instance.rabbitmq_config_obj.rmq_home, env=instance.env)

        gevent.sleep(15)  # test setup sets the volttron reconnect wait to 5 seconds

        # status of first agent would still be fine and it would
        # continue to publish hearbeat.
        assert instance.is_agent_running(agent)
        instance.remove_agent(agent)
    except Exception as e:
        pytest.fail("Test failed with exception: {}".format(e))

