import os
import pytest
import sys

test_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(test_dir+'/..')

from volttroncentral.registry import PlatformRegistry

@pytest.mark.vc
def test_registry_creation():
    reg = PlatformRegistry()


