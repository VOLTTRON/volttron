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
import shutil
import string
import sys
import os
import runpy
import subprocess
from volttron.platform import jsonapi

__author__ = 'Craig Allwardt<craig.allwardt@pnnl.gov>'
__version__ = '1.3.0'

parser = argparse.ArgumentParser()

parser.add_argument("agent", help="Path to the agent file to be executed.")
parser.add_argument("-s", "--silence", const=True, dest="silence", nargs="?",
                    help="Silence the help message.")
parser.add_argument("-n", "--no-config", action="store_true",
                    help="Don't include the default config in the agent directory.")
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


def write_required_statement(out=sys.stderr):
    out.write(
        """Required Environment Variables
    AGENT_VIP_IDENTITY - Required 
Optional Environmental Variables
    AGENT_CONFIG            - Set to <agent directory>/config by default
    VOLTTRON_HOME           - Set to ~/.volttron by default
"""
    )


sys.path.insert(0, abspath)
if not parsed.no_config:
    if not os.environ.get('AGENT_CONFIG'):
        path_found = None
        # Order of search is as follows config, config.yml, config.json
        for cfg in ('config', 'config.yml', 'config.json'):
            if os.path.exists(os.path.join(abspath, cfg)):
                path_found = os.path.join(abspath, cfg)
                break
        if not path_found:
            sys.stderr.write('AGENT_CONFIG variable not set.  Either set it or '
                             'put a config file in the root of the agent dir.')
            sys.exit()
        os.environ['AGENT_CONFIG'] = path_found

volttron_home = os.environ.get('VOLTTRON_HOME')

if not volttron_home:
    os.environ['VOLTTRON_HOME'] = os.path.abspath(
        os.path.expandvars(
            os.path.join(
                os.path.expanduser("~"), '.volttron')))
    volttron_home = os.environ.get('VOLTTRON_HOME')

# Now register the
agent_identity = os.environ.get('AGENT_VIP_IDENTITY')

if not agent_identity:
    sys.stderr.write("AGENT_VIP_IDENTITY MUST be set in environment\n")
    sys.exit(10)

valid_chars = "_.%s%s" % (string.ascii_letters, string.digits)

for c in agent_identity:
    if c not in valid_chars:
        sys.stderr.write("Invalid character found in AGENT_VIP_IDENTITY\n")
        sys.stderr.write("Valid characters are:\n\t{}\n".format(valid_chars))
        write_required_statement()
        sys.exit(10)

if agent_identity:
    new_dir = os.path.join(volttron_home, 'keystores', agent_identity)
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
        try:
            output = subprocess.check_output(['vctl', 'auth', 'keypair'],
                                             env=os.environ.copy(), universal_newlines=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            sys.stderr.write("Couldn't get key pair for identity: {}\n".format(
                agent_identity
            ))
            sys.stderr.write("Call was:\n\tvctl auth keypair\n")
            sys.stderr.write("Output of command: {}".format(e.output))
            sys.stderr.write("Your environment might not be setup correctly!")
            os.rmdir(new_dir)
            write_required_statement()
            sys.exit(20)
        else:
            keystore_file = os.path.join(new_dir, "keystore.json")
            json_obj = jsonapi.loads(output)
            with open(keystore_file, 'w') as fout:
                fout.write(output)

        pubkey = json_obj['public']
        try:
            params = ['vctl', 'auth', 'add',
                      '--credentials', "{}".format(pubkey), '--user_id', agent_identity,
                      '--capabilities', "edit_config_store",
                      '--comments', "Added from pycharm-launch.py script."
                      ]
            output = subprocess.check_output(params, env=os.environ.copy(), universal_newlines=True)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(str(e))
            sys.stderr.write("Command returned following output: {}".format(e.output))
            shutil.rmtree(new_dir)
            sys.stderr.write("Couldn't authenticate agent id: {}\n".format(
                agent_identity
            ))
            sys.stderr.write("Call was: {}\n".format(params))
            sys.stderr.write("Your environment might not be setup correctly!")
            write_required_statement()
            sys.exit(20)

if not parsed.silence:
    sys.stdout.write("For your information (-s) to not print this message.")
    write_required_statement(sys.stdout)

runpy.run_module(mod_name, run_name="__main__")
