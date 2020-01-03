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
import json
import os
import shutil

from ansible.cli import CLI
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.module_utils.common.collections import ImmutableDict
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible import context
import ansible.constants as C

from volttron.utils.prompt import prompt_response

os.environ['ANSIBLE_KEEP_REMOTE_FILES'] = "1"
C.DEFAULT_DEBUG = False


def do_init_systems(options):

    sudo_password = None
    while not sudo_password:
        sudo_password = prompt_response("SUDO Password: ", echo=False, mandatory=True)
        if sudo_password:
            break

    loader = DataLoader()

    context.CLIARGS = ImmutableDict(
        tags={}, listtags=False, listtasks=False, listhosts=False, syntax=False, connection='ssh',
        module_path=None, forks=10,
        remote_user='xxx', private_key_file=None,
        ssh_common_args=None, ssh_extra_args=None, sftp_extra_args=None, scp_extra_args=None,
        # become=True,
        # become_method='sudo',
        # sudo_pass='volttron',
        # become_user='root',
        verbosity=0, check=False, start_at_task=None)

    inventory = InventoryManager(loader=loader, sources=('examples/deployment/hosts.yml',))
    if options.limit:
        inventory.subset(options.limit)

    variable_manager = VariableManager(loader=loader, inventory=inventory,
                                       version_info=CLI.version_info(gitinfo=False))

    passwords = dict(become_pass=sudo_password)
    pbex = PlaybookExecutor(playbooks=[
        '/home/osboxes/repos/volttron/deployment/playbooks/remove-volttron.yml',
        '/home/osboxes/repos/volttron/deployment/playbooks/base-install.yml'],
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=passwords)

    results = pbex.run()


def add_deployment_subparser(add_parser_fn):
    deployment_parser = add_parser_fn('deploy', help="")
    subparsers = deployment_parser.add_subparsers(title='subcommands', metavar='',
                                                  dest='store_commands')
    init = add_parser_fn('hosts-init',
                         help="Installs required libraries, and clones volttron repository.",
                         subparser=subparsers)
    init.add_argument("-i", "--hosts-file", required=True,
                      help="A hosts yaml file modeled after ansible's inventory file.")
    init.add_argument("-l", "--limit",
                      help="Limit pattern for hosts in the inventory to run init on.")

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
    do_init_systems(opts)



