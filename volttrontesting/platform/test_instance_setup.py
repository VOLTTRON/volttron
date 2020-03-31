import os
import subprocess
import gevent
import pytest
from configparser import ConfigParser
from volttron.platform.instance_setup import _is_agent_installed
from volttron.utils import get_hostname
from volttron.platform.agent.utils import is_volttron_running
from volttrontesting.utils.platformwrapper import create_volttron_home
'''
NOTE: ZMQ tests only. RMQ tests will be added in 7.1

Example variables to be used during each of the tests, depending on the prompts that will be asked

message_bus = "zmq"
rmq_home = ""
domain_name = ""
new_root_ca = "Y"
ca_country = "US"
ca_state = "test-state"
ca_location = "test-location"
ca_organization = "test-org"
ca_org_unit = "test-org-unit"
default_rmq_values = "Y"
remove_rmq_conf = "Y"
vip_address = ""
vip_port = ""
is_web_enabled = "Y"
web_protocol = "https"
web_port = ""
gen_web_cert = "Y"
is_vc = "N"
vc_admin_name = "test"
vc_admin_password = "test"
is_vcp = "N"
instance_name = ""
vc_hostname = ""
vc_port = "8443"
install_historian = "N"
install_driver = "N"
install_fake_device = "N"
install_listener = "N"
agent_autostart = "N"
'''

def test_zmq_case_no_agents(monkeypatch):
    vhome = create_volttron_home()
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    config_path = os.path.join(vhome, "config")

    message_bus = "zmq"
    vip_address = "tcp://127.0.0.15"
    vip_port = "22916"
    is_web_enabled = "N"
    is_vcp = "N"
    install_historian = "N"
    install_driver = "N"
    install_listener = "N"

    vcfg_args = "\n".join([message_bus,
                           vip_address,
                           vip_port,
                           is_web_enabled,
                           is_vcp,
                           install_historian,
                           install_driver,
                           install_listener
                           ])

    with subprocess.Popen(["vcfg", "--vhome", vhome],
                          env=os.environ,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True
                          ) as vcfg:
        out, err = vcfg.communicate(vcfg_args)
    # print("CWD is: {}".format(os.getcwd()))
    # print("OUT is: {}".format(out))
    # print("ERROR is: {}".format(err))
    assert os.path.exists(config_path)
    config = ConfigParser()
    config.read(config_path)
    assert config.get('volttron', 'message-bus') == "zmq"
    assert config.get('volttron', 'vip-address') == "tcp://127.0.0.15:22916"
    assert config.get('volttron', 'instance-name') == "volttron1"
    assert not _is_agent_installed("listener")
    assert not _is_agent_installed("master_driver")
    assert not _is_agent_installed("platform_historian")
    assert not _is_agent_installed("vc ")
    assert not _is_agent_installed("vcp")
    assert not is_volttron_running(vhome)


def test_zmq_case_with_agents(monkeypatch):
    vhome = create_volttron_home()
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    config_path = os.path.join(vhome, "config")

    message_bus = "zmq"
    vip_address = "tcp://127.0.0.15"
    vip_port = "22916"
    is_web_enabled = "N"
    is_vcp = "Y"
    instance_name = "test_zmq"
    vc_hostname = "{}{}".format("https://", get_hostname())
    vc_port = "8443"
    install_historian = "Y"
    install_driver = "Y"
    install_fake_device = "Y"
    install_listener = "Y"
    agent_autostart = "N"

    vcfg_args = "\n".join([message_bus,
                           vip_address,
                           vip_port,
                           is_web_enabled,
                           is_vcp,
                           instance_name,
                           vc_hostname,
                           vc_port,
                           agent_autostart,
                           install_historian,
                           agent_autostart,
                           install_driver,
                           install_fake_device,
                           agent_autostart,
                           install_listener,
                           agent_autostart
                           ])

    with subprocess.Popen(["vcfg", "--vhome", vhome],
                          env=os.environ,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True
                          ) as vcfg:
        out, err = vcfg.communicate(vcfg_args)
    # print("CWD is: {}".format(os.getcwd()))
    print("OUT is: {}".format(out))
    print("ERROR is: {}".format(err))
    assert os.path.exists(config_path)
    config = ConfigParser()
    config.read(config_path)
    assert config.get('volttron', 'message-bus') == "zmq"
    assert config.get('volttron', 'vip-address') == "tcp://127.0.0.15:22916"
    assert config.get('volttron', 'instance-name') == "test_zmq"
    assert _is_agent_installed("listener")
    assert _is_agent_installed("master_driver")
    assert _is_agent_installed("platform_historian")
    assert _is_agent_installed("vcp")
    assert not _is_agent_installed("vc ")

    assert not is_volttron_running(vhome)


