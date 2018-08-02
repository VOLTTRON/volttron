import sys

from volttrontesting.fixtures.vc_fixtures import *
from volttrontesting.fixtures.volttron_platform_fixtures import *
from volttrontesting.fixtures.rmq_fixtures import *

collect_ignore = []

try:
    import pytest_rabbitmq
    from volttrontesting.fixtures.rmq_fixtures import *
except ImportError:
    pass


# Add system path of the agent's directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))