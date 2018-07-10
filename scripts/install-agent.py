import argparse
import json
import logging
import os
import subprocess
from subprocess import Popen
import tempfile
from time import sleep
import sys

import yaml


logging.basicConfig(level=logging.WARN)
log = logging.getLogger(os.path.basename(__file__))

# determine whether or not the script is being run from an activated environment
# or not.  If we are then we need to call this script again from the correct
# python interpreter.
if not hasattr(sys, 'real_prefix'):
    inenv = False
else:
    inenv = True

if os.environ.get('WAS_CORRECTED'):
    corrected = True
else:
    corrected = False

# Call the script with the correct environment if we aren't activated yet.
if not inenv and not corrected:
    mypath = os.path.dirname(__file__)
    # Travis-CI puts the python in a little bit different location than
    # we do.
    if os.environ.get('CI') is not None:
        correct_python =subprocess.check_output(['which', 'python']).strip()
    else:
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

__version__ = '0.3'


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


def install_requirements(agent_source):
    req_file = os.path.join(agent_source, "requirements.txt")
    if os.path.exists(req_file):
        log.info("Installing requirements for agent.")
        cmds = ["pip", "install", "-r", req_file]
        try:
            subprocess.check_call(cmds)
        except subprocess.CalledProcessError:
            sys.exit(1)


