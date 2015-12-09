import os
import json
import pytest
from volttrontesting.utils.platformwrapper import PlatformWrapper

@pytest.fixture(scope="module")
def instance_1_config():
    return {"vip-address": "tcp://127.0.0.1:22916"}

@pytest.fixture(scope="module")
def instance_2_config():
    return {"vip-address": "tcp://127.0.0.2:22916"}

def build_wrapper(platform_config, **kwargs):
    wrapper = PlatformWrapper()
    wrapper.startup_platform(platform_config, **kwargs)
    return wrapper

@pytest.fixture(scope="module")
def volttron_instance_1(request, instance_1_config):
    wrapper = build_wrapper(instance_1_config)

    def fin():
        wrapper.shutdown_platform(True)
        print('teardown instance 1')
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance_2(request, instance_2_config):
    print('getting instance 2')
    wrapper = build_wrapper(instance_2_config)

    def fin():
        wrapper.shutdown_platform(True)
        print('teardown instance 2')
    return wrapper
