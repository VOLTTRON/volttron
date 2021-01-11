import sys
import psutil

from volttron.platform import jsonapi
from volttrontesting.fixtures.volttron_platform_fixtures import *

# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

test_to_instance = {}


def pytest_runtest_logstart(nodeid, location):
    before = 0
    print(f"test node: {nodeid} location: {location}")
    for proc in psutil.process_iter():
        if 'volttron' in proc.name().lower():
            before += 1
    test_to_instance[nodeid] = dict(before=before, name=nodeid)


def pytest_runtest_logfinish(nodeid, location):
    # After each test the nodid is the name of the test
    after = 0
    print(f"test node: {nodeid} location: {location}")
    for proc in psutil.process_iter():
        if 'volttron' in proc.name().lower():
            after += 1
    test_to_instance[nodeid]["after"] = after

    if test_to_instance[nodeid]["before"] == test_to_instance[nodeid]["after"]:
        del test_to_instance[nodeid]
    else:
        with open("volttron_test_output_count.txt", 'w') as fp:
            fp.write(jsonapi.dumps(test_to_instance, indent=2))
    # print(f"finished test nodeid: {nodeid} location: {location}")
