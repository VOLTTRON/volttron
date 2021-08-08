#!/usr/bin/env python3

import argparse
import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(os.path.basename(__file__))

__version__ = "0.5"

# determine whether or not the script is being run from an activated environment
# or not.  If we are then we need to call this script again from the correct
# python interpreter.
if sys.base_prefix == sys.prefix:
    inenv = False
else:
    inenv = True

if os.environ.get("WAS_CORRECTED"):
    corrected = True
else:
    corrected = False

# Most of the time the environment will be run within a virtualenv
# however if we need to run the install agent in a non virtualized
# environment this allows us to do that.
ignore_env_check = os.environ.get("IGNORE_ENV_CHECK", False)

# Call the script with the correct environment if we aren't activated yet.
if not ignore_env_check and not inenv and not corrected:
    # Call this script in a subprocess with the correct python interpreter.
    cmds = [sys.executable, __file__]
    cmds.extend(sys.argv[1:])
    try:
        output = subprocess.call(cmds, env=os.environ)
        sys.exit(0)
    except RuntimeError:
        sys.exit(1)

# The rest of this script was moved into the volttron-control install command.
# This script will shell that script with this environment.

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-a", "--vip-address", default=None, help="vip-address to connect to."
    )
    parser.add_argument(
        "-vh",
        "--volttron-home",
        default=None,
        help="local volttron-home for the instance.",
    )
    parser.add_argument(
        "-vr",
        "--volttron-root",
        default=None,
        help="location of the volttron root on the filesystem.",
    )
    parser.add_argument(
        "-s",
        "--agent-source",
        required=True,
        help="source directory of the agent which is to be installed.",
    )
    parser.add_argument(
        "-i",
        "--vip-identity",
        default=None,
        help="identity of the agent to be installed (unique per instance)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        type=str,
        help="agent configuration file that will be packaged with the agent.",
    )
    parser.add_argument(
        "-t", "--tag", default=None, help="a tag is a means of identifying an agent."
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="agents are uninstalled by tag so force allows multiple agents to be removed at one go.",
    )
    parser.add_argument(
        "--priority",
        default=-1,
        type=int,
        help="priority of startup during instance startup",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="start the agent during the script execution",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="enable the agent with default 50 priority unless --priority set",
    )
    parser.add_argument(
        "-st",
        "--agent-start-time",
        default=5,
        type=int,
        help="the amount of time to wait and verify that the agent has started up.",
    )
    parser.add_argument(
        "--csv", action="store_true", help="format the standard out output to csv"
    )
    parser.add_argument(
        "--json", action="store_true", help="format the standard out output to jso"
    )
    parser.add_argument(
        "--skip-requirements",
        action="store_true",
        help="skip a requirements.txt file if it exists.",
    )

    opts = parser.parse_args()

    # Build up the command line that will be used to call the vctl
    # function to install an agent.
    cmds = ["install"]
    # Options first
    if opts.tag:
        cmds.extend(["--tag", str(opts.tag)])
    if opts.skip_requirements:
        cmds.extend(["--skip-requirements"])
    if opts.json:
        cmds.extend(["--json"])
    if opts.csv:
        cmds.extend(["--csv"])
    if opts.agent_start_time:
        cmds.extend(["--agent-start-time", str(opts.agent_start_time)])
    if opts.enable:
        cmds.extend(["--enable"])
    if opts.priority != -1:
        cmds.extend(["--priority", str(opts.priority)])
    if opts.force:
        cmds.extend(["--force"])
    if opts.tag:
        cmds.extend(["--tag", str(opts.tag)])
    if opts.config:
        cmds.extend(["--agent-config", str(opts.config)])
    if opts.vip_identity:
        cmds.extend(["--vip-identity", str(opts.vip_identity)])
    if opts.start:
        cmds.extend(["--start"])

    # This is the path to install an agent from.
    cmds.extend([opts.agent_source])

    cmds.insert(0, "volttron-ctl")
    # Use run because it is going to be in-charge of all of the output from
    # this command.
    subprocess.run(cmds, env=os.environ, stderr=sys.stderr, stdout=sys.stdout)