def test_zmq_case_web_no_agents(monkeypatch):
    vhome = create_volttron_home()
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    config_path = os.path.join(vhome, "config")

    message_bus = "zmq"
    vip_address = "tcp://127.0.0.15"
    vip_port = "22916"
    is_web_enabled = "Y"
    web_protocol = "https"
    web_port = "8443"
    gen_web_cert = "Y"
    new_root_ca = "Y"
    ca_country = "US"
    ca_state = "test-state"
    ca_location = "test-location"
    ca_organization = "test-org"
    ca_org_unit = "test-org-unit"
    is_vc = "N"
    is_vcp = "N"
    install_historian = "N"
    install_driver = "N"
    install_listener = "N"

    vcfg_args = "\n".join([message_bus,
                           vip_address,
                           vip_port,
                           is_web_enabled,
                           web_protocol,
                           web_port,
                           gen_web_cert,
                           new_root_ca,
                           ca_country,
                           ca_state,
                           ca_location,
                           ca_organization,
                           ca_org_unit,
                           is_vc,
                           is_vcp,
                           install_historian,
                           install_driver,
                           install_listener
                           ])

    with subprocess.Popen(["vcfg", "--vhome", vhome],
                          env=os.environ,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True
                          ) as vcfg:
        out, err = vcfg.communicate(vcfg_args)
    # print("CWD is: {}".format(os.getcwd()))
    # print("OUT is: {}".format(out))
    # print("ERROR is: {}".format(err))
    assert os.path.exists(config_path)
    config = ConfigParser()
    config.read(config_path)
    assert config.get('volttron', 'message-bus') == "zmq"
    assert config.get('volttron', 'vip-address') == "tcp://127.0.0.15:22916"
    assert config.get('volttron', 'instance-name') == "volttron1"
    assert config.get('volttron', 'bind-web-address') == "{}{}{}".format("https://", get_hostname(), ":8443")
    assert config.get('volttron', 'web-ssl-cert') == os.path.join(vhome, "certificates", "certs", "master_web-server.crt")
    assert config.get('volttron', 'web-ssl-key') == os.path.join(vhome, "certificates", "private", "master_web-server.pem")
    assert not _is_agent_installed("listener")
    assert not _is_agent_installed("master_driver")
    assert not _is_agent_installed("platform_historian")
    assert not _is_agent_installed("vc ")
    assert not _is_agent_installed("vcp")
    assert not is_volttron_running(vhome)


