# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

# https://docs.ansible.com/ansible/latest/dev_guide/developing_api.html

import os
import sys
import yaml
from ansible.cli import CLI
from ansible.module_utils.common.collections import ImmutableDict
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible import context
import ansible.constants as C

from volttron.platform import get_volttron_root
from volttron.utils.prompt import prompt_response

#os.environ['ANSIBLE_KEEP_REMOTE_FILES'] = "1"
C.DEFAULT_DEBUG = False


def do_volttron_up(hosts_path, options):
    with open(hosts_path) as fp:
        cfg = yaml.safe_load(fp)

    missing_dirs = []
    missing_config_files = []
    config_files = {}
    config_dirs = []
    base_config_path = os.path.dirname(hosts_path)
    for k, v in cfg.items():
        if 'hosts' in v:
            for host in v['hosts']:

                host_config_dir = os.path.join(base_config_path, host)
                if not os.path.isdir(host_config_dir):
                    missing_dirs.append(host_config_dir)
                    continue
                host_config_file = os.path.join(host_config_dir, f"{host}.yml")
                if not os.path.isfile(host_config_file):
                    missing_config_files.append(host_config_file)
                    continue
                config_files[host] = host_config_file
    if missing_config_files or missing_dirs:
        sys.stderr.write("Invalid config directories:\n")
        for x in missing_dirs:
            sys.stderr.write(f"\t{x}\n")
        sys.stderr.write("Invalid config files:\n")
        for x in missing_config_files:
            sys.stderr.write(f"\t{x}\n")
        sys.exit(1)
    #
    # loader = DataLoader()
    # inventory = InventoryManager(loader=loader, sources=hosts_path)
    # var_manager = VariableManager(loader=loader, inventory=inventory,
    #                               version_info=CLI.version_info(gitinfo=False))
    #
    # Path environment available on the local system to copy files to
    # the target environments.
    os.environ['DEPLOYMENT_ROOT'] = os.path.dirname(hosts_path)
    for h, v in config_files.items():
        extra_vars = dict(host_install_file=v)
        #var_manager.set_host_variable(h, "host_install_file", v)
        #var_manager.get_vars()
        configs_path = os.path.join(os.path.dirname(v), "configs")
        if not os.path.isdir(configs_path):
            sys.stderr.write(f"No configuration files for host {h}")
        else:
            sys.stdout.write(f"{h} has configurations {configs_path}")
        # if os.path.isdir(configs_path):
        #     extra_vars['host_config_dir'] = configs_path
        #     var_manager.set_host_variable(h, "host_config_dir", configs_path)
        # else:
        #     sys.stderr.write(f"WARNING: configs directory {configs_path} does not exist")
        #var_manager.eextra_vars = extra_vars
    # assert cfg['all']['hosts'], f"Invalid agents specified in {hosts_path}"
    # assert cfg['']
    pbex = _get_executor(options.hosts_file, None, "volttron-instance", limit=options.limit,
                         extra_vars=None)
                         #variable_manager=var_manager, inventory=inventory)
    # print(pbex._variable_manager.get_vars())

    results = pbex.run()
    print(results)

def do_volttron_status(options):
    pbex = _get_executor(options.hosts_file, None, "status", limit=options.limit)

    results = pbex.run()

def do_destroy_systems(options):
    pbex = _get_executor(options.hosts_file, None, "remove-volttron", limit=options.limit)

    results = pbex.run()


def do_init_systems(options):

    sudo_password = None
    while not sudo_password:
        sudo_password = prompt_response("SUDO Password: ", echo=False, mandatory=True)
        if sudo_password:
            break

    pbex = _get_executor(options.hosts_file, sudo_password, "base-install", limit=options.limit)

    results = pbex.run()


def add_common(parser):
    """
    Adds common hosts-file and limit arguments to the passed parser.

    :param parser:
    :return:
    """
    parser.add_argument("-i", "--hosts-file", required=True,
                        help="A hosts yaml file modeled after ansible's inventory file.")
    parser.add_argument("-l", "--limit",
                        help="Limit pattern for hosts in the inventory to run init on.")


