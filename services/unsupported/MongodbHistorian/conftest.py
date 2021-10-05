import sys

from volttrontesting.fixtures.volttron_platform_fixtures import *

# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# This path update and import shouldn't be needed here but without the below line pytest collection fails with error
# cannot import  ALL_TOPIC at line 28 of test_mongohistorian.py
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "tests"))
