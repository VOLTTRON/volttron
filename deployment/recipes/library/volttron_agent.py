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

import json
import os
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
    volttron_venv:
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
    time_limit:
        description:
            - Time limit, in seconds, for subprocess calls used by the module.
        type: int
        default: 30
    agent_vip_id:
        description:
            - vip identity of the agent to be installed
        type: string
        required: true
    agent_state:
        description:
            - either "present" or "absent" indicates if the must or must not be present
        type: string
        default: 'present'
        choices:
            - 'present'
            - 'absent'
    agent_enabled:
        description:
            - indicates if the agent should be enabled to automatically start with the platform
            - (note that this is independent of, and does not imply, agent_running)
        type: bool
        default: false
    agent_priority:
        description:
            - Used to determined agent start order when a platform (re)starts. (ignored unless enabled==True)
        type: int
        default: 50
    agent_running:
        description:
            - indicates if the agent should be started as part of the install
            - (note that this is independent of enabling an agent)
        type: bool
        default: false
    agent_source:
        description:
            - path to the source directory for the agent.
            - If relative, is relative to agent_configs_dir
            - May use $VOLTTRON_HOME, $VOLTTRON_ROOT, or absolute path.
        type: path
        required: true
    agent_config:
        description:
            - If present, a path to the agent configuration file to package with the agent.
            - If relative, is relative to agent_configs_dir.
            - May use $VOLTTRON_HOME, $VOLTTRON_ROOT, or absolute path.
        type: path
        required: false
    agent_tag:
        description:
            - If not empty, defines a tag to apply to the agent
        type: string
        default: ''
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
    and volttron_venv) is None. When that is the case, we need to use other configurations
    and the runtime environment to compute the literal value of those parameters as documented.

    Note: this function takes a reference to the ansible module object and returns a new params
    dictionary object. It does not modify the object in the calling scope, though you can update
    that variable with the return.
    '''
    params = module.params

    if params['volttron_root'] is None:
        params['volttron_root'] = f'{os.path.join(os.path.expanduser("~"), "volttron")}'
    if params['volttron_venv'] is None:
        params['volttron_venv'] = os.path.join(params['volttron_root'], 'env')
    if params['volttron_home'] is None:
        params['volttron_home'] = f'{os.path.join(os.path.expanduser("~"), ".volttron")}'
    if params['agent_configs_dir'] is None:
        params['agent_configs_dir'] = f'{os.path.join(os.path.expanduser("~"), "configs")}'

    return params

def get_platform_status(module, process_env):
    '''use vctl to get info about running agents
    '''
    params = module.params
    cmd_result = subprocess.run(
        args=[
            os.path.join(params['volttron_venv'], 'bin/vctl'),
            '--json',
            'status',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=params['volttron_root'],
        env=process_env,
    )
    if cmd_result.returncode == 2 and "unrecognized arguments: --json" in cmd_result.stderr:
        module.fail_json(msg='agent installation currently requires a volttron version which supports the --json flag in vctl')
    if cmd_result.returncode != 0:
        module.fail_json(msg='agent state not recognized', subprocess_result=repr(cmd_result))

    try:
        agents = {}
        if not "No installed Agents found" in cmd_result.stderr.decode():
            agents = json.loads(cmd_result.stdout)
    except json.JSONDecodeError:
        module.fail_json(msg='unable to decode platform status', status_output=cmd_result.stdout.decode(), status_error=cmd_result.stderr.decode())
    except Exception as e:
        module.fail_json(msg='unexpected exception decoding stats', error_repr=repr(e))
    return agents

def remove_agent(agent_uuid, params, process_env):
    '''uninstall an agent
    '''
    module_result = {}

    #TODO: we can't remove an agent by VIP_ID, need to parse out a UUID
    cmd_result = subprocess.run(
        args=[
            os.path.join(params['volttron_venv'], 'bin/vctl'),
            'remove',
            agent_uuid,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=params['volttron_root'],
        env=process_env,
        check=True,
    )
    module_result.update({
        'command': cmd_result.args,
        'return_code': cmd_result.returncode,
        'stdout': cmd_result.stdout.decode(),
        'stderr': cmd_result.stderr.decode(),
        'changed': True,
    })

    return module_result

def install_agent(module, process_env):
    '''
    '''
    params = module.params
    module_result = {}

    install_cmd=[
        os.path.join(params['volttron_venv'], 'bin/python'),
        os.path.join(params['volttron_root'], 'scripts/install-agent.py'),
        '-i', params['agent_vip_id'],
        '-vh', params['volttron_home'],
        '-vr', params['volttron_root'],
        '-s', params['agent_source'],
    ]
    if params['agent_enabled']:
        install_cmd.append('--enable')
        install_cmd.extend(['--priority', f"{params['agent_priority']}"])
    if params['agent_running']:
        install_cmd.append('--start')
    if params['agent_config']:
        install_cmd.extend(['--config', params['agent_config']])
    try:
        module_result['command'] = ' '.join(install_cmd)
        module_result['process_env'] = process_env
        cmd_result = subprocess.run(
            args=' '.join(install_cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=params['agent_configs_dir'],
            env=process_env,
            shell=True,
            timeout=params['time_limit'],
        )
        module_result.pop('process_env')
    except subprocess.TimeoutExpired:
        module.fail_json(msg=f"agent install script timed out ({params['time_limit']})",
                         command=' '.join(install_cmd),
                         process_env=process_env,
                        )
    except Exception as e:
        module.fail_json(msg=f"subprocess to install agent failed with unhandled exception: {repr(e)}",
                         command=' '.join(install_cmd),
                         process_env=process_env,
                        )
    module_result.update({
        'command': cmd_result.args,
        'return_code': cmd_result.returncode,
        'stdout': cmd_result.stdout.decode(),
        'stderr': cmd_result.stderr.decode(),
        'changed': True,
    })

    return module_result

def add_config_store():
    '''
    '''
    ##TODO: add logic for adding config store entries to an agent

#TODO make sure there are sufficient try/except blocks to return useful
#     failure case data
def execute_task(module):
    '''
    '''
    results = {'process_results':[]}
    params = module.params

    subprocess_env = dict(os.environ)
    subprocess_env.update({
        'VOLTTRON_HOME': params['volttron_home'],
        'VOLTTRON_ROOT': params['volttron_root'],
    })

    existing_agents = get_platform_status(module, subprocess_env)
    results['initial_agents'] = existing_agents

    if params['agent_state'] == 'present':
        if params['agent_vip_id'] in existing_agents:
            results['changed'] = False
        else:
            results.update(install_agent(module=module, process_env=subprocess_env))
            if results['return_code']:
                module.fail_json(msg='install agent failed', subprocess_details=results)
    elif params['agent_state'] == 'absent':
        if params['agent_vip_id'] not in existing_agents:
            results['changed'] = False
        else:
            results.update(remove_agent(agent_uuid=existing_agents[params['agent_vip_id']]['agent_uuid'], params=params, process_env=subprocess_env))
    else:
        module.fail_json(msg='agent state not recognized')

    results['final_agents'] = get_platform_status(module, subprocess_env)
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
        "volttron_venv": {
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
        "time_limit": {
            "type": "int",
            "default": 30,
        },
        "agent_vip_id": {
            "type": "str",
            "required": True,
        },
        "agent_state": {
            "type": "str",
            "default": "present",
            "choices": [
                "present",
                "absent",
            ],
        },
        "agent_enabled": {
            "type": "bool",
            "default": False,
        },
        "agent_priority": {
            "type": "int",
            "default": 50,
        },
        "agent_running": {
            "type": "bool",
            "default": False,
        },
        "agent_source": {
            "type": "path",
            "required": True,
        },
        "agent_config": {
            "type": "path",
            "required": False,
        },
        "agent_tag": {
            "type": "str",
            "default": '',
        },
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
        import traceback
        module.fail_json(msg='volttron_agent had an unhandled exception', exception=repr(e), trace=traceback.format_stack())

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
