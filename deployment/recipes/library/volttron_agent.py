#!/usr/bin/python
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


# Note for reference, this module is developed per the patter in the ansible
# docs here: https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_documenting.html

import os
import psutil
import subprocess

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: volttron_agents

short_description: Manage the state of agents in a platform

description:
    - Manage the lifecycle and configuration state of agents installed in a platform.
    - Note, thorough inspection of agent configuration and state is subtle; this module is
      intended to simply fail with a useful message in those cases. It may be necessary to
      remove and re-install agents in these situations.
    - Note, this module assumes that there is a running platform available for it to interact with.

options:
    volttron_root:
        description:
            - path to the VOLTTRON source tree (where start_volttron and stop_volttron are found)
        default: $HOME/volttron
        type: path
    volttron_env:
        description:
            - path to the virtual environment where VOLTTRON is installed
        default: $volttron_root/env
        type: path
    volttron_home:
        description:
            - path to the VOLTTRON_HOME directory for this instance
        default: $HOME/.volttron'
        type: path
    agent_configs_dir:
        description:
            - path to directory on the remote system where agent configuration files have been placed
        default: $HOME/configs
        type: path
    agents:
        description:
            - A list of dictionaries, each of which defines an agent in the system.
            - The following keys are supported:
                - 'vip_id' (string, required): vip identity
                - 'state' (string, default="present"): either "present" or "absent" indicates if the
                                                       must or must not be present
                - 'enabled' (bool, default=False): indicates if the agent should be enabled to
                                                   automatically start with the platform
                - 'priority' (int, default=50): ignored unless enabled==True. Used to determined
                                                agent start order when a platform (re)starts.
                - 'running' (bool, default=False): indicates if the agent should be running or not.
                - 'source' (string - path, required): path to the source directory for the agent.
                                                      If relative, is relative to agent_configs_dir, may use
                                                      VOLTTRON_HOME, VOLTTRON_ROOT, or absolute path.
                - 'config' (string - path, optional): if present, a path to the agent configuration file
                                                      to package with the agent. If relative, is relative
                                                      to agent_configs_dir, may use VOLTTRON_HOME, VOLTTRON_ROOT,
                                                      or absolute path.
                - 'tag' (string, default=''): if not empty, defines a tag to apply to the agent
        type: list
        required: true
        elements: dict

'''

#TODO: add some number of examples
EXAMPLES = '''
'''

RETURN = '''
process_results:
    type: list
    description: a list of dictionaries containing the result details from interacting with each agent
                 each element will include stdout, stderr, command, and return_code
    elements: dict
changed_agents:
    type: list
    description: a list of the VIP Identities of agents which were changed
'''

from ansible.module_utils.basic import AnsibleModule

def update_logical_defaults(module):
    '''
    Compute the as-documented default values for parameters assigned a default
    'None' value by the ansible interface.

    Programmatically, the default value assigned by ansible to these variables (volttron_root,
    and volttron_env) is None. When that is the case, we need to use other configurations
    and the runtime environment to compute the literal value of those parameters as documented.

    Note: this function takes a reference to the ansible module object and returns a new params
    dictionary object. It does not modify the object in the calling scope, though you can update
    that variable with the return.
    '''
    params = module.params

    if params['volttron_root'] is None:
        params['volttron_root'] = f'{os.path.join(os.path.expanduser("~"), "volttron")}'
    if params['volttron_env'] is None:
        params['volttron_env'] = os.path.join(params['volttron_root'], 'env')
    if params['volttron_home'] is None:
        params['volttron_home'] = f'{os.path.join(os.path.expanduser("~"), ".volttron")}'
    if params['agent_configs_dir'] is None:
        params['agent_configs_dir'] = f'{os.path.join(os.path.expanduser("~"), "configs")}'

    return params

def install_agent(agent_specs, process_env):
    '''execute a subprocess to install and configure an agent
    '''

def remove_agent(agent_id, process_env):
    '''uninstall an agent
    '''
    remove_result = subprocess.run(
    )

##TODO: add logic for removing an agent
##TODO: add logic for installing an agent
##TODO: add logic for adding config store entries to an agent

def execute_task(module):
    ''' ensure that the platform is in the desired running/not-running state

    Uses the VOLTTRON_PID file in the configured volttron_home to determine if the platform
    is currently running, and compares that against the configured desired state. If the
    state does not match the desired state, uses a subprocess to call either the stop-volttron
    or the start-volttron script as appropriate to reach the desired state and then uses the
    (possibly updated) VOLTTRON_PID file to re-check the resulting state.

    In the even that the detected state is found to be present, the function returns with 'changed'=False
    If a start or stopped script is run, 'changed' will always be True, but the process may
    still report as failed if either the start/stop script return code indicates an error, or if
    the state detected after the script is run does not match the desired state.

    Note:
    - In the event of failure, this function will call the module's fail_json method immediately.
    '''
    results = {'process_results':[]}
    params = module.params

    # since not in the desired state, attempt to move to that state
    subprocess_env = dict(os.environ)
    subprocess_env.update({
        'VOLTTRON_HOME': params['volttron_home'],
        'VOLTTRON_ROOT': params['volttron_root'],
    })

    # if no failures, return results
    return results

def run_module():
    '''execution logic for the ansible module

    This function is organized per the ansible documentation
    (https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_documenting.html)
    and implements the standardized logic sequence for a custom module:
    1. define the module's input spec
    2. define the module's return spec
    3. create an instance of the AnsibleModule class using the above
       (ansible internally takes care of populating hte params member)
    4. execute the module's custom logic
    4.1 update the params using update_logical_defaults
    4.2 parse the params into a desired action, check if it needs to be executed, and possibly
        execute (execute_task function)
    5. use ansible's exit_json or fail_json to ensure results are sent back to the execution
       environmentas expected.
    '''
    #TODO: update the above

    # define available arguments/parameters a user can pass to the module
    # these should match the DOCUMENTATION above
    module_args = {
        "volttron_root": {
            "type": "path",
            "default": None,
        },
        "volttron_env": {
            "type": "path",
            "default": None,
        },
        "volttron_home": {
            "type": "path",
            "required": False,
            "default": None,
        },
        "agent_configs_dir": {
            "type": "path",
            "default": None,
        },
        "agents": {
            "type": "dict",
            "required": True,
        }
    }

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = {
        'changed': False,
        'stdout': '',
        'stderr': '',
        'command': [],
        'return_code': None,
    }

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    module.params = update_logical_defaults(module)

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # actually execute the task
    try:
        result.update(execute_task(module))
    except Exception as e:
        module.fail_json(msg='volttron_bootstrap had an unhandled exception', error=repr(e))

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