def add_deployment_subparser(add_parser_fn):
    deployment_parser = add_parser_fn('deploy', help="")
    subparsers = deployment_parser.add_subparsers(title='subcommands', metavar='',
                                                  dest='store_commands')
    init = add_parser_fn('init',
                         help="Installs required libraries, and clones volttron repository.",
                         subparser=subparsers)
    add_common(init)
    destroy = add_parser_fn('destroy',
                            help="Removes volttron and volttron_home from hosts",
                            subparser=subparsers)
    add_common(destroy)

    up = add_parser_fn('up',
                       help="Starts volttron platforms and install agents on the instance based upon agent.yml file",
                       subparser=subparsers)
    add_common(up)

    status = add_parser_fn('status',
                           help="Prints status of the platforms specified in the hosts file.",
                           subparser=subparsers)
    add_common(status)

    #
    #
    # provision = add_parser_fn('provision',
    #                           help="Deploys agents to remote platforms",
    #                           subparser=subparsers)
    # provision.add_argument('--platform-config',
    #                        help="Yaml based platform provision based upon schema")
    # provision.add_argument('--volttron-user')
    # provision.add_argument('--message-bus')


def do_deployment_command(opts):
    hosts_path = os.path.abspath(opts.hosts_file)
    if not os.path.isfile(hosts_path):
        sys.stderr.write(f"Invalid hosts-file path passed: {hosts_path}\n")
        sys.exit(1)
    opts.hosts_file = hosts_path

    if opts.store_commands == 'init':
        do_init_systems(opts)
    elif opts.store_commands == 'destroy':
        do_destroy_systems(opts)
    elif opts.store_commands == 'up':
        do_volttron_up(hosts_path, opts)
    elif opts.store_commands == 'status':
        do_volttron_status(opts)
    else:
        sys.stderr.write(f"Invalid argument to parser {opts.store_commands}")


def get_playbook(playbook):
    """
    Return full path to a playbook in the deployment/playbook directory.

    Playbook should be specified without a .yml extension.

    :param playbook:
    :return:
    """

    if playbook.endswith(".yml"):
        raise ValueError("Playbook should be passed without .yml extension")
    playbook_root = "deployment/playbooks"
    playbook_path = os.path.join(get_volttron_root(), playbook_root, f"{playbook}.yml")
    return playbook_path


def _get_cli_args() -> ImmutableDict:
    return ImmutableDict(
        tags={}, listtags=False, listtasks=False, listhosts=False, syntax=False, connection='ssh',
        module_path=None, forks=10,
        remote_user='xxx', private_key_file=None,
        ssh_common_args=None, ssh_extra_args=None, sftp_extra_args=None, scp_extra_args=None,
        # become=True,
        # become_method='sudo',
        # sudo_pass='volttron',
        # become_user='root',
        verbosity=0, check=False, start_at_task=None)


def _get_executor(hosts_file, sudo_password, playbooks, limit=None, variable_manager=None, inventory=None, extra_vars=None):
    if not playbooks:
        raise ValueError("playbooks must be specified!")

    if not isinstance(playbooks, list):
        playbooks = [playbooks]
    playbooks = [get_playbook(p) for p in playbooks]
    if inventory:
        loader = inventory._loader
    else:
        loader = DataLoader()
    context.CLIARGS = _get_cli_args()
    if inventory is None:
        inventory = InventoryManager(loader=loader, sources=hosts_file)

    if limit:
        inventory.subset(limit)

    if variable_manager is None:
        variable_manager = VariableManager(loader=loader, inventory=inventory,
                                           version_info=CLI.version_info(gitinfo=False))
    else:
        variable_manager.set_inventory(inventory)
    passwords = dict(become_pass=sudo_password)

    pbex = PlaybookExecutor(playbooks=playbooks,
                            inventory=inventory,
                            variable_manager=variable_manager,
                            loader=loader,
                            passwords=passwords)
    return pbex
