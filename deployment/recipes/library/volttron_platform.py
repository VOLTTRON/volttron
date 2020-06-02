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
module: volttron_platform

short_description: Manage the state of an existing platform

description:
    - Manage the state of an installed VOLTTRON platform (start/stop).
    - Note that there is no 'restart' state (that would not be idempotent), you can use two tasks to set "stopped" immediately followed by "running"

options:
    volttron_root:
        description:
            - path to the VOLTTRON source tree (where start_volttron and stop_volttron are found)
        default: $HOME/volttron
        type: string
    volttron_home:
        description:
            - path to the VOLTTRON_HOME directory for this instance
        default: $HOME/.volttron'
        type: string
    state:
        description:
            - set if the platform should be "running" or "stopped"
        default: "running"
        choices:
            - "running"
            - "stopped"
        type: string

'''

EXAMPLES = '''
# Start the platform
- name: Start platform
  volttron_platform:
    volttron_root: /home/username/volttron
    state: running

'''

RETURN = '''
stdout:
    description: the stdout from the [start,stop]_volttron script
    type: str
    returned: when subprocess is executed
stderr:
    description: the stderr from the [start,stop]_volttron script
    type: str
    returned: when subprocess is executed
command:
    description: the full details of the command as executed in subprocess
    type: list
    elements: string
    returned: when subprocess is executed
return_code:
    description: the shell return code produced by the subprocess
    type: int
    returned: when subprocess is executed
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
    if params['volttron_home'] is None:
        params['volttron_home'] = f'{os.path.join(os.path.expanduser("~"), ".volttron")}'

    return params

def check_pid(pid_file):
    '''check if a process corresonding to a PID file exists

    Given a potential path to a PID file, return a boolean indicating if there
    exists a corresponding process.

    Note that if the file does not exist, the function also returns False
    '''
    is_running = False
    if os.path.exists(pid_file):
        pid = int(open(pid_file, 'r').read())
        if psutil.pid_exists(pid):
            is_running = True
    return is_running

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
    results = {}
    params = module.params

    available_scripts = {
        "running": "./start-volttron",
        "stopped": "./stop-volttron",
    }

    is_running = False
    pid_file_path = os.path.join(params['volttron_home'], 'VOLTTRON_PID')
    is_running = check_pid(pid_file_path)

    # if already in the desired state, do nothing
    if params['state'] == "running" and is_running:
        return results
    if params['state'] == "stopped" and not is_running:
        return results

    # since not in the desired state, attempt to move to that state
    subprocess_env = dict(os.environ)
    subprocess_env.update({
        'VOLTTRON_HOME': params['volttron_home'],
    })
    script_result = subprocess.run(
        args = [
            available_scripts[params['state']],
        ],
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
        cwd = params['volttron_root'],
        env = subprocess_env,
        preexec_fn=os.setpgrp,
    )
    results.update({
        'command': script_result.args,
        'return_code': script_result.returncode,
        'stdout': script_result.stdout.decode(),
        'stderr': script_result.stderr.decode(),
        'changed': True,
    })

    # if script failed, propagate failure
    if script_result.returncode != 0:
        module.fail_json(msg=f'{available_scripts[params["state"]]} returned an error', **results)
    # re-check state and fail if not in desired state
    is_running = check_pid(pid_file_path)
    if params['state'] == "running" and not is_running:
        module.fail_json(msg='start script returned success but VOLTTRON PID not found', **results)
    if params['state'] == 'stopped' and is_running:
        module.fail_json(msg='stop script returned success but VOLTTRON PID still exists', **results)

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

    # define available arguments/parameters a user can pass to the module
    # these should match the DOCUMENTATION above
    module_args = {
        "volttron_root": {
            "type": "str",
            "default": None,
        },
        "volttron_home": {
            "type": "str",
            "required": False,
            "default": None,
        },
        "state": {
            "type": "str",
            "required": False,
            "default": "running",
            "choices": [
                "running",
                "stopped",
            ]
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
