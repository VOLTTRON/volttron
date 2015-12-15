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

def build_wrapper(vip_address, **kwargs):
    wrapper = PlatformWrapper()
    print('BUILD_WRAPPER: {}'.format(vip_address))
    wrapper.startup_platform(vip_address=vip_address, **kwargs)
    return wrapper

@pytest.fixture(scope="module")
def volttron_instance1(request, instance1_config):
    print("building instance 1")
    wrapper = build_wrapper("tcp://127.0.0.1:22916")

    def cleanup():
        wrapper.shutdown_platform(True)
        print('teardown instance 1')
    request.addfinalizer(cleanup)
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance2(request, instance2_config):
    print("building instance 2")
    wrapper = build_wrapper("tcp://127.0.0.2:22916")

    def cleanup():
        wrapper.shutdown_platform(True)
        print('teardown instance 2')
    request.addfinalizer(cleanup)
    return wrapper
