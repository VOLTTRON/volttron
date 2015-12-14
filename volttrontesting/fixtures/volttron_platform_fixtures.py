import os
import json
import pytest
from volttrontesting.utils.platformwrapper import PlatformWrapper

@pytest.fixture(scope="module")
def instance1_config():
    return {"vip-address": "tcp://127.0.0.1:22916"}

@pytest.fixture(scope="module")
def instance2_config():
    return {"vip-address": "tcp://127.0.0.2:22916"}

def build_wrapper(platform_config, **kwargs):
    wrapper = PlatformWrapper()
    wrapper.startup_platform(platform_config, **kwargs)
    return wrapper

@pytest.fixture(scope="module")
def volttron_instance1(request, instance1_config):
    wrapper = build_wrapper(instance1_config)

    def fin():
        wrapper.shutdown_platform(True)
        print('teardown instance 1')
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance2(request, instance2_config):
    print('getting instance 2')
    wrapper = build_wrapper(instance2_config)

    def fin():
        wrapper.shutdown_platform(True)
        print('teardown instance 2')
    return wrapper