def test_zmq_case_web_with_agents(monkeypatch):
    vhome = create_volttron_home()
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    config_path = os.path.join(vhome, "config")

    message_bus = "zmq"
    vip_address = "tcp://127.0.0.15"
    vip_port = "22916"
    is_web_enabled = "Y"
    web_protocol = "https"
    web_port = "8443"
    gen_web_cert = "Y"
    new_root_ca = "Y"
    ca_country = "US"
    ca_state = "test-state"
    ca_location = "test-location"
    ca_organization = "test-org"
    ca_org_unit = "test-org-unit"
    is_vc = "N"
    is_vcp = "Y"
    instance_name = "test_zmq"
    vc_hostname = "{}{}".format("https://", get_hostname())
    vc_port = "8443"
    install_historian = "Y"
    install_driver = "Y"
    install_fake_device = "Y"
    install_listener = "Y"
    agent_autostart = "N"
    vcfg_args = "\n".join([message_bus,
                           vip_address,
                           vip_port,
                           is_web_enabled,
                           web_protocol,
                           web_port,
                           gen_web_cert,
                           new_root_ca,
                           ca_country,
                           ca_state,
                           ca_location,
                           ca_organization,
                           ca_org_unit,
                           is_vc,
                           is_vcp,
                           instance_name,
                           vc_hostname,
                           vc_port,
                           agent_autostart,
                           install_historian,
                           agent_autostart,
                           install_driver,
                           install_fake_device,
                           agent_autostart,
                           install_listener,
                           agent_autostart
                           ])

    with subprocess.Popen(["vcfg", "--vhome", vhome],
                          env=os.environ,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True
                          ) as vcfg:
        out, err = vcfg.communicate(vcfg_args)
    # print("CWD is: {}".format(os.getcwd()))
    print("OUT is: {}".format(out))
    print("ERROR is: {}".format(err))
    assert os.path.exists(config_path)
    config = ConfigParser()
    config.read(config_path)
    assert config.get('volttron', 'message-bus') == "zmq"
    assert config.get('volttron', 'vip-address') == "tcp://127.0.0.15:22916"
    assert config.get('volttron', 'instance-name') == "test_zmq"
    assert config.get('volttron', 'bind-web-address') == "{}{}{}".format("https://", get_hostname(), ":8443")
    assert config.get('volttron', 'web-ssl-cert') == os.path.join(vhome, "certificates", "certs", "master_web-server.crt")
    assert config.get('volttron', 'web-ssl-key') == os.path.join(vhome, "certificates", "private", "master_web-server.pem")
    assert _is_agent_installed("listener")
    assert _is_agent_installed("master_driver")
    assert _is_agent_installed("platform_historian")
    assert not _is_agent_installed("vc ")
    assert _is_agent_installed("vcp")
    assert not is_volttron_running(vhome)


def test_zmq_case_web_vc(monkeypatch):
    vhome = create_volttron_home()
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    config_path = os.path.join(vhome, "config")

    message_bus = "zmq"
    vip_address = "tcp://127.0.0.15"
    vip_port = "22916"
    is_web_enabled = "Y"
    web_protocol = "https"
    web_port = "8443"
    gen_web_cert = "Y"
    new_root_ca = "Y"
    ca_country = "US"
    ca_state = "test-state"
    ca_location = "test-location"
    ca_organization = "test-org"
    ca_org_unit = "test-org-unit"
    is_vc = "Y"
    vc_admin_name = "test"
    vc_admin_password = "test"
    is_vcp = "Y"
    instance_name = "test_zmq"
    install_historian = "N"
    install_driver = "N"
    install_listener = "N"
    agent_autostart = "N"
    vcfg_args = "\n".join([message_bus,
                           vip_address,
                           vip_port,
                           is_web_enabled,
                           web_protocol,
                           web_port,
                           gen_web_cert,
                           new_root_ca,
                           ca_country,
                           ca_state,
                           ca_location,
                           ca_organization,
                           ca_org_unit,
                           is_vc,
                           # vc_admin_name,
                           # vc_admin_password,
                           # vc_admin_password,
                           agent_autostart,
                           is_vcp,
                           instance_name,
                           agent_autostart,
                           install_historian,
                           install_driver,
                           install_listener
                           ])

    with subprocess.Popen(["vcfg", "--vhome", vhome],
                          env=os.environ,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True
                          ) as vcfg:
        out, err = vcfg.communicate(vcfg_args)
    print("OUT is: {}".format(out))
    print("ERROR is: {}".format(err))
    # print("CWD is: {}".format(os.getcwd()))

    assert os.path.exists(config_path)
    config = ConfigParser()
    config.read(config_path)
    assert config.get('volttron', 'message-bus') == "zmq"
    assert config.get('volttron', 'vip-address') == "tcp://127.0.0.15:22916"
    assert config.get('volttron', 'instance-name') == "test_zmq"
    assert config.get('volttron', 'volttron-central-address') == "{}{}{}".format("https://", get_hostname(), ":8443")
    assert config.get('volttron', 'bind-web-address') == "{}{}{}".format("https://", get_hostname(), ":8443")
    assert config.get('volttron', 'web-ssl-cert') == os.path.join(vhome, "certificates", "certs", "master_web-server.crt")
    assert config.get('volttron', 'web-ssl-key') == os.path.join(vhome, "certificates", "private", "master_web-server.pem")
    assert not _is_agent_installed("listener")
    assert not _is_agent_installed("master_driver")
    assert not _is_agent_installed("platform_historian")
    assert _is_agent_installed("vc ")
    assert _is_agent_installed("vcp")
    assert not is_volttron_running(vhome)

