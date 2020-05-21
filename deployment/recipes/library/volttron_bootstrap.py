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

import itertools
import os
import subprocess
import sys

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: volttron_bootstrap

short_description: Use VOLTTRON's bootstrap script to install user-space dependencies

description:
    - This module makes use of the packaged "bootstrap.py" script that is included with VOLTTRON to install extra dependencies.
    - It assumes that the full VOLTTRON source tree exists on the target system and executes the command using python's subprocess.
    - This is basically some extra logic on top of direct use of the shell module to add logic to detect when the system has been changed.

options:
    volttron_root:
        description:
            - path to the VOLTTRON source tree (where bootstrap.py will be found)
        required: true
    volttron_env:
        description:
            - path to the VOLTTRON virtual environment to be used
        default: $volttron_root/env
    features:
        description:
            - List of the bootstrap options to enable on the remote system.
            - Dynamically supports all options of bootstrap.py (run `python3 /path/to/bootstrap.py --help` for a complete listing)
            - Options should be listed without the argument prefix (`--`)
            - If missing or an empty list, bootstraps the base system without any extra options.
            - Any elements which evaluate to false is ignored, allowing logic statements in the playbook list elements.
        required: false
        type: list
        elements: string

'''

EXAMPLES = '''
# Bootstrap only the base system
- name: Test bootstrap the base system only
  volttron_bootstrap:
    volttron_root: /home/username/volttron

'''

RETURN = '''
bootstrap_stdout:
    description: the stdout from the bootstrap subprocess
    type: str
    returned: always
bootstrap_stderr:
    description: the stderr from the bootstrap subprocess
    type: str
    returned: always
'''

from ansible.module_utils.basic import AnsibleModule

def get_package_list(volttron_python):
    freeze_result = subprocess.run(
        args = [volttron_python, '-m', 'pip', 'freeze'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check = True,
    )
    return freeze_result.stdout.decode()

def execute_bootstrap(module):
    results = {}
    params = module.params

    if params['volttron_env'] is None:
        params['volttron_env'] = os.path.join(params['volttron_root'], 'env')
    results.update({'params': params})

    volttron_python = os.path.join(params['volttron_env'], 'bin/python')
    if not os.path.exists(volttron_python):
        module.fail_json("volttron python not found, volttron_bootstrap requires an existing venv")

    initial_packages = get_package_list(volttron_python)

    ## unpack one layer of nested lists
    features = itertools.chain(*[item if isinstance(item, list) else [item] for item in params['features']])
    bootstrap_result = subprocess.run(
        args = [
            volttron_python,
            os.path.join(params['volttron_root'], 'bootstrap.py'),
            *[f'--{feature}' for feature in features if feature],
        ],
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
    )
    results.update({
        'command': bootstrap_result.args,
        'return_code': bootstrap_result.returncode,
        'bootstrap_stdout': bootstrap_result.stdout.decode(),
        'bootstrap_stderr': bootstrap_result.stderr.decode(),
    })

    final_packages = get_package_list(volttron_python)

    if final_packages != initial_packages:
        results['changed'] = True
    if 'rabbitmq' in params['features']:
        results['changed'] = True

    return results

def run_module():
    # define available arguments/parameters a user can pass to the module
    # these should match the DOCUMENTATION above
    module_args = {
        "volttron_root": {
            "type": "str",
            "required": True,
        },
        "volttron_env": {
            "type": "str",
            "required": False,
            "default": None,
        },
        "features": {
            "type": "list",
            "required": False,
            "default": [],
        }
    }

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = {
        'changed': False,
        'bootstrap_stdout': '',
        'bootstrap_stderr': '',
    }

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    try:
        result.update(execute_bootstrap(module))
    except Exception as e:
        #import traceback
        #_, _, exc_traceback = sys.exc_info()
        module.fail_json(msg='volttron_bootstrap had an unhandled exception', error=repr(e))

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    #result['original_message'] = module.params['name']
    #result['message'] = 'goodbye'

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    #if module.params['new']:
    #    result['changed'] = True

    ## during the execution of the module, if there is an exception or a
    ## conditional state that effectively causes a failure, run
    ## AnsibleModule.fail_json() to pass in the message and the result
    #module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
