#!/usr/bin/env python3
# import module snippets
import base64
from configparser import ConfigParser, NoOptionError
from deepdiff import DeepDiff
import enum
import json
import ipaddress
import logging
from netifaces import interfaces, ifaddresses, AF_INET
import os
import pwd
import psutil
import shutil
import socket
import re
import sys
import subprocess
from time import sleep
from urllib.parse import urlparse

from ansible.module_utils.basic import AnsibleModule
from zmq import curve_keypair
from zmq.utils import z85
import yaml


class VolttronInstanceModule(AnsibleModule):
    def __init__(self, **kwargs):
        super(VolttronInstanceModule, self).__init__(**kwargs)

        # VOLTTRON cannot be ran as root.
        if os.geteuid() == 0:
            self.fail_json(msg="Cannot use this module in root context.")
            return

        self._vhome = expand_all(self.params['volttron_home'])
        self._vroot = expand_all(self.params['volttron_root'])
        self._host_config_file = expand_all(self.params['config_file'])
        self._multiplatform_file = os.path.join(self._vhome, "external_platform_discovery.json")

        # These two dictionaries will be populated in the self._discover_current_state method at the
        # bottom of this function
        self._host_config_expected = {}
        self._host_config_current = {}

        # TODO Allow volttron_path to be set from the playbook yml file.
        # self._vpath = p.get('volttron_path', "env/bin/volttron")
        self._volttron_python = os.path.join(self._vroot, "env/bin/python")
        self._volttron_executable = os.path.join(self._vroot, "env/bin/volttron")
        self._vctl = os.path.join(self._vroot, "env/bin/vctl")
        self._ansible_python = sys.executable
        self._instance_state = InstanceState.NOT_BOOTSTRAPPED
        self._agents_config = {}
        self._agents_status = {}
        self._serverkey = None

        logger().debug(f"PARAMS ARE:\n{json.dumps(self.params['volttron_host_facts'])}")
        self._all_hosts = self.params['volttron_host_facts']
        self._phase = self.params["phase"]
        if self._phase is None:
            self._phase = InstallPhaseEnum("NONE")
        else:
            self._phase = InstallPhaseEnum(self._phase)
        self._requested_state = self.params["state"]
        if self._requested_state is None:
            self._requested_state = InstanceState("UNKNOWN")
        else:
            self._requested_state = InstanceState(self._requested_state)
        # discover the state of the instance as well as the agents that make it up.
        self.__discover_current_state__()

    @property
    def phase(self):
        return self._phase

    @property
    def requested_state(self):
        return self._requested_state

    def _write_multi_platform_file(self):
        current_content = {}
        if os.path.isfile(self._multiplatform_file):
            current_content = json.loads(open(self._multiplatform_file).read())
        expected_content = {}
        for host, v in self._all_hosts.items():
            if v['instance']['expected'].get('participate-in-multiplatform'):
                expected_content[host] = {
                    "instance-name": v['instance']['expected']['config']['instance-name'],
                    "vip-address": v['instance']['expected']['config']['vip-address'],
                    "serverkey": v['instance']['serverkey']
                }

        diff = DeepDiff(current_content, expected_content)

        if diff:
            with open(self._multiplatform_file, 'w') as fp:
                fp.write(json.dumps(expected_content, indent=2))
            return True

        return False

    def handle_status(self):

        logger().debug("Inside handle_status")
        logger().debug(f"current is:\n{json.dumps(self._host_config_current, indent=2)}\nexpected:\n{json.dumps(self._host_config_expected, indent=2)}")
        diff = DeepDiff(self._host_config_current, self._host_config_expected)

        results = dict(changed=False,
                       will_change=bool(diff),
                       state=self._instance_state.name,
                       current=self._host_config_current,
                       serverkey=self._serverkey,
                       agents_state=self._agents_status)

        if diff:
            results['expected'] = self._host_config_expected

        self.exit_json(**results)

    def handle_external_connection_phase(self):
        changed = self._write_multi_platform_file()
        if changed:
            self.__stop_volttron__("external_connection_phase")
        self.__start_volttron__("external_connection_phase")
        self.exit_json(changed=changed, msg="completed handling external connections")

    def handle_start_agent_phase(self):
        self.__start_volttron__("handle_start_agent_phase")

        installed_agents = self.__status_all_agents__()
        problems = []
        for identity, props in installed_agents.items():
            cmd = [self._vctl, "start", props['agent_uuid']]
            cmd_result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if cmd_result.returncode != 0:
                problems.append(f"Could not start agent {identity}\nstderr:\n{cmd_result.stderr} ")

        if problems:
            self.fail_json(changed=True, msg=problems)
        self.__discover_current_state__()
        self.exit_json(changed=True, agents_state=self._agents_status)

    def handle_install_agent_phase(self):

        if self._instance_state == InstanceState.STOPPED:
            rc, stdout, stderr = self.__start_volttron__()
            if rc != 0:
                self.exit_json(changed=False, msg=f"Could not start the volttron platform\n{stderr}")
        elif self._instance_state == InstanceState.NOT_BOOTSTRAPPED:
            self.exit_json(changed=False, msg="Invalid state must bootstrap before we can run the install agent phase")

        self.__status_all_agents__()
        diff = DeepDiff(self._host_config_current, self._host_config_expected)
        requires_restart = False
        if diff:
            requires_restart = True
            self._write_volttron_config(self._host_config_expected['config'])

        if self._instance_state == InstanceState.RUNNING and requires_restart:
            logger().debug("instance is running but requires a restart")
            self.__stop_volttron__("install agent phase instance requires restart")

        self.__start_volttron__("install agent phase starting volttron")

        for identity, spec in self._agents_config.items():
            self._install_agent(identity, spec)

        self.exit_json(msg="What I am done")
        # if self._instance_state == InstanceState.RUNNING:
        #     self.exit_json(changed=changed, msg="VOLTTRON has started")
        # else:
        #     self.fail_json(msg="Unable to start VOLTTRON!")

    def handle_update_runtime_state(self):
        # if the configs are different then we need to write the expected to the file
        needs_changing = DeepDiff(self._host_config_current['config'], self._host_config_expected['config'])

        if needs_changing:
            self._write_volttron_config(self._host_config_expected['config'])
            self.__stop_volttron__()

        if self._requested_state == InstanceState.RUNNING and self._instance_state == InstanceState.RUNNING:
            self.exit_json(changed=False, msg="VOLTTRON is running")

        if self._requested_state == InstanceState.STOPPED and \
                self._instance_state in (InstanceState.STOPPED, InstanceState.NEVER_STARTED, InstanceState.ERROR):
            self.exit_json(changed=False, msg="VOLTTRON is stopped")

        if self._requested_state == InstanceState.RUNNING:
            rc, stdout, stderr = self.__start_volttron__()
            if rc != 0:
                self.fail_json(msg=f"Could not start volttron stdout\n{stdout}\nstderr\n{stderr}")
        elif self._requested_state == InstanceState.STOPPED:
            rc, stdout, stderr = self.__stop_volttron__()
            if rc != 0:
                self.fail_json(msg=f"Could not stop volttron stdout\n{stdout}\nstderr\n{stderr}")

        self.__discover_current_state__()

        if self._requested_state != self._instance_state:
            self.fail_json(msg=f"Could not move to state ({self._requested_state})")
        else:
            msg = f"VOLTTRON is now {self._instance_state.name}"
            if needs_changing:
                msg += ": configuration was updated"
            self.exit_json(changed=True, msg=msg)

    def __start_volttron__(self, failure_message=''):

        if self._instance_state == InstanceState.RUNNING:
            logger().debug("in start_volttron instance already running")
            return

        cmd = [self._volttron_executable, '-L', 'examples/rotatinglog.py']
        proc = subprocess.Popen(cmd,
                                stdout=open('/dev/null', 'w'),
                                stderr=open('logfile.log', 'a'),
                                preexec_fn=os.setpgrp,
                                cwd=self._vroot)

        if not self._wait_for_state(InstanceState.RUNNING):
            self.fail_json(msg=f"{failure_message}: Failed to start volttron", stdout=open('logfile.log').read())

    def __stop_volttron__(self, failure_message=''):
        logger().debug(f"Stopping volttron instance state is: {self._instance_state}")
        if self._instance_state == InstanceState.STOPPED:
            logger().debug(f'VOLTTRON is {InstanceState.STOPPED.name}')
            return

        cmd = [self._vctl, 'shutdown', '--platform']

        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                cwd=self._vroot)

        self._wait_for_state(InstanceState.STOPPED)
        try:
            stdout = result.stdout.decode('utf-8')
        except AttributeError:
            stdout = result.stdout
        try:
            stderr = result.stderr.decode('utf-8')
        except AttributeError:
            stderr = result.stderr

        if result.returncode != 0:
            self.exit_json(msg=f"{failure_message}: Failed to stop volttron", stderr=stderr, stdout=stdout)

    def _wait_for_state(self, expected_state, timeout=10):
        countdown = timeout
        current_state = self._instance_state
        while current_state is not expected_state and countdown > 0:
            sleep(1)
            countdown -= 1
            self.__discover_current_state__()
            if self._instance_state == expected_state:
                break

        return self._instance_state == expected_state

    def _write_volttron_config(self, config):
        os.makedirs(self._vhome, exist_ok=True)
        volttron_config_file = os.path.join(self._vhome, 'config')
        expected_config = config.copy()

        config_parser = ConfigParser()
        config_parser.add_section("volttron")
        for k, v in expected_config.items():
            config_parser.set("volttron", k, f'"{v}"')
        with open(volttron_config_file, 'w') as fp:
            config_parser.write(fp)

        #
        #
        #
        # host_config_cpy = {}
        # if host_config_dict is not None:
        #     host_config_cpy = host_config_dict.copy()
        # host_config_cpy.pop("participate-in-multiplatform", None)
        #
        # logger().debug(f"Building config from:\n{json.dumps(host_config_cpy, indent=2)}")
        # cfg_loc = os.path.join(volttron_home, 'config')
        # had_config = False
        # changed = False
        # if not os.path.isdir(volttron_home):
        #     os.makedirs(volttron_home)
        # else:
        #     if os.path.isfile(cfg_loc):
        #         had_config = True
        #
        # parser = ConfigParser()
        #
        # if had_config:
        #     parser.read(cfg_loc)
        #
        # vc_address = None
        # vc_serverkey = None
        # vip_address = None
        # bind_web_address = None
        #
        # if had_config:
        #     vc_address = _get_option_no_error(parser,
        #                                       'volttron',
        #                                       'voltttron-central-address')
        #     vc_serverkey = _get_option_no_error(parser,
        #                                         'volttron',
        #                                         'voltttron-central-serverkey')
        #     vip_address = _get_option_no_error(parser, 'volttron', 'vip-address')
        #     bind_web_address = _get_option_no_error(parser,
        #                                             'volttron', 'bind-web-address')
        # else:
        #     changed = True
        #     parser.add_section('volttron')
        #     for k, v in host_config_cpy.items():
        #         parser.set('volttron', k, str(v))
        #
        # if not had_config:
        #     if 'volttron_central_addres' not in host_config_cpy:
        #         _remove_option_no_error(parser, 'volttron', 'volttron-central-address')
        #     else:
        #         parser.set('volttron', 'volttron-central-address',
        #                    host_config_cpy['volttron_central_address'])
        #
        #     if 'volttron_central_serverkey' not in host_config_cpy:
        #         _remove_option_no_error(parser, 'volttron',
        #                                 'volttron-central-serverkey')
        #     else:
        #         parser.set('volttron', 'volttron-central-serverkey',
        #                    host_config_cpy['volttron_central_serverkey'])
        #
        #     if 'vip_address' not in host_config_cpy:
        #         _remove_option_no_error(parser, 'volttron', 'vip-address')
        #     else:
        #         parser.set('volttron', 'vip-address',
        #                    host_config_cpy['vip_address'])
        #
        #     # if not host_config_dict['enable_web']:
        #     #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        #     # elif not host_config_dict['bind_web_address']:
        #     #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        #     # else:
        #     #     parser.set('volttron', 'bind-web-address',
        #     #                host_config_dict['bind_web_address'])
        #
        # parser.write(open(cfg_loc, 'w'))
        # return changed

    def __discover_current_state__(self):
        """
        Determine the state of volttron on target system.  The function determines
        whether or not volttron is running based upon the VOLTTRON_PID file in
        the volttron_home directory.  First of all the function will check to make sure
        that volttron has been bootstrapped.  If it is not the function will return
        `InstanceState.NOT_BOOTSTRAPPED.  If the process id in VOLTTRON_PID is in /proc/ directory
        then the process is alive and the function returns `InstanceState.RUNNING`.  Otherwise, the
        function will return `InstanceState.STOPPED`

        :return:
        """

        # region verify correct paths available for the system
        # if the volttron path doesn't exist yet then then we know the user
        # hasn't inited this instance yet.
        if not os.path.exists(self._vroot):
            self.fail_json(msg=f"volttron_path does not exist {self._vroot}. "
                               f"Please run vctl deploy init on this host.")

        # The host config file must be present for the script to understand
        # how to configure this instance.
        if not os.path.exists(self._host_config_file):
            self.fail_json(msg=f"config_file path does not exist {self._host_config_file}. "
                               "Please run vctl deploy init on this host.")
        # endregion

        # region determine the instance state - RUNNING, STOPPED, NOT_BOOTSTRAPPED, etc
        PID_FILE = os.path.join(self._vhome, "VOLTTRON_PID")

        if not os.path.exists(self._volttron_executable):
            self._instance_state = InstanceState.NOT_BOOTSTRAPPED
        else:
            if os.path.exists(PID_FILE):
                pid = open(PID_FILE).read()
                if os.path.isdir(f"/proc/{pid}"):
                    self._instance_state = InstanceState.RUNNING
                else:
                    self._instance_state = InstanceState.STOPPED
            else:
                self._instance_state = InstanceState.STOPPED

        logger().debug(f"_discover_current_state: {self._instance_state}")
        # endregion

        # Read expected hosts file and translate that into what will go into the main volttron config
        with open(self._host_config_file) as fp:
            host_cfg_loaded = yaml.safe_load(fp)

        if 'config' not in host_cfg_loaded:
            self.fail_json(msg="Must have config section in host configuration file.")
        if 'agents' not in host_cfg_loaded:
            self.fail_json(msg="Must have agents section in host configuration file.")
        logger().debug(f"host config loaded: {json.dumps(host_cfg_loaded, indent=2)}")

        # No agent configuration means that we have a platform just sitting there doing nothing,
        # however that is not an error state.
        self._agents_config = host_cfg_loaded.get('agents', {})
        if self._agents_config is None:
            self._agents_config = {}

        self._host_config_expected = host_cfg_loaded.get('config', {})
        # If no configuration parameters passed that's ok
        if self._host_config_expected is None:
            self._host_config_expected = {}

        # The config key will be used to write the new volttron config file
        self._host_config_expected['config'] = {}

        # populate the instance name first based upon /etc/hostname or custom-instance-name
        # within the config file.
        instance_name = None
        try:
            with open("/etc/hostname") as fp:
                instance_name = fp.read().strip()
        except FileNotFoundError:
            instance_name = self._host_config_expected.get('custom-instance-name', instance_name)
        if instance_name is None:
            self.fail_json(msg="Couldn't read /etc/hostname nor was custom-instance-name specified in host file.")

        self._host_config_expected['config']['instance-name'] = instance_name

        if 'enable-web-http' in self._host_config_expected and 'enable-web-https' in self._host_config_expected:
            self.fail_json(msg="Cannot have both an https and http endpoint specified")

        if 'enable-web-http' in self._host_config_expected or 'enable-web-https' in self._host_config_expected:
            is_http = 'enable-web-http' in self._host_config_expected
            # is_https = 'enable-web-https' in self._host_config_expected
            bind_web_address = 'http://' if is_http else 'https://'

            hostname = self._host_config_expected.get('custom-web-hostname',
                                                      self._host_config_expected['config']['instance-name'])
            web_port = self._host_config_expected.get('custom-web-port', 8080 if is_http else 8443)
            # TODO validate web port here

            bind_web_address = bind_web_address + f"{hostname}:{web_port}"
            self._host_config_expected['config']['bind-web-address'] = bind_web_address

            # TODO handle cert generation here as well as if user passed certs in via config

        # TODO verify agent configuration path etc are available to install.

        # Does this platform participate in multi-platform
        multiplatform_participant = False
        try:
            a_bool = to_bool(self._host_config_expected.get('participate-in-multiplatform', False))
            multiplatform_participant = a_bool
            logging.debug(f"Will participate in multi-platform: {multiplatform_participant}")
        except TypeError:
            self.fail_json(msg=f"Invalid value for participate-in-multiplatform")
        else:
            self._host_config_expected['participate-in-multiplatform'] = multiplatform_participant

        # Allow external connections to the platform
        allow_external_connections = False
        try:
            allow_external_connections = to_bool(
                self._host_config_expected.get('allow-external-connections', multiplatform_participant))
            logging.debug(f"Will allow external connections: {allow_external_connections}")
        except TypeError:
            self.fail_json(msg=f"Invalid value for 'allow-external-connections'")
        else:
            self._host_config_expected['allow-external-connections'] = allow_external_connections

        custom_vip_ip = self._host_config_expected.get("custom-vip-ip", None)
        custom_vip_port = int(self._host_config_expected.get("custom-vip-port", 22916))
        if custom_vip_port <= 1024 or custom_vip_port > 65535:
            self.fail_json(msg="Invalid custom-vip-port must be between 1024 and 65535")

        if custom_vip_ip:
            vip_address = f"tcp://{custom_vip_ip}:{custom_vip_port}"
        else:
            vip_address = None

        if multiplatform_participant and not allow_external_connections:
            self.fail_json(msg="Mismatch between allow-external-connections and participate-in-multiplatform")

        if multiplatform_participant or allow_external_connections:
            try:
                vip_address = dertimine_vip_address(should_be_public=True,
                                                    vip_address=vip_address,
                                                    custom_port=self._host_config_expected.get('custom-vip-port', 22916))
            except ValueError as ex:
                self.fail_json(msg=ex)
            else:
                self._host_config_expected['config']['vip-address'] = vip_address
        else:
            try:
                vip_address = dertimine_vip_address(should_be_public=False,
                                                    vip_address=vip_address,
                                                    custom_port=self._host_config_expected.get('custom-vip-port', 22916))
            except ValueError as ex:
                self.fail_json(msg=ex)
            else:
                self._host_config_expected['config']['vip-address'] = vip_address

        os.makedirs(self._vhome, exist_ok=True)
        keystore_file = os.path.join(self._vhome, "keystore")
        if not os.path.exists(keystore_file):
            with open(keystore_file, 'w') as fp:
                public, secret = curve_keypair()
                fp.write(json.dumps(
                    {'public': encode_key(public), 'secret': encode_key(secret)},
                    indent=2))

        with open(os.path.join(self._vhome, "keystore")) as fp:
            keystore = json.loads(fp.read())
            self._host_config_expected['serverkey'] = keystore['public']
        logger().debug("HOSTCONFIGEXPECTED:")
        logger().debug(f"{json.dumps(self._host_config_expected, indent=2)}")
        if 'volttron-central-instance' in self._host_config_expected:
            vc_instance = self._host_config_expected['volttron-central-instance']
            # use as local and then modify to use other instance if necessary
            vc_config_specs = {
                'volttron-central-address': self._host_config_expected['config']['bind-web-address'],
                'volttron-central-serverkey': self._host_config_expected['serverkey']
            }
            if vc_instance != self._host_config_expected['config']['instance-name']:
                if vc_instance not in self._all_hosts:
                    self.fail_json(msg=f"Invalid host specified for volttron-central-instance {vc_instance}")

                other_instance = self._all_hosts[vc_instance]
                vc_config_specs['volttron-central-address'] = other_instance['config']['vip-address']
                vc_config_specs['volttron-central-serverkey'] = other_instance['config']['serverkey']

            self._host_config_expected['config'].update(vc_config_specs)

        self._host_config_expected['config']['message-bus'] = self._host_config_expected.get('message-bus', 'zmq')
        self.__discover_agents_status__()

        # endregion

        # region load current config
        volttron_config_file = os.path.join(self._vhome, "config")

        self._host_config_current.clear()
        self._host_config_current['config'] = {}
        if os.path.isfile(volttron_config_file):
            parser = ConfigParser()
            parser.read(volttron_config_file)
            for k, v in parser.items("volttron"):
                self._host_config_current['config'][k] = v

        # These are things that are specified after volttron starts in the config file
        if 'web-secret-key' in self._host_config_current['config']:
            tmp = self._host_config_expected['config']
            tmp['web-secret-key'] = self._host_config_current['config']['web-secret-key']

        self._host_config_current["participate-in-multiplatform"] = os.path.isfile(self._multiplatform_file)

        # endregion

        # region load publickey into local member variable
        keystore_file = os.path.join(self._vhome, "keystore")
        logger().debug(f"KEYSTOREFILE: {keystore_file}")
        if os.path.isfile(keystore_file):
            with open(keystore_file) as fp:
                data = json.loads(fp.read())
                self._serverkey = data['public']
        # endregion
        logger().debug(f"HOST CONFIG CURRENT:\n{json.dumps(self._host_config_current, indent=2)}")
        logger().debug(f"HOST CONFIG EXPECTED:\n{json.dumps(self._host_config_expected, indent=2)}")

    def _install_agent(self, identity, agent_spec: dict):
        """
        Installs
        The install_agent function is the main function of the module.  It wraps
        two scripts that are available in the volttron repository under the scripts
        directory.  The instance.py script allows querying of the instance for
        information without having to be activated, and the install-agent.py
        script that has command line arguments for installing the agents on a
        running instance.

        @param: identity: The agent's identity
        @param: agent_spec: The specification for agent installation

        :return:
        """

        cmd = [self._vctl, "install", agent_spec['source'], '--json', '--force',
               '--vip-identity', identity]

        if "priority" in agent_spec:
            cmd.extend(['--priority', str(agent_spec['priority'])])

        logger().debug(f"Commands are {cmd}")

        response = subprocess.run(cmd, cwd=self._vroot,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if response.returncode != 0:
            logger().debug(f"Something failed spectacularly during install for idenitity {identity}")
            logger().debug(f"STDOUT\n{response.stdout}")
            logger().debug(f"STDERR\n{response.stdout}")
            return

        logger().debug(f"Installed {identity}")
        logger().debug(f"STDOUT\n{response.stdout}")
        logger().debug(f"STDERR\n{response.stdout}")

        #
        # params = module.params
        # # First we need to verify that the instance is currently running or we
        # # cannot install anything.
        # args = [python, os.path.join(scripts_dir, 'instance.py'), '--volttron-home',
        #         params['volttron_home']]
        #
        # (rc, out, err) = module.run_command(args)
        #
        # if rc != 0:
        #     return True, False, dict(msg="instance not running", out=out, err=err)
        #
        # if int(out.strip()) == 0:
        #     err = "Instance {} is not running.".format(params['volttron_home'])
        #     return (True, False,
        #             dict(msg=err))
        #
        # # Next we need to customize the installation script parameters based upon
        # # the input from the caller.
        # script = os.path.join(scripts_dir, "install-agent.py")
        #
        # args = [python, script]
        # args.extend(['--volttron-home', params['volttron_home']])
        # args.extend(['--volttron-root', params['volttron_root']])
        # args.extend(['--agent-source', params['source']])
        #
        # if params['identity']:
        #     args.extend(['--vip-identity', params['identity']])
        #
        # # Always use force because we can't find a reason not to upgrade if
        # # possible.
        # args.extend(['--force'])
        #
        # # If a priority is specified that implies the agent will be enabled.
        # if params['priority']:
        #     args.extend(['--enable', '--priority', str(params['priority'])])
        # elif params['enable']:
        #     args.extend(['--enable'])
        #
        # # When a config_objecct is sent as a parameter we use a temp file to write
        # # the content to before using it within the installation.  We do this so
        # # that we don't have to deal with passing json on the commmand line, though
        # # it will work it is frought with perils
        # #
        # # We serialize the json (config_object) and stuff it into the temp file.
        # tmpfilename = '/tmp/tmp-{}'.format(random.randint(10, 1000))
        # #module.fail_json(msg=tmpfilename + str(params['config_object']))
        # if params['config_object']:
        # #    module.exit_json(msg=params['config_object'])
        #     # Dump to to tmp file and then add the --config param to the arguments.
        #     data = json.dumps(params['config_object'])
        #     with open(tmpfilename, 'w') as f:
        #         f.write(data)
        #
        #     args.extend(['--config', tmpfilename])
        # elif params['config']:
        #     args.extend(['--config', params['config']])
        #
        # if params['state'] == 'started':
        #     args.extend(['--start'])
        #
        # if params['tag']:
        #     args.extend(['--tag', params['tag']])
        #
        # (rc, stdout, stderr) = module.run_command(args)
        #
        # retvalues = {}
        # is_error = int(rc) != 0
        # if is_error:
        #     retvalues['msg'] = "rc code from install-agent.py invalid."
        #
        # # Cleanup temp file if necessary.
        # if os.path.exists(tmpfilename):
        #     os.remove(tmpfilename)
        #
        # install_return = None
        # if not is_error:
        #     # Now there is a lot of cruf in the stdout, however it is split by \n
        #     # and after the word RECORD at the end of a line is json data
        #     pos = stdout.rindex('RECORD') + len('RECORD') + 1
        #     jsondata = stdout[pos:]
        #     #return is_error, False, dict(stdout=jsondata)
        #     install_return = json.loads(jsondata.replace("\n", " "))
        #     if params['state'] == 'started':
        #         is_error = 'started' in install_return and not install_return['started']
        #         if is_error:
        #             retvalues['msg'] = "Agent wasn't able to reach started state."
        #
        # retvalues['params'] = params
        # retvalues['args'] = args
        # retvalues['install_agent_ret'] = install_return
        # if is_error:
        #     return is_error, False, retvalues
        #
        # retvalues['result'] = "installed {} agent.".format(params['source'])
        # return is_error, True, retvalues

    def __status_all_agents__(self):
        # Will need to be fixed when vctl status --json available.
        cmd = [self._vctl, "--json", "status"]
        cmd_results = subprocess.run(cmd, cwd=self._vroot,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        if cmd_results.returncode == 0:
            if cmd_results.stdout.decode('utf-8') == '':
                return {}
            return json.loads(cmd_results.stdout.decode('utf-8'))
        else:
            cmd = [self._vctl, "--json", "list"]
            cmd_results = subprocess.run(cmd, cwd=self._vroot,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
            if cmd_results.returncode == 0:
                if cmd_results.stdout.decode('utf-8') == '':
                    return {}
                return json.loads(cmd_results.stdout.decode('utf-8'))
            return dict(msg=f"Failed to get the status of agents",
                        stderr=cmd_results.stderr.decode('utf-8'))

    def __get_agent_status__(self, agent_dir):
        """
        Retrieve the agent status from the installed directory in VOLTTRON_HOME.

        This method uses the metadata.json file in the agent's .dist-info folder
        to load information about the agent.  In addition it uses psutil to
        verify whether an agent is running or not.

        The function will return a dictionary with the following keys:
         - pid          - PID of the agent if running
         - public_key   - public_key of the agent if available
         - priority     - startup order if available
         - tag          - agent tag if available

        :param agent_dir: The installed agent directory
        :return:
        """

        dist_info_dir = None
        for root, dirs, files in os.walk(agent_dir):
            for d in dirs:
                if d.endswith("dist-info"):
                    dist_info_dir = os.path.join(root, d)
                    break
        agent_data_dir = None
        for root, dirs, files in os.walk(agent_dir):
            for d in dirs:
                if d.endswith("agent-data"):
                    agent_data_dir = os.path.join(root, d)
                    break

        logger().debug(f"dist-info dir is {dist_info_dir}")
        logger().debug(f"agent-data dir is {agent_data_dir}")

        logger().debug(f"Checking directory exists {dist_info_dir}")
        if not os.path.isdir(dist_info_dir):
            return dict(state=AgentState.NOT_INSTALLED.name)

        agent_uuid = os.path.basename(agent_dir)
        tag_file = os.path.join(agent_dir, "TAG")
        priority_file = os.path.join(agent_dir, "AUTOSTART")
        key_file = os.path.join(agent_data_dir, "keystore.json")

        with open(os.path.join(dist_info_dir, 'metadata.json')) as file:
            metadata = json.loads(file.read())
        logger().debug(f"metadata is {metadata}")
        try:
            exports = metadata['exports']
        except KeyError:
            exports = metadata['extensions']['python.exports']
        eggsecutable = exports['setuptools.installation']['eggsecutable']
        found_proc = None
        module, _ = eggsecutable.split(":")
        logger().debug(f"searching for module: {module} using psutils")
        for proc in psutil.process_iter():
            if module in proc.name():
                found_proc = proc
                break
        logger().debug(f"found_proc is: {found_proc}")
        pid = None
        if found_proc:
            pid = found_proc.pid
        tag = None
        if os.path.exists(tag_file):
            tag = open(tag_file).read()
        priority = None
        if os.path.exists(priority_file):
            priority = open(priority_file).read()
        public_key = None
        if os.path.exists(key_file):
            with open(key_file) as fp:
                data = json.loads(fp.read())
                public_key = data['public']
        return {
            "agent_uuid": agent_uuid,
            "pid": pid,
            "public_key": public_key,
            "priority": priority,
            "tag": tag
        }

    def __find_all_agents__(self):
        """
        Find all of the agents in the specified `path`.  The path should
        be the VOLTTRON_HOME/agents directory.

        The function uses the each agent's IDENTITY file to create a
        dictionary of agent identities mapped onto the agent state.

        This function requires using `get_agent_status` to determine the
        state of the agent.

        :param path:
            Path of the search for agents.
        :return:
            dictionary of identity -> agent status
        """
        results = {}
        name = "IDENTITY"
        for root, dirs, files in os.walk(os.path.join(self._vhome, "agents")):
            if name in files:
                file_path = os.path.join(root, name)
                logger().debug(f"file_path is {file_path}")
                identity = open(file_path).read()
                logger().debug(f"Passing dirname ({os.path.dirname(file_path)})")
                results[identity] = self.__get_agent_status__(os.path.dirname(file_path))

        return results

    def __discover_agents_status__(self):
        """
        Uses all found agents (from `find_all_agents` function) to provide an
        agent state key.  The function compares expected agents to the currently
        installed and runnning agents to provide the state.

        This function will return a dictionary such as the following:

        {
          "identity1":
            {
              "state": "RUNNING",
              "pid": 4234
            },
          "identity2":
            {
              "state": "NOT_INSTALLED"
            }
        }

        :param volttron_home:
        :param agents_config_dict:
        :return:
            dictionary identity -> state with pid
        """
        agents_state = self.__find_all_agents__()
        runtime_status = self.__status_all_agents__()

        self._agents_status = {}
        for identity, spec in self._agents_config.items():
            if identity not in self._agents_status:
                self._agents_status[identity] = {}

            if identity not in agents_state:
                self._agents_status[identity] = dict(state=AgentState.NOT_INSTALLED.name)
            elif 'pid' not in agents_state[identity]:
                self._agents_status[identity] = dict(state=AgentState.STOPPED.name)
            else:
                self._agents_status[identity] = dict(state=AgentState.RUNNING.name)

def main():
    init_logging(expand_all("~/ansible_logging.log"))
    logger().debug("Before module instantiation")
    logger().debug(f"ENV: {os.environ}")

    module = VolttronInstanceModule(argument_spec=dict(
        volttron_home=dict(required=False, default=expand_all("~/.volttron")),
        volttron_root=dict(required=False, default=expand_all("~/volttron")),
        config_file=dict(required=True),
        phase=dict(choices=InstallPhaseEnum.__members__.keys()),
        # instance_name=dict(default=socket.gethostname()),
        # vip_address=dict(default=None),
        # bind_web_address=dict(default=None),
        # volttron_central_address=dict(default=None),
        # volttron_central_serverkey=dict(default=None),
        # Only binds when this flag is set to true.

        state=dict(choices=InstanceState.__members__.keys()),
        volttron_host_facts=dict(required=False, type='dict')
        # started=dict(default=True, type="bool")
    ), supports_check_mode=True)

    logger().debug(f"Passed params:\n{json.dumps(module.params, indent=2)}")
    if module.check_mode:
        logger().debug("module.check_mode True calling handle_status")
        module.handle_status()

    logger().debug(f"allow external conn {module.phase.name}")
    if module.phase == InstallPhaseEnum.AGENT_INSTALL:
        module.handle_install_agent_phase()
    elif module.phase == InstallPhaseEnum.ALLOW_EXTERNAL_CONNECTIONS:
        module.handle_external_connection_phase()
    elif module.phase == InstallPhaseEnum.START_AGENTS:
        module.handle_start_agent_phase()
    else:
        module.fail_json(msg=f"Unknown phase {module.phase} {type(module.phase)}specified that should have been known.")

    # # Short cut for params
    # p = module.params
    #
    # vroot = expand_all(p['volttron_root'])
    #
    # # if the volttron path doesn't exist yet then then we know the user
    # # hasn't inited this instance yet.
    # if not os.path.exists(vroot):
    #     module.fail_json(msg=f"volttron_path does not exist {vroot}. "
    #                          f"Please run vctl deploy init on this host.")
    #
    # # region host configuration file validation (No changes made!) populates host_cfg and agent_cfg vars
    # host_config_file = expand_all(p['config_file'])
    #
    # # The host config file must be present for the script to understand
    # # how to configure this instance.
    # if not os.path.exists(vroot):
    #     module.fail_json(msg=f"config_file path does not exist {host_config_file}. "
    #                          "Please run vctl deploy init on this host.")
    #
    # expected_state = InstanceState(p['state'])
    # expected_phase = InstallPhaseEnum(p['phase'])
    # if expected_state == InstanceState.STOPPED:
    #     module.handle_stop_volttron()
    #
    # if expected_phase == InstallPhaseEnum.AGENT_INSTALL:
    #     module.handle_install_agent_phase()
    #
    # module.exit_json(msg="exiting after stuff")
    # if expected_state == InstanceState.STOPPED:
    #     module.handle_stop_volttron()
    #
    # # the validate doesn't make changes, just makes sure that the change is valid for both
    # # the agents and config entries in the host_config_file.  The function calls
    # # exit_json if something is not proper.
    # host_cfg, agent_cfg = _validate_and_build_updated_configuration(host_config_file, module)
    #
    # logger().debug(f"After validate host_cfg:\n{json.dumps(host_cfg, indent=2)}"
    #                f"\nagent_cfg: {json.dumps(agent_cfg, indent=2)}")
    #
    # # endregion
    #
    # module.exit_json(msg="I am exiting now!")
    #
    # write_volttron_config_file("/tmp/new_volttron_config", host_cfg)
    #
    # # volttron_context allows the functions to get the main directories
    # # without having to pass them along in the arguments of functions.
    # volttron_context.update_volttron_root(vroot)
    #
    # vhome = expand_all(p['volttron_home'])
    #
    # # Check mode allows ansible to run a mininimal commmand that "doesn't change"
    # # any state.  In our system, if the serverkey is not created then it will
    # # be created during a check mode call.
    # check_mode = module.check_mode
    #
    # # region create main keystore file that keeps the instance's serverkey
    #
    # # Create the volttron_home directory if it doesn't exist and create the main
    # # instanc's public and secreate key for the instance.  This is the value that
    # # one can retrive when doing a vctl auth serverkey command from the command line.
    # os.makedirs(vhome, 0o755, exist_ok=True)
    #
    # serverkey_file = os.path.join(vhome, "keystore")
    #
    # if not os.path.exists(serverkey_file):
    #     public, secret = curve_keypair()
    #     with open(serverkey_file, 'w') as fp:
    #         fp.write(
    #             json.dumps(
    #                 {'public': encode_key(public), 'secret': encode_key(secret)},
    #                 indent=2))
    #
    # with open(serverkey_file) as fp:
    #     keypair = json.loads(fp.read())
    #     publickey = keypair['public']
    #
    # # endregion
    #
    # # The main volttron config file will automatically be created when
    # # the agent is first started or when this module is run without check_mode
    # # set to true.
    # main_volttron_config = os.path.join(vhome, "config")
    #
    # # region check_mode
    # if module.check_mode:
    #     if not os.path.isfile(main_volttron_config):
    #         retdict = format_return_dict(host_cfg, agent_cfg, InstanceState.NEVER_STARTED, {})
    #         module.exit_json(**retdict)
    #     instance_state = get_instance_state()
    #     retdict = format_return_dict(host_cfg, agent_cfg, instance_state, agent_cfg)
    #
    #     module.exit_json(**retdict)
    #
    # # endregion
    #
    # # state is required if check_mode is not set
    # if 'state' not in p:
    #     module.exit_json(changed=False, msg="missing required arguments: state",
    #                      available_states=AgentState.__members__.keys())
    #
    # if 'phase' not in p:
    #     module.exit_json(changed=False, msg="missing required argument: phase",
    #                      available_phases=InstallPhaseEnum.__members__.keys())
    #
    # expected_state = InstanceState(p['state'])
    # current_phase = InstallPhaseEnum(p['phase'])
    # volttron_host_facts = None
    #
    # if expected_state == InstanceState.STOPPED:
    #     module.handle_stop_volttron()
    #
    # module.handle_start_volttron()
    #
    # if current_phase == InstallPhaseEnum.AGENT_INSTALL:
    #     start_volttron(module)
    #
    # if current_phase == InstallPhaseEnum.ALLOW_EXTERNAL_CONNECTIONS:
    #     if 'volttron_host_facts' not in p:
    #         module.exit_json(changed=False,
    #                          msg="missing required argument: "
    #                              "'volttron_host_facts' for phase 'ALLOW_EXTERNAL_CONNECTIONS")
    #     else:
    #         volttron_host_facts = p['volttron_host_facts']
    # logger().debug(f"Expected State is {expected_state}")
    # logger().debug(f"curren_phase is {current_phase}")
    #
    # # Create/update main volttron config file
    # config_file_changed = build_volttron_configfile(vhome, host_cfg)
    # current_state = get_instance_state()
    #
    # if current_state == InstanceState.RUNNING:
    #     logger().debug("Inside running block")
    #     if current_phase == InstallPhaseEnum.AGENT_INSTALL:
    #         logger().debug("Before do_install_agents")
    #         results = do_install_and_remove_agents_phase(agent_cfg)
    #     elif current_phase == InstallPhaseEnum.ALLOW_EXTERNAL_CONNECTIONS:
    #         logger().debug("Before do allow")
    #         results = do_allow_connections(agent_cfg, volttron_host_facts)
    #     else:
    #         logger().debug("Before start tag.")
    #         results = do_start_tag_agents(agent_cfg)
    #
    #     module.exit_json(changed=True)
    #
    # module.exit_json(msg="Outside!")
    # if current_state == expected_state and not config_file_changed:
    #     agent_state_changed = False
    #     # if current_state == InstanceState.RUNNING:
    #     #     module.fail_json(msg="doing check for agents")
    #     #     agent_state_changed = update_agents(cfg_host['agents'])
    #     before_agent, after_agent = update_agents(host_cfg['agents'])
    #
    #     module.exit_json(changed=True, msg="First block here", before_agent=before_agent, after_agent=after_agent)
    #
    #     module.exit_json(changed=False, msg=f"No Change Required", state=current_state.name,
    #                      serverkey=publickey,
    #                      agent_state_changed=agent_state_changed)
    # elif expected_state == InstanceState.RUNNING:
    #     if config_file_changed and current_state == InstanceState.RUNNING:
    #         logger().debug("Stopping volttron due to restart")
    #         stop_volttron()
    #         current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)
    #         if current_state != InstanceState.STOPPED:
    #             module.fail_json(msg="Failed to stop running volttron in timely manner")
    #     logger().debug("Starting volttron")
    #     start_volttron()
    #     current_state = wait_for_state(InstanceState.RUNNING, vhome, vroot)
    #
    #     if current_state != InstanceState.RUNNING:
    #         module.fail_json(msg="Failed to start VOLTTRON")
    #
    #     before_agent, after_agent = update_agents(host_cfg['agents'])
    #
    #     module.exit_json(changed=True, before_agent=before_agent, after_agent=after_agent)
    #
    #     module.exit_json(changed=True, failed=current_state != expected_state,
    #                      msg="VOLTTRON started", serverkey=publickey,
    #                      state=current_state.name)
    # elif expected_state == InstanceState.STOPPED:
    #     logger().debug("Stopping volttron")
    #     stop_volttron()
    #     current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)
    #
    #     if current_state != expected_state:
    #         force_kill_volttron()
    #         current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)
    #
    #         if current_state != expected_state:
    #             module.fail_json(msg="Couldn't shutdown or force kill volttron")
    #
    #     current_state = get_instance_state()
    #
    #     module.exit_json(changed=True, failed=current_state != expected_state,
    #                      msg="VOLTTRON stopped",
    #                      serverkey=publickey,
    #                      state=current_state.name)
    #
    # module.fail_json(msg="Unknown state found")
    #
    # config_file_changed = build_volttron_configfile(vhome, p)
    #
    # after_state = get_instance_state()
    # changed = after_state != current_state
    # module.exit_json(changed=changed,
    #                  ansible_facts=p,
    #                  original_state=current_state,
    #                  after_state=after_state)


# region utility functions
def init_logging(filepath, level=logging.DEBUG):
    # if os.path.isfile(filepath):
    #     os.remove(filepath)
    logging.basicConfig(filename=filepath, level=level)


def logger():
    return logging.getLogger(__name__)


def expand_all(path):
    return os.path.expandvars(os.path.expanduser(path))


def encode_key(key):
    """"Base64-encode and return a key in a URL-safe manner."""
    assert len(key) in (32, 40)
    if len(key) == 40:
        key = z85.decode(key)
    return base64.urlsafe_b64encode(key)[:-1].decode("ASCII")


def has_bootstrapped(volttron_path):
    return os.path.exists(os.path.join(volttron_path, 'env/bin/python'))


def python(volttron_path):
    return os.path.join(volttron_path, 'env', 'bin', 'python')


def is_loopback(vip_address):
    ip = vip_address.strip().lower().split("tcp://")[1]
    addr = ipaddress.ip_address(ip)
    return addr.is_loopback


def is_ip_private(vip_address):
    """ Determines if the passed vip_address is a private ip address or not.

    :param vip_address: A valid ip address.
    :return: True if an internal ip address.
    """
    ip = vip_address.strip().lower().split("tcp://")[1]


    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile("^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile("^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile("^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile("^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) is not None or priv_24.match(
        ip) is not None or priv_20.match(ip) is not None or priv_16.match(
        ip) is not None


def ip4_addresses():
    ip_list = []
    for interface in interfaces():
        for link in ifaddresses(interface)[AF_INET]:
            ip_list.append(link['addr'])
    return ip_list

# endregion


class InstanceState(enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    INVALID_PATH = "INVALID_PATH"
    NOT_BOOTSTRAPPED = "NOT_BOOTSTRAPPED"
    NEVER_STARTED = 'NEVER_STARTED'
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class AgentState(enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERRORED = "ERRORED"
    NOT_INSTALLED = "NOT_INSTALLED"
    UNKNOWN = "UNKNOWN"


class InstallPhaseEnum(enum.Enum):
    AGENT_INSTALL = "AGENT_INSTALL"
    ALLOW_EXTERNAL_CONNECTIONS = "ALLOW_EXTERNAL_CONNECTIONS"
    START_AGENTS = "START_AGENTS"
    UNINSTALL = "UNINSTALL"
    NONE = "NONE"


# region configuration handling functions
def _get_option_no_error(inst, section, option, default=None):
    try:
        value = inst.get(section, option)
    except NoOptionError:
        value = default
    return value


def _remove_option_no_error(inst, section, option):
    try:
        inst.remove_option(section, option)
        return True
    except NoOptionError:
        return False


def _validate_agent_config(agent_dict: dict):

    agent_keys = ['source', 'config', 'config_store']
    for id, item in agent_dict.items():

        logger().debug(f"{json.dumps(os.environ.copy(), indent=2)}")


def build_volttron_configfile(volttron_home, host_config_dict:dict):
    """
    :param volttron_home:
    :param params:
    :return:
    """
    host_config_cpy = {}
    if host_config_dict is not None:
        host_config_cpy = host_config_dict.copy()
    host_config_cpy.pop("participate-in-multiplatform", None)

    logger().debug(f"Building config from:\n{json.dumps(host_config_cpy, indent=2)}")
    cfg_loc = os.path.join(volttron_home, 'config')
    had_config = False
    changed = False
    if not os.path.isdir(volttron_home):
        os.makedirs(volttron_home)
    else:
        if os.path.isfile(cfg_loc):
            had_config = True

    parser = ConfigParser()

    if had_config:
        parser.read(cfg_loc)

    vc_address = None
    vc_serverkey = None
    vip_address = None
    bind_web_address = None

    if had_config:
        vc_address = _get_option_no_error(parser,
                                          'volttron',
                                          'voltttron-central-address')
        vc_serverkey = _get_option_no_error(parser,
                                            'volttron',
                                            'voltttron-central-serverkey')
        vip_address = _get_option_no_error(parser, 'volttron', 'vip-address')
        bind_web_address = _get_option_no_error(parser,
                                                'volttron', 'bind-web-address')
    else:
        changed = True
        parser.add_section('volttron')
        for k, v in host_config_cpy.items():
            parser.set('volttron', k, str(v))

    if not had_config:
        if 'volttron_central_addres' not in host_config_cpy:
            _remove_option_no_error(parser, 'volttron', 'volttron-central-address')
        else:
            parser.set('volttron', 'volttron-central-address',
                       host_config_cpy['volttron_central_address'])

        if 'volttron_central_serverkey' not in host_config_cpy:
            _remove_option_no_error(parser, 'volttron',
                                    'volttron-central-serverkey')
        else:
            parser.set('volttron', 'volttron-central-serverkey',
                       host_config_cpy['volttron_central_serverkey'])

        if 'vip_address' not in host_config_cpy:
            _remove_option_no_error(parser, 'volttron', 'vip-address')
        else:
            parser.set('volttron', 'vip-address',
                       host_config_cpy['vip_address'])

        # if not host_config_dict['enable_web']:
        #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        # elif not host_config_dict['bind_web_address']:
        #     _remove_option_no_error(parser, 'volttron', 'bind-web-address')
        # else:
        #     parser.set('volttron', 'bind-web-address',
        #                host_config_dict['bind_web_address'])

    parser.write(open(cfg_loc, 'w'))
    return changed
# endregion

# region VOLTTRON command functions
# def start_volttron(module):
#
#     instance_state = get_instance_state()
#     if instance_state == InstanceState.NOT_BOOTSTRAPPED:
#         module.exit_json(msg="A non-bootstrapped VOLTTRON cannot be started please run python bootstrap.py first.")
#
#     vroot = volttron_context.VOLTTRON_ROOT
#     vhome = volttron_context.VOLTTRON_HOME
#
#     if instance_state == InstanceState.RUNNING:
#         logger().debug("Instance is already running")
#         return
#
#     cmd = [volttron_context.VOLTTRON, '-L', 'examples/rotatinglog.py']
#     logger().debug(f"starting volttron {cmd}")
#     proc = subprocess.Popen(cmd,
#                             stdout=open('/dev/null', 'w'),
#                             stderr=open('logfile.log', 'a'),
#                             preexec_fn=os.setpgrp,
#                             cwd=volttron_context.VOLTTRON_ROOT)
#
#     logger().debug(proc)
#
#     current_state = wait_for_state(InstanceState.RUNNING, timeout=10)
#
#     if current_state != InstanceState.RUNNING:
#         force_kill_volttron()
#         current_state = wait_for_state(InstanceState.STOPPED, vhome, vroot)
#
#         if current_state != InstanceState.RUNNING:
#             module.fail_json(msg="Couldn't start VOLTTRON!")
#
#
# def stop_volttron():
#     cmd = [volttron_context.VCTL, 'shutdown', '--platform']
#     logger().debug(f"stopping volttron {cmd}")
#     proc = subprocess.Popen(cmd,
#                             stdout=open('/dev/null', 'w'),
#                             stderr=open('logfile.log', 'a'),
#                             preexec_fn=os.setpgrp,
#                             cwd=volttron_context.VOLTTRON_ROOT)
#
#
# def force_kill_volttron():
#     logger().debug("Force killing volttron")
#     proc = subprocess.Popen(['killall', '-9', 'volttron'],
#                             stdout=open('/dev/null', 'w'),
#                             stderr=open('logfile.log', 'a'))
#
#     proc = subprocess.Popen(['killall', '-9', 'python'],
#                             stdout=open('/dev/null', 'w'),
#                             stderr=open('logfile.log', 'a'))
# endregion


# def update_agents(agents_config_dict: dict):
#     agents_state = get_agents_state(agents_config_dict)
#     # all_installed_agents = set(agents_state.keys())
#     found_agents = set()
#     not_installed = set()
#
#     for identity, v in agents_state.items():
#         # If agent hasn't been installed but user wants the agent then go ahead and install it
#         if v['state'] == AgentState.NOT_INSTALLED.name and identity in agents_config_dict:
#             install_results = install_agent(identity, agents_config_dict[identity])
#
#     agents_state_after = get_agents_state(agents_config_dict)
#
#     # for id, agent_spec in agents_config_dict.items():
#     #     logger().debug(f"{id} => {agent_spec}")
#     #     if id in agents_state:
#     #         found_agents.add(id)
#     #         state = AgentState(agents_state[id]['state'])
#     #         if state == AgentState.NOT_INSTALLED:
#     #             install_agent(id, agent_spec)
#     agents_state_after = self.__discover_agents_status__(agents_config_dict)
#     return agents_state, agents_state_after














# def do_install_and_remove_agents_phase(agents_config_dict: dict, reinstall: bool = False):
#
#     agents_state = get_agents_state(agents_config_dict)
#     logger().debug(f"Doing install_remove_agent_state agents_state:\n {agents_state}")
#     # all_installed_agents = set(agents_state.keys())
#     found_agents = set()
#     not_installed = set()
#
#     for identity, v in agents_state.items():
#         # If agent hasn't been installed but user wants the agent then go ahead and install it
#         if v['state'] == AgentState.NOT_INSTALLED.name and identity in agents_config_dict:
#             install_results = install_agent(identity, agents_config_dict[identity])
#
#
# def do_allow_connections(agent_config_dict, volttron_host_dict):
#     logger().debug("I AM HERE!")
#     for host_facts in volttron_host_dict['results']:
#         logger().debug(host_facts['ansible_facts']['my_data']['ansible_local'])
#     # with open("/tmp/foofile", 'w') as fp:
#     #     fp.write(json.dumps(volttron_host_dict, indent=2))


# def do_start_tag_agents(ageent_config_dict):
#     pass
#
#
# def persist_facts():
#     instance_state = get_instance_state()
#     parser = ConfigParser()
#     config_loc = os.path.join(volttron_context.VOLTTRON_HOME, "config")
#     if os.path.isfile(config_loc):
#         parser = ConfigParser()
#         parser.read(config_loc)
#
#         for p, v in parser.items("volttron"):
#             instance_state['config'][p] = v
#
#     with open("/etc/ansible/facts.d", "w") as fp:
#         fp.write(json.dumps(instance_state, indent=2))
#
#
# def write_volttron_config_file(config_filename, host_config_dict:dict):
#     config = _host_dict_to_volttron_config_dict(host_config_dict)
#     with open(config_filename, 'w') as fp:
#         fp.write(json.dumps(config, indent=2))
#
#
# def format_return_dict(host_cfg:dict, agent_cfg:dict, instance_state: InstanceState, agents_state:dict):
#     serverkey_file = os.path.join(volttron_context.VOLTTRON_HOME, "keystore")
#     with open(serverkey_file) as fp:
#         keypair = json.loads(fp.read())
#         publickey = keypair['public']
#
#     formatted = {
#         "state":
#             {
#                 "instance_state": instance_state.name,
#                 "serverkey": publickey,
#                 "agents_state": agents_state,
#             },
#         "config":
#             {
#                 "vip-address": host_cfg['vip-address']
#             },
#         "options":
#             {
#                 "participate-in-multiplatform": host_cfg.get('participate-in-multiplatform', False)
#             }
#         }
#     return formatted


def to_bool(arg):
    abool = None
    try:
        abool = bool(arg)
    except TypeError:
        if isinstance(arg, str):
            if arg.upper() in ('YES', 'TRUE'):
                abool = True
            elif arg.upper() in ('NO', 'FALSE'):
                abool = False
    if abool is None:
        raise TypeError(f'Invalid type for value {arg} should be a boolean value')

    return abool


def valid_local_public_vip_address(vip_address):
    if vip_address is None:
        return False
    parsed = urlparse(vip_address)

    if parsed.scheme != 'tcp':
        return False

    if parsed.port is None:
        return False

    if parsed.port <= 1024 or parsed.port > 65535:
        return False

    try:
        addr = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False
    else:
        if addr not in ip4_addresses():
            return False

        return not addr.is_loopback


def dertimine_vip_address(should_be_public, vip_address, custom_port=22916):
    """

    :param should_be_public:
    :param vip_address:
    :param custom_port:
    :return:
    """
    vip_addr = None
    if vip_address is None:
        if should_be_public:
            public_addr = None
            for addr in ip4_addresses():
                if not ipaddress.ip_address(addr).is_loopback:
                    public_addr = addr
                    break
            vip_addr = f"tcp://{public_addr}:{custom_port}"
        else:
            vip_addr = f"tcp://127.0.0.1:22916"
    elif should_be_public and not valid_local_public_vip_address(vip_address):
        raise ValueError(f"Invalid vip address specified {vip_address} can not be loopback")
    elif not should_be_public and valid_local_public_vip_address(vip_address):
        raise ValueError(f"Invalid vip address specified {vip_address} should be loopback address")

    if vip_addr is None:
        raise ValueError("Couldn't determine vip-address for this host!")

    return vip_addr


def _host_dict_to_volttron_config_dict(host_config_dict: dict):
    config = host_config_dict.copy()

    # TODO build total list of all things that could be in the dictionary filter those out!
    config.pop('participate-in-multiplatform', None)
    config.pop('allow-external-connection', None)

    config.pop('custom-vip-ip', None)
    config.pop('custom-vip-port', None)


def _validate_and_build_updated_configuration(host_config_file, module: AnsibleModule):

    if not os.path.isfile(host_config_file):
        module.fail_json(msg=f"The host config file ({host_config_file} does not exist.")
    with open(host_config_file) as fp:
        host_cfg_loaded = yaml.safe_load(fp)
    if 'config' not in host_cfg_loaded:
        module.fail_json(msg="Must have config section in host configuration file.")
    if 'agents' not in host_cfg_loaded:
        module.fail_json(msg="Must have agents section in host configuration file.")
    logger().debug(f"host config loaded: {host_cfg_loaded}")
    host_config = host_cfg_loaded.get('config', {})
    agents_config = host_cfg_loaded.get('agents', {})

    # If no configuration paraementers are passed that's ok
    if host_config is None:
        host_config = {}

    # No agent configuration means that we have a platform just sitting there doing nothing.
    if agents_config is None:
        agents_config = {}

    # region verify and create vip-address for volttron config file
    multiplatform_participant = False
    try:
        logger().debug(f"host config is {host_config}")
        a_bool = to_bool(host_config.get('participate-in-multiplatform', False))
        multiplatform_participant = a_bool # to_bool(host_config.get('participate-in-multiplatform', False))
    except TypeError:
        module.fail_json(msg=f"Invalid value for participate-in-multiplatform")

    allow_external_connections = False
    try:
        allow_external_connections = to_bool(host_config.pop('allow-external-connections', multiplatform_participant))
    except TypeError:
        module.fail_json(msg=f"Invalid value for 'allow-external-connections'")

    custom_vip_ip = host_config.pop("custom-vip-ip", None)
    custom_vip_port = int(host_config.get("custom-vip-port", 22916))
    if custom_vip_port <= 1024 or custom_vip_port > 65535:
        module.fail_json(msg="Invalid custom-vip-port must be between 1024 and 65535")

    if custom_vip_ip:
        vip_address = f"tcp://{custom_vip_ip}:{custom_vip_port}"
    else:
        vip_address = None

    if multiplatform_participant and not allow_external_connections:
        module.fail_json(msg="Mismatch between allow-external-connections and participate-in-multiplatform")

    if multiplatform_participant or allow_external_connections:
        try:
            vip_address = dertimine_vip_address(should_be_public=True, vip_address=vip_address)
        except ValueError as ex:
            module.fail_json(msg=ex)
        else:
            host_config['vip-address'] = vip_address
    else:
        try:
            vip_address = dertimine_vip_address(should_be_public=False, vip_address=vip_address)
        except ValueError as ex:
            module.fail_json(msg=ex)
        else:
            host_config['vip-address'] = vip_address
    # endregion

    return host_config, agents_config


if __name__ == '__main__':
    main()
