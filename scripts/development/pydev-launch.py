#!/usr/bin/env python2.7
'''
This module supports launching agents from Eclipse PyDev with minimal
configuration. To get it working, follow these simple steps:

  1. Create a new "Run Configuration" named "Launch VOLTTRON
     Agent" and point the "Main Module" to this script (e.g.,
     ${project_loc}/scripts/launch.py).
  2. On the Arguments tab, use ${resource_loc} as the first
     argument in "Program Arguments" and set the "Working
     directory" to Default.

That is all that is required, assuming the default interpreter is
pointing to the virtualenv Python.

This script will automatically set the AGENT_CONFIG, AGENT_SUB_ADDR, and
AGENT_PUB_ADDR environment variables, if they are not already set, as
well as add the module to sys.path, then transfer execution to the
script.  One caveat is that the config file needs to be named config and
must exist in the directory directly below the root package of the
script.
'''

import os.path
import runpy
import sys

# Find the root path, to add to sys.path, and the module name
path, filename = os.path.split(os.path.abspath(sys.argv[1]))
assert filename.endswith('.py')
module = [filename[:-3]]
while path:
    if not os.path.exists(os.path.join(path, '__init__.py')):
        break
    path, package = os.path.split(path)
    module.insert(0, package)
module = '.'.join(module)

# Add environment variables required to execute agents
try:
    home = os.path.expanduser(os.path.expandvars(os.environ['VOLTTRON_HOME']))
except KeyError:
    os.environ['VOLTTRON_HOME'] = home = os.path.expanduser('~/.volttron')

if 'AGENT_CONFIG' not in os.environ:
    config = os.path.join(path, 'config')
    if os.path.exists(config):
        os.environ['AGENT_CONFIG'] = config

ipc = 'ipc://%s%s/run/' % (
    '@' if sys.platform.startswith('linux') else '', home)
if 'AGENT_SUB_ADDR' not in os.environ:
    os.environ['AGENT_SUB_ADDR'] = ipc + 'subscribe'
if 'AGENT_PUB_ADDR' not in os.environ:
    os.environ['AGENT_PUB_ADDR'] = ipc + 'publish'

# Remove this script from sys.argv
del sys.argv[0]
# Append agent root directory to sys.path
sys.path.append(path)
# Transfer execution to the agent module
runpy.run_module(module, run_name='__main__')
