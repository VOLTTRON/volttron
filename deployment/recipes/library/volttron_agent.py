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

import csv
import io
import glob
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
    agent_spec:
        description:
            - a dictionary of configuration details for the agent
            - valid keys are:
                - agent_state: (either 'present' or 'absent'), indicates if the agent should or should not be present
                - agent_enabled: (bool), if true, indicates that the agent should be started when the platform starts (does not imply running)
                - agent_priority: (int; default 50) sets the priority ordering for starting an enalbed agent
                - agent_running: (bool), if true, indicates that the agent should be started as it is installed (does not imply enabled)
                - agent_tag: (string), if installing the agent, apply this tag
                - agent_config_store: (list) a list of config store entries to apply to the agent, each entry is a dict supporting the following keys:
                    - absolute_path: (bool, default False) if true, the agents path configuration is assumed absolute on the remote, otherwise the path is prepended with the agent_configs_dir
                    - path: (string - path) path to either a file to add to the config store, or a directory of files to add. If a directory, all files contained will be added to the config store
                    - name: (string) name of the entry to place in the config store. For files this is used instead of the file name. For directories this is prefixed to every contained file (the directory is included recursively and intermediate directories are included in the name).

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

    # set agent spec optional params to their defaults if missing
    params['agent_spec']['agent_state'] = params['agent_spec'].get('agent_state', 'present')
    params['agent_spec']['agent_tag'] = params['agent_spec'].get('agent_tag', '')
    params['agent_spec']['agent_config_store'] = params['agent_spec'].get('agent_config_store', [])

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
    #params = module.params
    module_spec = module.params['agent_spec']
    module_result = {}

    install_cmd=[
        os.path.join(module.params['volttron_venv'], 'bin/python'),
        os.path.join(module.params['volttron_root'], 'scripts/install-agent.py'),
        '-i', module.params['agent_vip_id'],
        '-vh', module.params['volttron_home'],
        '-vr', module.params['volttron_root'],
        '-s', module_spec['agent_source'],
    ]
    if module_spec.get('agent_enabled', False):
        install_cmd.append('--enable')
        install_cmd.extend(['--priority', f"{module_spec.get('agent_priority', 50)}"])
    if module_spec.get('agent_running', False):
        install_cmd.append('--start')
    if module_spec.get('agent_config', False):
        install_cmd.extend(['--config', module_spec['agent_config']])
    if module_spec.get('agent_tag', ''):
        install_cmd.extend(['-t', module_spec['agent_tag']])
    try:
        module_result['command'] = ' '.join(install_cmd)
        module_result['process_env'] = process_env
        cmd_result = subprocess.run(
            args=' '.join(install_cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=module.params['agent_configs_dir'],
            env=process_env,
            shell=True,
            timeout=module.params['time_limit'],
        )
        module_result.pop('process_env')
    except subprocess.TimeoutExpired:
        module.fail_json(msg=f"agent install script timed out ({module.params['time_limit']})",
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

def resolve_config_store(module, process_env):
    '''
    '''
    original_store = get_agent_config_store(module, process_env)
    target_store = {}

    def _construct_entry_args(path, name=None, absolute_path=False, present=True):
        '''
        '''
        action = None
        if not present:
            if name not in original_store:
                # the config store entry should not exist and already does not
                action = (lambda: {}, {})
            else:
                # the config store entry exists and should be removed
                action = (remove_config_store,
                          {'module': module,
                           'process_env': process_env,
                           'identity': module.params['agent_vip_id'],
                           'stored_name': name,
                          }
                )
        else:
            data_path = None
            if absolute_path:
                data_path = path
            else:
                data_path = os.path.join(module.params['agent_configs_dir'], path)
            if name in original_store:
                # the config store entry already exists, check it
                desired_data = open(data_path, 'r').read()
                # TODO
                target_store[name] = desired_data
                data_differs = False
                if name.endswith('.json'):
                    data_differs = json.loads(desired_data) == json.loads(original_store[name])
                elif name.endswith('.csv'):
                    data_differs = list(csv.reader(io.StringIO(desired_data))) == list(csv.reader(io.StringIO(original_store[name])))
                else:
                    data_differs = (desired_data == original_store[name])
                if data_differs:
                    # the config store will not be changed, no action
                    action = (lambda: {}, {})
                else:
                    action = (add_config_store,
                              {'module': module,
                               'process_env': process_env,
                               'identity': module.params['agent_vip_id'],
                               'stored_name': name,
                               'file_path': data_path,
                              }
                    )
            else:
                # the config store entry is missing, add it
                action = (add_config_store,
                          {'module': module,
                           'process_env': process_env,
                           'identity': module.params['agent_vip_id'],
                           'stored_name': name,
                           'file_path': data_path,
                          }
                )
        return action

    store_entries = []
    for a_config_listing in module.params['agent_spec']['agent_config_store']:
        data_path = None
        if a_config_listing.get('absolute_path', False):
            data_path = a_config_listing['path']
        else:
            data_path = os.path.join(module.params['agent_configs_dir'], a_config_listing['path'])
        ##module.fail_json(msg=f'determed that data_path is {data_path}')
        if os.path.isdir(os.path.join(module.params['agent_configs_dir'], a_config_listing['path'])):
            for a_file in glob.glob(os.path.join(data_path, '**'), recursive=True):
                if os.path.isdir(a_file):
                    continue
                stored_name = a_file.split(a_config_listing['path'])[-1].lstrip('/')
                stored_name = os.path.join(a_config_listing.get('name',''), stored_name)
                store_entries.append(_construct_entry_args(
                    a_file,
                    name=stored_name,
                    absolute_path=True,
                    present=a_config_listing.get('present', True),
                ))
        else:
            # the name of the config entry will be the same as the file path if not specified
            this_name = a_config_listing.get('name', a_config_listing['path'])
            store_entries.append(_construct_entry_args(
                a_config_listing['path'],
                this_name,
                a_config_listing.get('absolute_path', False),
                a_config_listing.get('present', True),
            ))

    resolver_results = []
    changed = False
    for resolver_function, resolver_args in store_entries:
        a_resolution = resolver_function(**resolver_args)
        changed = changed or a_resolution.get('changed', False)
        resolver_results.append(a_resolution)

    return {'original_store': original_store,
            'target_store': target_store,
            'changed': changed,
            'config_store_changed': changed,
            'config_store_resolutions': resolver_results,
           }

def get_agent_config_store(module, process_env):
    '''
    '''
    config_store = {}
    list_result = subprocess.run(
        args=' '.join([
            os.path.join(module.params['volttron_venv'], 'bin/vctl'),
            'config',
            'list',
            module.params['agent_vip_id'],
        ]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=process_env,
        shell=True,
        timeout=module.params['time_limit'],
    )
    if list_result.returncode:
        module.fail_json(msg=f"listing config store failed", stdout=list_result.stdout.decode(), stderr=list_result.stderr.decode())
    for a_store in list_result.stdout.decode().split():
        store_data = subprocess.run(
            args=' '.join([
                os.path.join(module.params['volttron_venv'], 'bin/vctl'),
                'config',
                'get',
                module.params['agent_vip_id'],
                a_store,
            ]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
            shell=True,
            timeout=module.params['time_limit'],
        )
        if store_data.returncode:
            module.fail_json(msg=f'getting config store {a_store} failed', stdout=store_data.stdout.decode(), stderr=store_data.stderr.decode())
        config_store[a_store] = store_data.stdout.decode()
    return config_store

def remove_config_store(module, process_env, identity, stored_name):
    '''
    '''
    module_result = {}

    cmd=[
        os.path.join(module.params['volttron_venv'], 'bin/vctl'),
        'config',
        'delete',
        identity,
        stored_name,
    ]
    cmd_result = subprocess.run(
        args=cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=module.params['volttron_root'],
        env=process_env,
    )
    if cmd_result.returncode:
        module.fail_json(msg=f'failed while deleting config store [{stored_name}] for agent [{identity}]',
                         command=' '.join(cmd),
                         stdout=cmd_result.stdout.decode(),
                         stderr=cmd_result.stderr.decode(),
        )
    module_result.update({
        'command': ' '.join(cmd),
        'return_code': cmd_result.returncode,
        'stdout': cmd_result.stdout.decode(),
        'stderr': cmd_result.stderr.decode(),
        'changed': True,
    })

    return module_result

def add_config_store(module, process_env, identity, stored_name, file_path):
    ''' add data to an agent's config store
    '''
    module_result = {}

    cmd=[
        os.path.join(module.params['volttron_venv'], 'bin/vctl'),
        'config',
        'store',
        identity,
        stored_name,
        file_path,
    ]
    if file_path.endswith('json'):
        cmd.append('--json')
    if file_path.endswith('csv'):
        cmd.append('--csv')
    cmd_result = subprocess.run(
        args=cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=module.params['volttron_root'],
        env=process_env,
    )
    if cmd_result.returncode:
        module.fail_json(msg=f'failed while adding config store [{stored_name}] to agent [{identity}]',
                         command=' '.join(cmd),
                         stdout=cmd_result.stdout.decode(),
                         stderr=cmd_result.stderr.decode(),
        )
    module_result.update({
        'command': cmd_result.args,
        'return_code': cmd_result.returncode,
        'stdout': cmd_result.stdout.decode(),
        'stderr': cmd_result.stderr.decode(),
        'changed': True,
    })

    return module_result

def execute_task(module):
    '''
    '''
    results = {
        'process_results':[],
        'changed': False,
    }
    agent_spec = module.params['agent_spec']

    subprocess_env = dict(os.environ)
    subprocess_env.update({
        'VOLTTRON_HOME': module.params['volttron_home'],
        'VOLTTRON_ROOT': module.params['volttron_root'],
    })

    existing_agents = get_platform_status(module, subprocess_env)
    results['initial_agents'] = existing_agents

    if agent_spec['agent_state'] == 'present':
        if module.params['agent_vip_id'] in existing_agents:
            pass
        else:
            results.update(install_agent(module=module, process_env=subprocess_env))
            if results['return_code']:
                module.fail_json(msg='install agent failed', subprocess_details=results)
        if agent_spec['agent_config_store']:
            results.update(resolve_config_store(module=module, process_env=subprocess_env))
            results.update({'zzzz_config_store': True})
        else:
            pass
    elif agent_spec['agent_state'] == 'absent':
        if agent_spec['agent_vip_id'] not in existing_agents:
            pass
        else:
            results.update(remove_agent(agent_uuid=existing_agents[agent_spec['agent_vip_id']]['agent_uuid'], params=module.params, process_env=subprocess_env))
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
        "agent_spec": {
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
        import traceback
        raise e
        #module.fail_json(msg='volttron_agent had an unhandled exception', exception=repr(e), trace=traceback.format_stack())

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
