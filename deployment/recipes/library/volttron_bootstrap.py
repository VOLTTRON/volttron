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


# Note for reference, this module is developed per the pattern in the ansible
# docs here: https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_documenting.html

import itertools
import os
import subprocess
from ansible.module_utils.basic import AnsibleModule

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
        type: path
        default: $HOME/volttron
    volttron_env:
        description:
            - path to the VOLTTRON virtual environment to be used
        type:path
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
command:
    description: the full bootstrap command as executed
    type: str
    returned: always
return_code:
    description: the shell return code from the bootstrap subprocess
    type: str
    returned: always
'''


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
        params['volttron_root'] = f'{os.path.expanduser("~")}/volttron'
    if params['volttron_env'] is None:
        params['volttron_env'] = os.path.join(params['volttron_root'], 'env')

    return params

def get_package_list(volttron_python):
    ''' Use pip freeze to get a snapshot of the venv

    Per the pip documentation, PIP does *not* provide a library interface. We therefore
    use a subprocess to call 'pip freeze' and return a string representation of the result.
    '''
    freeze_result = subprocess.run(
        args=[volttron_python, '-m', 'pip', 'freeze'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return freeze_result.stdout.decode()

def execute_bootstrap(module):
    '''Construct and execute the volttron bootstrap command

    This function uses a subprocess to execute the VOLTTRON bootstrap in the configured
    virtual environment and with the set of optional features included per the passed parameters.
    The bootstrap script will always be run, but the packages in the environment will be checked
    prior to execution and compared after to determine if there were any changes made, this is
    used to report the 'changed' status for ansible.

    Note:
    - If the rabbitmq feature is included, the module will always report the status as "changed"
      more sophisticated change detection may be possible but is not yet implemented.
    - If the bootstrap process fails, this function will still return like normal, the returned
      dictionary includes a return_code field with the shell's return value, the calling scope
      is expected to evaluate and handle this value.

    '''
    results = {}
    params = module.params

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
        ## TODO is it possible to bootstrap with --rabbitmq and not cause change/disruption? I think the bootstrap script may always overwrite things, need to check.
        results['changed'] = True

    return results

def run_module():
    ''' execution logic for the ansible module

    This function is organized per the ansible documentation
    (https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_documenting.html)
    and implements the standardized logic sequence for a custom module:
    1. define the module's input spec
    2. define the module's return spec
    3. construct an instance of the AnsibleModule class using the above
       (ansible internally takes care of populating the params member)
    4. execute the module's custom logic
    4.1 update the params using update_logical_defaults
    4.2 call the bootstrap script in a subprocess
    5. use ansible's fail_json or exit_json functions to send results back to the ansible
       execution
    '''

    # define available arguments/parameters a user can pass to the module
    # these should match the DOCUMENTATION above
    module_args = {
        "volttron_root": {
            "type": "path",
            "required": True,
        },
        "volttron_env": {
            "type": "path",
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

    module.params = update_logical_defaults(module)

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    try:
        result.update(execute_bootstrap(module))
    except Exception as an_exception:
        module.fail_json(msg='volttron_bootstrap had an unhandled exception', error=repr(an_exception))

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
