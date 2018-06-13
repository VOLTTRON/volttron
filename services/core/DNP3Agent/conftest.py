import sys

from volttrontesting.fixtures.vc_fixtures import *
from volttrontesting.fixtures.volttron_platform_fixtures import *

collect_ignore = ["function_test.py", "tests/mesa_master_test.py"]

try:
    import pydnp3
except ImportError:
    # pydnp3 library has not been installed -- all pytest modules would fail
    collect_ignore.extend(["tests/test_dnp3_agent.py",
                           "tests/test_mesa_agent.py",
                           "tests/test_mesa_data.py"])

# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Add system path of the agent's dnp3 subdirectory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/dnp3'))
