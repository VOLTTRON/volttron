import argparse
import logging
import os
import subprocess
from subprocess import Popen
import tempfile
import sys


logging.basicConfig(level=logging.WARN)
log = logging.getLogger(os.path.basename(__file__))

if not hasattr(sys, 'real_prefix'):
    inenv = False
else:
    inenv = True

if not inenv:
    mypath = os.path.dirname(__file__)
    correct_python = os.path.abspath(
        os.path.join(mypath, '../env/bin/python'))
    if not os.path.exists(correct_python):
        log.error("Invalid location for the script {}".format(correct_python))
        sys.exit(-10)

    # Call this script in a subprocess with the correct python interpreter.
    cmds = [correct_python, __file__]
    cmds.extend(sys.argv[1:])
    process = subprocess.Popen(cmds, env=os.environ)
    process.wait()
    sys.exit(process.returncode)

from zmq.utils import jsonapi
from volttron.platform import get_address, get_home, get_volttron_root, \
    is_instance_running
from volttron.platform.packaging import create_package, add_files_to_package

__version__ = '0.1'


def _build_copy_env(opts):
    env = os.environ.copy()
    env['VOLTTRON_HOME'] = opts.volttron_home
    env['VIP_ADDRESS'] = opts.vip_address
    return env


def identity_exists(opts, identity):
    env = _build_copy_env(opts)
    cmds = [opts.volttron_control, "status"]

    process = subprocess.Popen(cmds, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    (stdoutdata, stderrdata) = process.communicate()

    for x in stdoutdata.split("\n"):
        if x:
            line_split = x.split()
            if identity == line_split[2]:
                return line_split[0]
    return False


def remove_agent(opts, agent_uuid):
    env = _build_copy_env(opts)
    cmds = [opts.volttron_control, "remove", agent_uuid]

    process = subprocess.Popen(cmds, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    process.wait()


def install_agent(opts, package, config):
    if not isinstance(config, dict):
        config_file = config
    else:
        cfg = tempfile.NamedTemporaryFile()
        with open(cfg.name, 'w') as fout:
            fout.write(jsonapi.dumps(config))
        config_file = cfg.name

    # Configure the whl file before installing.
    add_files_to_package(opts.package, {'config_file': config_file})
    env = _build_copy_env(opts)
    if opts.vip_identity:
        cmds = [opts.volttron_control, "upgrade", opts.vip_identity, package]
    else:
        cmds = [opts.volttron_control, "install", package]

    if opts.tag:
        cmds.extend(["--tag", opts.tag])

    process = Popen(cmds, env=env, stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE)
    (output, errorout) = process.communicate()

    # split the command line response for the install.
    agent_uuid = output.split('\n')[0].split()[-2]

    if opts.start:
        cmds = [opts.volttron_control, "start", agent_uuid]
        process = Popen(cmds, env=env, stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        (outputdata, errordata) = process.communicate()

    if opts.enable:
        cmds = [opts.volttron_control, "enable", agent_uuid]

        if opts.priority != -1:
            cmds.extend(["--priority", str(opts.priority)])

        process = Popen(cmds, env=env, stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        (outputdata, errordata) = process.communicate()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(version=__version__)

    parser.add_argument("-a", "--vip-address", default=get_address())
    parser.add_argument("-vh", "--volttron-home", default=get_home())
    parser.add_argument("-vr", "--volttron-root", default=get_volttron_root())
    parser.add_argument("-s", "--agent-source", required=True)
    parser.add_argument("-i", "--vip-identity", default=None)
    parser.add_argument("-c", "--config", default=None, type=file)
    parser.add_argument("-co", "--config-object", type=str, default="{}")
    parser.add_argument("-wh", "--wheelhouse", default=None)
    parser.add_argument("-t", "--tag", default=None)
    parser.add_argument("-f", "--force", action='store_true')
    parser.add_argument("--priority", default=-1, type=int)
    parser.add_argument("--start", action='store_true')
    parser.add_argument("--enable", action='store_true')

    opts = parser.parse_args()

    agent_source = opts.agent_source
    if not os.path.isdir(agent_source):
        if os.path.isdir(os.path.join(opts.volttron_root, agent_source)):
            agent_source = os.path.join(opts.volttron_root, agent_source)
        else:
            log.error("Invalid agent source directory specified.")
            sys.exit(-10)
    opts.agent_source = agent_source

    if not os.path.isfile(os.path.join(agent_source, "setup.py")):
        log.error("Agent source must contain a setup.py file.")
        sys.exit(-10)

    if not is_instance_running(opts.volttron_home):
        log.error("The instance at {} is not running".format(
            opts.volttron_home))
        sys.exit(-10)

    wheelhouse = opts.wheelhouse
    if not wheelhouse:
        wheelhouse = os.path.join(opts.volttron_home, "packaged")
    opts.wheelhouse = wheelhouse

    if opts.priority != -1:
        if opts.priority < 0 or opts.priority >= 100:
            log.error("Invalid priority specified must be between 1, 100")
            sys.exit(-10)
        opts.enable = True

    opts.volttron_control = os.path.join(opts.volttron_root,
                                         "env/bin/volttron-ctl")

    if opts.vip_identity is not None:
        # if the identity exists the variable will have the agent uuid in it.
        exists = identity_exists(opts, opts.vip_identity)
        if exists:
            if not opts.force:
                log.error(
                    "identity already exists, but force wasn't specified.")
                sys.exit(-10)
            # Note we don't remove the agent here because if we do that will
            # not allow us to update without losing the keys.  The
            # install_agent method either installs or upgrades the agent.

    opts.package = create_package(agent_source, wheelhouse, opts.vip_identity)

    if not os.path.isfile(opts.package):
        log.error("The wheel file for the agent was unable to be created.")
        sys.exit(-10)

    try:
        jsonobj = jsonapi.loads(opts.config_object)
    except Exception as ex:
        log.error("Invalid json passed in config_object: {}".format(ex.args))
        sys.exit(-10)

    if opts.config:
        install_agent(opts, opts.package, opts.config)
    else:
        install_agent(opts, opts.package, jsonobj)






