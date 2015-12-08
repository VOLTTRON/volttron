import os
import json
import pytest
from volttrontesting.utils.platformwrapper import PlatformWrapper

@pytest.fixture(scope="module")
def instancce_1_config():
    return {"vip-address": "tcp://127.0.0.1:22916"}

@pytest.fixture(scope="module")
def instancce_2_config():
    return {"vip-address": "tcp://127.0.0.2:22916"}

@pytest.fixture(scope="module")
def volttron_instance_1(request, instancce_1_config):
    print('getting instance 1')
    vh = '/tmp/instance1home'
    if not os.path.exists(vh):
        os.makedirs(vh)

    config_dir = os.path.join(vh, 'config')
    with open(os.path.join(vh, 'config'), 'w') as fout:
        fout.write(json.dumps(instancce_1_config))
        fout.close()

    wrapper = PlatformWrapper("/tmp/instance1home")
    print("CONFIG DIR: ", config_dir)
    print("EXISTS?: ", os.path.exists(config_dir))
    wrapper.startup_platform(config_dir)
    def fin():
        wrapper.shutdown_platform(cleanup_temp=True)
        print('teardown instance 1')
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance_2(request, instancce_2_config):
    print('getting instance 2')
    vh = '/tmp/instance2home'
    if not os.path.exists(vh):
        os.makedirs(vh)

    config_dir = os.path.join(vh, 'config')
    with open(config_dir, 'w') as fout:
        fout.write(json.dumps(instancce_2_config))
        fout.close()
        
    wrapper = PlatformWrapper("/tmp/instance2home")
    wrapper.startup_platform(config_dir)
    def fin():
        wrapper.shutdown_platform(cleanup_temp=True)
        print ('teardown instance 2')
    return wrapper
