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


@pytest.fixture(scope="module")
def instance(request):
    instance = PlatformWrapper(messagebus='rmq', ssl_auth=True)
    # because tests in the module shutdown and restart instance within test and we don't want
    # all rmq users and queues to be deleted.
    instance.skip_cleanup = True

    yield instance

    print("In fixture cleanup. skip clean up is {}".format(instance.skip_cleanup))

    try:
        if instance.is_running():
           instance.shutdown_platform()
    finally:
        # Since we explicitly set instance.skip_cleanup=True for the entire test suite, we have
        # call the cleanup explicitly. This will
        # 1. remove all test rmq users, queues, vhosts
        # 2. Restore original rabbitmq.conf if one exists
        # 3. remove the test volttron_home if DEBUG_MODE=True is not set the env
        instance.cleanup()


@pytest.mark.wrapper
def test_vstart_without_rmq_init(request, instance):
    """
    Test error where volttron is started with message bus as rmq but without
    any certs
    :param request: pytest request object
    :parma instance: volttron instance for testing
    """
    try:
        os.rename(
            os.path.join(instance.volttron_home, "certificates"),
            os.path.join(instance.volttron_home, "certs_backup")
            )
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        assert not (instance.is_running())
    finally:
        shutil.rmtree(os.path.join(instance.volttron_home, "certificates"))
        os.rename(
            os.path.join(instance.volttron_home, "certs_backup"),
            os.path.join(instance.volttron_home, "certificates")
            )


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
        restart_ssl(instance.rabbitmq_config_obj.rmq_home, env_file=instance.rabbitmq_config_obj.rmq_env_file)
        # backup original certificates dir before replacing it with fast expiry certs
        shutil.copytree(crts.default_certs_dir,
                  os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"))

        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names("volttron_test")

        data = {'C': 'US',
                'ST': 'Washington',
                'L': 'Richland',
                'O': 'pnnl',
                'OU': 'volttron',
                'CN': root_ca}
        crts.create_root_ca(valid_days=0.0001, **data)
        copy(crts.cert_file(crts.root_ca_name),
             crts.cert_file(crts.trusted_ca_name))

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost')

        crts.create_ca_signed_cert(admin_cert_name, type='client')
        gevent.sleep(9)
        print("Attempting to start volttron after cert expiry")
        try:
            # it fails fast. send a timeout instead of waiting for default timeout
            instance.startup_platform(vip_address=get_rand_vip(), timeout=10)
        except:
            pass
        gevent.sleep(5)
        assert not (instance.is_running())
        # Rabbitmq log would show Fatal certificate expired
    finally:
        shutil.rmtree(crts.default_certs_dir)
        # restore original certs for next test case
        os.rename(os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"),
                  crts.default_certs_dir)
        gevent.sleep(2)
        # ssl restart  doesn't work when ca cert is expired. So have to restart rabbitmq server
        stop_rabbit(rmq_home=instance.rabbitmq_config_obj.rmq_home, env_file=instance.rabbitmq_config_obj.rmq_env_file)
        start_rabbit(rmq_home=instance.rabbitmq_config_obj.rmq_home, env_file=instance.rabbitmq_config_obj.rmq_env_file)


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
        # backup original certificates dir before replacing it with fast expiry certs
        shutil.copytree(crts.default_certs_dir,
                        os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"))

        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names("volttron_test")

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost', valid_days=0.0001)
        gevent.sleep(9)
        try:
            instance.startup_platform(vip_address=get_rand_vip(), timeout=10)
        except:
            pass
        gevent.sleep(5)
        assert not (instance.is_running())
        # Rabbitmq log would show
        # "TLS server: In state certify received CLIENT ALERT: Fatal -
        # Certificate Expired"
    finally:
        shutil.rmtree(crts.default_certs_dir)
        # restore original certs for next test case
        os.rename(os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"),
                  crts.default_certs_dir)
        print("In finally. Restarting ssl so that RMQ picks up the right certs")
        restart_ssl(rmq_home=instance.rabbitmq_config_obj.rmq_home, env_file=instance.rabbitmq_config_obj.rmq_env_file)


@pytest.mark.dev
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
        # backup original certificates dir before replacing it with fast expiry certs
        shutil.copytree(crts.default_certs_dir,
                        os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"))

        (root_ca, server_cert_name, admin_cert_name) = Certs.get_admin_cert_names(instance.instance_name)

        crts.create_ca_signed_cert(admin_cert_name, type='client',
                                   fqdn='localhost', valid_days=0.0001)
        gevent.sleep(20)
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        gevent.sleep(5)
        assert instance.is_running()

        # MGMT PLUGIN DOES NOT COMPLAIN ABOUT EXPIRED ADMIN CERT?? May be because we send the password too ?
        cmd = ['volttron-ctl', 'rabbitmq', 'list-users']
        process = subprocess.Popen(cmd, env=instance.env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    finally:
        instance.p_process.terminate()  # certs are messed up so just terminate
        shutil.rmtree(crts.default_certs_dir)
        # restore original certs for next test case
        os.rename(os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"),
                  crts.default_certs_dir)
        print("In finally. Restarting ssl so that RMQ picks up the right certs")
        restart_ssl(rmq_home=instance.rabbitmq_config_obj.rmq_home, env_file=instance.rabbitmq_config_obj.rmq_env_file)


@pytest.mark.timeout(300)
@pytest.mark.wrapper
def test_vstart_rabbit_startup_error(request, instance):
    """
    Test use case when start_rabbitmq fails. See if volttron catches it correctly.
    :param request:
    :param instance:
    :return:
    """
    try:
        # Now delete the yml file so volttron will not know which rmq to start
        # and hence throw error during start_rabbitmq in main
        os.rename(
            os.path.join(instance.volttron_home, "rabbitmq_config.yml"),
            os.path.join(instance.volttron_home, "rabbit.yml"),
        )
        gevent.sleep(1)
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        assert not (instance.is_running())
        gevent.sleep(1)
    finally:
        os.rename(
            os.path.join(instance.volttron_home, "rabbit.yml"),
            os.path.join(instance.volttron_home, "rabbitmq_config.yml"),
        )


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
        # backup original certificates dir before replacing it with fast expiry certs
        shutil.copytree(crts.default_certs_dir,
                        os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"))

        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names("volttron_test")

        data = {'C': 'US',
                'ST': 'Washington',
                'L': 'Richland',
                'O': 'pnnl',
                'OU': 'volttron',
                'CN': root_ca}
        print("current time:{}".format(datetime.datetime.utcnow()))
        crts.create_root_ca(valid_days=0.0005, **data)
        print("current time after root ca:{}".format(datetime.datetime.utcnow()))
        copy(crts.cert_file(crts.root_ca_name),
             crts.cert_file(crts.trusted_ca_name))

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost')

        crts.create_ca_signed_cert(admin_cert_name, type='client')
        instance.startup_platform(vip_address=get_rand_vip())
        print("current time after platform start:{}".format(datetime.datetime.utcnow()))
        agent = instance.install_agent(
            agent_dir=get_examples("ListenerAgent"),
            vip_identity="listener", start=True)
        gevent.sleep(30)  # wait for CA to expire

        # Can't install new agent
        try:
            agent = instance.install_agent(
                agent_dir=get_examples("ListenerAgent"),
                vip_identity="listener2", start=True)
            pytest.fail("Agent install should fail")
        except Exception as e:
            print("Exception:", e)
            assert True

        # Can't find status. Essentially we have to create CA and reissue all client certs.
        try:
            instance.is_agent_running(agent)
        except Exception as e:
            assert True

    finally:
        instance.p_process.terminate()  # certs are messed up so just terminate
        shutil.rmtree(crts.default_certs_dir)
        # restore original certs for next test case
        os.rename(os.path.join(os.path.dirname(crts.default_certs_dir), "certs_backup"),
                  crts.default_certs_dir)
        # ssl restart  doesn't work when ca cert is expired. So have to restart rabbitmq server
        # restart_ssl(rmq_home=instance.rabbitmq_config_obj.rmq_home
        #                               'rabbitmq_server/rabbitmq_server-3.7.7'))
        stop_rabbit(rmq_home=instance.rabbitmq_config_obj.rmq_home, env=instance.env)
        start_rabbit(rmq_home=instance.rabbitmq_config_obj.rmq_home, env=instance.env)


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
            Certs.get_admin_cert_names("volttron_test")

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost', valid_days=0.0004)  # 34.5 seconds
        print("current time:{}".format(datetime.datetime.utcnow()))

        instance.startup_platform(vip_address=get_rand_vip())

        print("current time:{}".format(datetime.datetime.utcnow()))

        agent = instance.install_agent(
            agent_dir=get_examples("ListenerAgent"),
            vip_identity="listener1", start=True)
        gevent.sleep(20)
        print("Attempting agent install after server certificate expiry")
        try:
            agent = instance.install_agent(
                agent_dir=get_examples("ListenerAgent"),
                vip_identity="listener2", start=True)
            pytest.fail("Agent install should fail")
        except Exception as e:
            print("Exception:", e)
            assert True

        # Restore server cert and restart rmq ssl, wait for 30 seconds for volttron to reconnect
        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost')
        restart_ssl(rmq_home=instance.rabbitmq_config_obj.rmq_home, env_file=instance.rabbitmq_config_obj.rmq_env_file)

        gevent.sleep(15)  # test setup sets the volttron reconnect wait to 5 seconds

        # status of first agent would still be fine and it would
        # continue to publish hearbeat.
        assert instance.is_agent_running(agent)

    finally:
        instance.shutdown_platform()