def install_agent(opts, package, config):
    """
    The main installation method for installing the agent on the correct local
    platform instance.
    :param opts:
    :param package:
    :param config:
    :return:
    """
    if config is None:
        config = {}

    # if not a dict then config should be a filename
    if not isinstance(config, dict):
        config_file = config
    else:
        cfg = tempfile.NamedTemporaryFile()
        with open(cfg.name, 'w') as fout:
            fout.write(yaml.safe_dump(config)) # jsonapi.dumps(config))
        config_file = cfg.name

    try:
        with open(config_file) as fp:
            data = yaml.safe_load(fp)
            # data = json.load(fp)
    except:
        log.error("Invalid yaml/json config file.")
        sys.exit(-10)

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

    parsed = output.split("\n")

    # If there is not an agent with that identity:
    # 'Could not find agent with VIP IDENTITY "BOO". Installing as new agent
    # Installed /home/volttron/.volttron/packaged/listeneragent-3.2-py2-none-any.whl as 6ccbf8dc-4929-4794-9c8e-3d8c6a121776 listeneragent-3.2'

    # The following is standard output of an agent that was previously installed
    # If the agent was not previously installed then only the second line
    # would have been output to standard out.
    #
    # Removing previous version of agent "foo"
    # Installed /home/volttron/.volttron/packaged/listeneragent-3.2-py2-none-any.whl as 81b811ff-02b5-482e-af01-63d2fd95195a listeneragent-3.2

    if 'Could not' in parsed[0]:
        agent_uuid = parsed[1].split()[-2]
    elif 'Removing' in parsed[0]:
        agent_uuid = parsed[1].split()[-2]
    else:
        agent_uuid = parsed[0].split()[-2]

    output_dict = dict(agent_uuid=agent_uuid)

    if opts.start:
        cmds = [opts.volttron_control, "start", agent_uuid]
        process = Popen(cmds, env=env, stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        (outputdata, errordata) = process.communicate()

        # Expected output on standard out
        # Starting 83856b74-76dc-4bd9-8480-f62bd508aa9c listeneragent-3.2
        if 'Starting' in outputdata:
            output_dict['starting'] = True

    if opts.enable:
        cmds = [opts.volttron_control, "enable", agent_uuid]

        if opts.priority != -1:
            cmds.extend(["--priority", str(opts.priority)])

        process = Popen(cmds, env=env, stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        (outputdata, errordata) = process.communicate()
        # Expected output from standard out
        # Enabling 6bcee29b-7af3-4361-a67f-7d3c9e986419 listeneragent-3.2 with priority 50
        if "Enabling" in outputdata:
            output_dict['enabling'] = True
            output_dict['priority'] = outputdata.split("\n")[0].split()[-1]

    if opts.start:
        # Pause for agent_start_time seconds before verifying that the agent
        sleep(opts.agent_start_time)

        cmds = [opts.volttron_control, "status", agent_uuid]
        process = Popen(cmds, env=env, stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        (outputdata, errordata) = process.communicate()

        # 5 listeneragent-3.2 foo     running [10737]
        output_dict["started"] = "running" in outputdata
        if output_dict["started"]:
            pidpos = outputdata.index('[') + 1
            pidend = outputdata.index(']')
            output_dict['agent_pid'] = int(outputdata[pidpos: pidend])

    if opts.json:
        sys.stdout.write("%s\n" % json.dumps(output_dict, indent=4))
    if opts.csv:
        keylen = len(output_dict.keys())
        keyline = ''
        valueline = ''
        keys = output_dict.keys()
        for k in range(keylen):
            if k < keylen - 1:
                keyline += "%s," % keys[k]
                valueline += "%s," % output_dict[keys[k]]
            else:
                keyline += "%s" % keys[k]
                valueline += "%s" % output_dict[keys[k]]
        sys.stdout.write("%s\n%s\n" % (keyline, valueline))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(version=__version__)

    parser.add_argument("-a", "--vip-address", default=get_address(),
                        help="vip-address to connect to.")
    parser.add_argument("-vh", "--volttron-home", default=get_home(),
                        help="local volttron-home for the instance.")
    parser.add_argument("-vr", "--volttron-root", default=get_volttron_root(),
                        help="location of the volttron root on the filesystem.")
    parser.add_argument("-s", "--agent-source", required=True,
                        help="source directory of the agent which is to be installed.")
    parser.add_argument("-i", "--vip-identity", default=None,
                        help="identity of the agent to be installed (unique per instance)")
    parser.add_argument("-c", "--config", default=None, type=file,
                        help="agent configuration file that will be packaged with the agent.")
    parser.add_argument("-wh", "--wheelhouse", default=None,
                        help="location of agents after they have been built")
    parser.add_argument("-t", "--tag", default=None,
                        help="a tag is a means of identifying an agent.")
    parser.add_argument("-f", "--force", action='store_true',
                        help="agents are uninstalled by tag so force allows multiple agents to be removed at one go.")
    parser.add_argument("--priority", default=-1, type=int,
                        help="priority of startup during instance startup")
    parser.add_argument("--start", action='store_true',
                        help="start the agent during the script execution")
    parser.add_argument("--enable", action='store_true',
                        help="enable the agent with default 50 priority unless --priority set")
    parser.add_argument("-st", "--agent-start-time", default=5, type=int,
                        help="the amount of time to wait and verify that the agent has started up.")
    parser.add_argument("--csv", action='store_true',
                        help="format the standard out output to csv")
    parser.add_argument("--json", action="store_true",
                        help="format the standard out output to jso")
    parser.add_argument("--skip-requirements", action="store_true",
                        help="skip a requirements.txt file if it exists.")

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

    if opts.volttron_home.endswith('/'):
        log.warn("VOLTTRON_HOME should not have / on the end trimming it.")
        opts.volttron_home = opts.volttron_home[:-1]

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

    if opts.json and opts.csv:
        opts.csv = False
    elif not opts.json and not opts.csv:
        opts.json = True

    if os.environ.get('CI') is not None:
        opts.volttron_control = "volttron-ctl"
    else:
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

    if opts.force and opts.vip_identity is None:
        # If force is specified then identity must be specified to indicate the target of the force

        log.error(
            "Force option specified without a target identity to force.")
        sys.exit(-10)

    if not opts.skip_requirements:
        # use pip requirements.txt file and install dependencies if nessary.
        install_requirements(agent_source)

    opts.package = create_package(agent_source, wheelhouse, opts.vip_identity)

    if not os.path.isfile(opts.package):
        log.error("The wheel file for the agent was unable to be created.")
        sys.exit(-10)

    jsonobj = None
    # At this point if we have opts.config, it will be an open reference to the
    # passed config file.
    if opts.config:
        # Attempt to use the yaml parser directly first
        try:
            tmp_cfg_load = yaml.safe_load(opts.config.read())
            opts.config = tmp_cfg_load

        except yaml.scanner.ScannerError:
            sys.stderr.write("Invalid yaml file detect, attempting to parser using json parser.\n")
            opts.config.seek(0)
            should_parse_json = False
            for line in opts.config:
                line = line.partition('#')[0]
                if line.rstrip():
                    if line.rstrip()[0] in ('{', '['):
                        should_parse_json = True
                        break
            if not should_parse_json:
                sys.stderr.write("Invalid json file detected, must start with { or [ character.\n")
                sys.exit(1)

            # Yaml failed for some reason, could be invalid yaml or could
            # have embedded invalid character in a json file.  So now we
            # are going to try to deal with json here.

            tmpconfigfile = tempfile.NamedTemporaryFile()
            opts.config.seek(0)
            with open(tmpconfigfile.name, 'w') as fout:

                for line in opts.config:
                    line = line.partition('#')[0]
                    if line.rstrip():
                        fout.write(line.rstrip() + "\n")
            config_file = tmpconfigfile.name
            try:
                with open(tmpconfigfile.name) as f:
                    opts.config = jsonapi.loads(f.read())
            finally:
                tmpconfigfile.close()

    if opts.config:
        install_agent(opts, opts.package, opts.config)
    else:
        install_agent(opts, opts.package, {})




