import sys

from volttrontesting.fixtures.volttron_platform_fixtures import *

# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def pytest_runtest_logfinish(nodeid, location):
    # After each test the nodid is the name of the test
    pass
    # print(f"finished test nodeid: {nodeid} location: {location}")
