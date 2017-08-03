"""
This is a utility script to be able to debug modules from within pycharm or
run agents very easily from the command line.  This module is influenced
on the pydev-launch.py.

This script takes one parameter, the script to run.  If an AGENT_CONFIG is not
available in the environment and there is a config file within the root of the
agent's base directory then it will add it.

Example:

    # From the root of volttron git repository
    python scripts/pycharm-launch.py services/core/VolttronCentral/volttroncentral/agent.py

In order to execute from pycharms, set VOLTTRON_HOME and/or AGENT_CONFIG.  In
the script input box select scripts/pycharm-launcy.py.  In the script parameters
input box put services/core/VolttronCentral/volttroncentral/agent.py.
"""
import argparse
import sys
import os
import runpy
import subprocess
import json

__author__ = 'Craig Allwardt<craig.allwardt@pnnl.gov>'
__version__ = '1.0.0'

parser = argparse.ArgumentParser()

parser.add_argument("agent", help="Path to the agent file to be executed.")
parsed = parser.parse_args()

mod_name = [os.path.basename(parsed.agent)]
if not os.path.isfile(parsed.agent):
    sys.stdout.write("Passed argument must be a python file! {}".
                     format(parsed.agent))
    sys.exit()

abspath = os.path.abspath(os.path.join(parsed.agent, os.pardir))
if not os.path.exists(abspath):
    sys.stdout.write("Path does not exist: {}".format(abspath))
    sys.exit()

while True:
    if not os.path.exists(os.path.join(abspath, "__init__.py")):
        # now we can break because we are at the top of the passed package.
        break
    mod_name.insert(0, os.path.basename(abspath))
    abspath = os.path.abspath(os.path.join(abspath, os.pardir))

mod_name = '.'.join(mod_name)
mod_name = mod_name[:-3]

sys.path.insert(0, abspath)
if not os.environ.get('AGENT_CONFIG'):
    if not os.path.exists(os.path.join(abspath, 'config')):
        sys.stderr.write('AGENT_CONFIG variable not set.  Either set it or '
                         'put a config file in the root of the agent dir.')
        sys.exit()
    os.environ['AGENT_CONFIG'] = os.path.join(abspath, 'config')

volttron_home = os.environ.get('VOLTTRON_HOME')

if not volttron_home:
    os.environ['VOLTTRON_HOME'] = os.path.join(os.path.expandvars("~"), '.volttron')

# Now register the
agent_identity = os.environ.get('AGENT_VIP_IDENTITY')

if not agent_identity:
    sys.stderr.write("AGENT_VIP_IDENTITY MUST be set in environment\n")
    sys.exit(10)

if agent_identity:
    new_dir = os.path.join(volttron_home, 'keystores', agent_identity)
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
        try:
            output = subprocess.check_output(['vctl', 'auth', 'keypair'],
                                             env=os.environ.copy())
        except subprocess.CalledProcessError:
            sys.stderr.write("Couldn't get key pair for identity: {}\n".format(
                agent_identity
            ))
            sys.stderr.write("Call was:\n\tvctl auth keypair\n")
            sys.stderr.write("Your environment might not be setup correctly!")
            os.rmdir(new_dir)
            sys.exit(20)
        else:
            keystore_file = os.path.join(new_dir, "keystore.json")
            json_obj = json.loads(output)
            with open(keystore_file, 'w') as fout:
                fout.write(output)

        pubkey = json_obj['public']
        try:
            params = ['vctl', 'auth', 'add',
                      '--credentials', "{}".format(pubkey),
                      '--user_id', "{}".format(agent_identity),
                      '--comments', "Added from pycharm-launch.py script."
                      ]
            output = subprocess.check_output(params, env=os.environ.copy())
        except subprocess.CalledProcessError as e:
            os.rmdir(new_dir)
            sys.stderr.write(e.message)
            sys.stderr.write("Couldn't authenticate agent id: {}\n".format(
                agent_identity
            ))
            sys.stderr.write("Call was: {}\n".format(params))
            sys.stderr.write("Your environment might not be setup correctly!")
            sys.exit(20)

runpy.run_module(mod_name, run_name="__main__")
