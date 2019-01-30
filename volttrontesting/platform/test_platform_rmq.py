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
from volttrontesting.fixtures.rmq_test_setup import create_rmq_volttron_setup, \
    cleanup_rmq_volttron_setup

from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttron.platform.certs import Certs
from volttron.platform import get_ops, get_examples
from volttron.utils.rmq_setup import stop_rabbit


@pytest.fixture(scope="module")
def instance(request):
    instance = PlatformWrapper(message_bus='rmq', ssl_auth=True)

    def stop():
        try:
            cleanup_rmq_volttron_setup(vhome=instance.volttron_home,
                                       ssl_auth=True)
            instance.shutdown_platform()
        except:
            pass
    request.addfinalizer(stop)
    return instance

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
            os.path.join(instance.volttron_home, "certs")
            )
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        assert not (instance.is_running())
    finally:
        os.rename(
            os.path.join(instance.volttron_home, "certs"),
            os.path.join(instance.volttron_home, "certificates")
            )

@pytest.mark.wrapper
def test_vstart_expired_ca_cert(request, instance):
    """
    Test error when volttron is started with expired CA cert when rabbitmq
    server is already running
    :param request: pytest request object
    :parma instance: volttron instance for testing
    """
    # replace certs
    crts = Certs()
    orig_ca_file = crts.cert_file(crts.root_ca_name)
    try:
        shutil.copytree(crts.cert_dir,
                  os.path.join(os.path.dirname(crts.cert_dir),"certs_backup"))
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
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        gevent.sleep(5)
        assert not (instance.is_running())
        # Rabbitmq log would show Fatal certificate expired
    finally:
        pass
        shutil.rmtree(crts.cert_dir)
        os.rename(os.path.join(os.path.dirname(crts.cert_dir), "certs_backup"),
                  crts.cert_dir)

@pytest.mark.wrapper
def test_vstart_expired_server_cert(request, instance):
    """
    Test error when volttron is started with expired server cert when RMQ
    server is already running
    :param request: pytest request object
    :parma instance: volttron instance for testing
    """
    # replace certs
    crts = Certs()
    orig_ca_file = crts.cert_file(crts.root_ca_name)
    try:
        shutil.copytree(crts.cert_dir,
                  os.path.join(os.path.dirname(crts.cert_dir),"certs_backup"))
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names("volttron_test")

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost', valid_days=0.0001)
        gevent.sleep(9)
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        gevent.sleep(5)
        assert not (instance.is_running())
        # Rabbitmq log would show
        # "TLS server: In state certify received CLIENT ALERT: Fatal -
        # Certificate Expired"
    finally:
        pass
        shutil.rmtree(crts.cert_dir)
        os.rename(os.path.join(os.path.dirname(crts.cert_dir), "certs_backup"),
                  crts.cert_dir)


@pytest.mark.skip("Discuss what should be the expected behavior")
@pytest.mark.wrapper
def test_vstart_expired_admin_cert(request, instance):
    """
    Test error when volttron is started with expired admin cert when RMQ server
    is already running
    :param request: pytest request object
    :param instance: volttron instance for testing
    """
    # replace certs
    crts = Certs()
    try:
        shutil.copytree(crts.cert_dir,
                  os.path.join(os.path.dirname(crts.cert_dir),"certs_backup"))
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names("volttron_test")

        crts.create_ca_signed_cert(admin_cert_name, type='client',
                                   fqdn='localhost', valid_days=0.0001)
        gevent.sleep(9)
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        gevent.sleep(5)
        assert instance.is_running()
        cmd = ['volttron-ctl', 'rabbitmq', 'list-users']
        process = subprocess.Popen(cmd, env=instance.env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err)= process.communicate()
        print ("out : {}".format(out))
        print ("err: {}".format(err))

    finally:
        shutil.rmtree(crts.cert_dir)
        os.rename(os.path.join(os.path.dirname(crts.cert_dir), "certs_backup"),
                  crts.cert_dir)
        cleanup_rmq_volttron_setup(vhome=instance.volttron_home,
                                   ssl_auth=True)
        instance.shutdown_platform()

@pytest.mark.timeout(300)
def test_vstart_rabbit_startup_error(request, instance):

    try:
        if instance.is_running():
            instance.shutdown_platform()
        # Now delete the yml file so volttron will not know which rmq to start
        # and hence throw error during start_rabbitmq in main
        os.rename(
            os.path.join(instance.volttron_home, "rabbitmq_config.yml"),
            os.path.join(instance.volttron_home, "rabbit.yml"),
        )
        try:
            instance.startup_platform(vip_address=get_rand_vip())
        except:
            pass
        assert not (instance.is_running())
    finally:
        os.rename(
            os.path.join(instance.volttron_home, "rabbit.yml"),
            os.path.join(instance.volttron_home, "rabbitmq_config.yml"),
        )


@pytest.mark.timeout(300)
@pytest.mark.skip("Discuss what should be the expected behavior")
def test_expired_ca_cert_after_vstart(request, instance):
    """
    Test error when CA cert expires after volttron has started
    :param request: pytest request object
    :param instance: instance of volttron using rmq and ssl
    """
    stop_rabbit(rmq_home=os.path.join(os.environ.get('HOME'),
                                      'rabbitmq_server/rabbitmq_server-3.7.7'))
    crts = Certs()
    orig_ca_file = crts.cert_file(crts.root_ca_name)
    try:
        shutil.copytree(crts.cert_dir,
                        os.path.join(os.path.dirname(crts.cert_dir),
                                     "certs_backup"))
        (root_ca, server_cert_name, admin_cert_name) = \
            Certs.get_admin_cert_names("volttron_test")

        data = {'C': 'US',
                'ST': 'Washington',
                'L': 'Richland',
                'O': 'pnnl',
                'OU': 'volttron',
                'CN': root_ca}
        print("current time:{}".format(datetime.datetime.utcnow()))
        crts.create_root_ca(valid_days=0.001, **data)
        copy(crts.cert_file(crts.root_ca_name),
             crts.cert_file(crts.trusted_ca_name))

        crts.create_ca_signed_cert(server_cert_name, type='server',
                                   fqdn='localhost')

        crts.create_ca_signed_cert(admin_cert_name, type='client')
        instance.startup_platform(vip_address=get_rand_vip())
        print("current time:{}".format(datetime.datetime.utcnow()))
        agent = instance.install_agent(
            agent_dir=get_examples("ListenerAgent"),
            vip_identity="listener", start=True)
        gevent.sleep(50)
        try:
            agent = instance.install_agent(
                agent_dir=get_examples("ListenerAgent"),
                vip_identity="listener2", start=True)
            pytest.fail("Agent install should fail")
        except Exception as e:
            print("Exception:", e)
            assert True
        # status of first agent would still be fine and it would
        # continue to publish hearbeat. What should be the expected
        # behavior
        assert instance.is_agent_running(agent)

    finally:
        shutil.copytree(os.path.join(os.path.dirname(crts.cert_dir),
                                     "certs_backup"),
                        crts.cert_dir)