def test_zmq_case_web_vc_with_agents(monkeypatch):
    vhome = create_volttron_home()
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    config_path = os.path.join(vhome, "config")

    message_bus = "zmq"
    vip_address = "tcp://127.0.0.15"
    vip_port = "22916"
    is_web_enabled = "Y"
    web_protocol = "https"
    web_port = "8443"
    gen_web_cert = "Y"
    new_root_ca = "Y"
    ca_country = "US"
    ca_state = "test-state"
    ca_location = "test-location"
    ca_organization = "test-org"
    ca_org_unit = "test-org-unit"
    is_vc = "Y"
    vc_admin_name = "test"
    vc_admin_password = "test"
    is_vcp = "Y"
    instance_name = "test_zmq"
    install_historian = "Y"
    install_driver = "Y"
    install_fake_device = "Y"
    install_listener = "Y"
    agent_autostart = "N"
    vcfg_args = "\n".join([message_bus,
                           vip_address,
                           vip_port,
                           is_web_enabled,
                           web_protocol,
                           web_port,
                           gen_web_cert,
                           new_root_ca,
                           ca_country,
                           ca_state,
                           ca_location,
                           ca_organization,
                           ca_org_unit,
                           is_vc,
                           # vc_admin_name,
                           # vc_admin_password,
                           # vc_admin_password,
                           agent_autostart,
                           is_vcp,
                           instance_name,
                           agent_autostart,
                           install_historian,
                           agent_autostart,
                           install_driver,
                           install_fake_device,
                           agent_autostart,
                           install_listener,
                           agent_autostart
                           ])

    with subprocess.Popen(["vcfg", "--vhome", vhome],
                          env=os.environ,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True
                          ) as vcfg:
        out, err = vcfg.communicate(vcfg_args)
    print("OUT is: {}".format(out))
    print("ERROR is: {}".format(err))
    # print("CWD is: {}".format(os.getcwd()))

    assert os.path.exists(config_path)
    config = ConfigParser()
    config.read(config_path)
    assert config.get('volttron', 'message-bus') == "zmq"
    assert config.get('volttron', 'vip-address') == "tcp://127.0.0.15:22916"
    assert config.get('volttron', 'instance-name') == "test_zmq"
    assert config.get('volttron', 'volttron-central-address') == "{}{}{}".format("https://", get_hostname(), ":8443")
    assert config.get('volttron', 'bind-web-address') == "{}{}{}".format("https://", get_hostname(), ":8443")
    assert config.get('volttron', 'web-ssl-cert') == os.path.join(vhome, "certificates", "certs", "master_web-server.crt")
    assert config.get('volttron', 'web-ssl-key') == os.path.join(vhome, "certificates", "private", "master_web-server.pem")
    assert _is_agent_installed("listener")
    assert _is_agent_installed("master_driver")
    assert _is_agent_installed("platform_historian")
    assert _is_agent_installed("vc ")
    assert _is_agent_installed("vcp")
    assert not is_volttron_running(vhome)
