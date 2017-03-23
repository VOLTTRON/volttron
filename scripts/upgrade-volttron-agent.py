import argparse
import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.DEBUG)

if not hasattr(sys, 'real_prefix'):
    inenv = False
else:
    inenv = True

if not inenv:
    mypath = os.path.dirname(__file__)
    activatepath = os.path.join(mypath, '../../env/bin/activate')
    if not os.path.exists(activatepath):
        sys.stderr.write("Invalid location for the script {}".format(__file__))
        sys.exit(-10)

from volttron.platform import get_address, get_home, get_volttron_root, \
    is_platform_running
from volttron.platform.packaging import create_package

__version__ = '0.1'

log = logging.getLogger(os.path.basename(__file__))

if __name__ == '__main__':


    parser = argparse.ArgumentParser(version=__version__)

    parser.add_argument("-a", "--vip-address", default=get_address())
    parser.add_argument("-vh", "--volttron-home", default=get_home())
    parser.add_argument("-vr", "--volttron-root", default=get_volttron_root())
    parser.add_argument("-s", "--agent-source", required=True)
    parser.add_argument("-i", "--identity", default=None)
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("-cc", "--config_content", default={})
    parser.add_argument("-wh", "--wheelhouse", default=None)

    opts = parser.parse_args()

    agent_source = opts.agent_source
    if not os.path.isdir(agent_source):
        if os.path.isdir(os.path.join(opts.volttron_root, agent_source)):
            agent_source = os.path.join(opts.volttron_root, agent_source)
        else:
            log.error("Invalid agent source directory specified.")
            sys.exit(-10)
    if not os.path.isfile(os.path.join(agent_source, "setup.py")):
        log.error("Agent source must contain a setup.py file.")
        sys.exit(-10)

    if not is_platform_running(opts.volttron_home):
        log.error("The instance at {} is not running".format(
            opts.volttron_home))
        sys.exit(-10)

    wheelhouse = opts.wheelhouse
    if not wheelhouse:
        wheelhouse = os.path.join(opts.volttron_home, "packaged")

    wheel = create_package(agent_source, wheelhouse, opts.identity)




