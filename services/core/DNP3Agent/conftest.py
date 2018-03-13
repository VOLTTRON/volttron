import sys

from volttrontesting.fixtures.vc_fixtures import *
from volttrontesting.fixtures.volttron_platform_fixtures import *

# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Add system path of the agent's dnp3 subdirectory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/dnp3'))
