import argparse
import logging
import os
import subprocess
import sys


logging.basicConfig(level=logging.WARN)
log = logging.getLogger(os.path.basename(__file__))

if not hasattr(sys, 'real_prefix'):
    inenv = False
else:
    inenv = True

if not inenv:
    mypath = os.path.dirname(__file__)
    correct_python = sys.executable
    if not os.path.exists(correct_python):
        log.error("Invalid location for the script {}".format(correct_python))
        sys.exit(-10)

    # Call this script in a subprocess with the correct python interpreter.
    cmds = [correct_python, __file__]
    cmds.extend(sys.argv[1:])
    process = subprocess.Popen(cmds, env=os.environ)
    process.wait()
    sys.exit(process.returncode)

from volttron.platform import get_home, is_instance_running

__version__ = '0.2'


if __name__ == '__main__':

    parser = argparse.ArgumentParser(version=__version__)
    parser.add_argument("-vh", "--volttron-home", default=get_home())

    args = parser.parse_args()
    result = is_instance_running(args.volttron_home)
    if result:
        result = 1
    else:
        result = 0
    sys.stdout.write("{}\n".format(int(result)))
