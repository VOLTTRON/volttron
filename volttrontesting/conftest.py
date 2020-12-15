import sys

from volttrontesting.fixtures.volttron_platform_fixtures import *

# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Skip tests when we don't have these specific modules available
# to test with.  Add others that some agents are required, but
# unavailable.
pytest.importorskip("pydnp3")
pytest.importorskip("pandas")
pytest.importorskip("numpy")
