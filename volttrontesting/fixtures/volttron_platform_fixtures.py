import os
import pytest
from volttrontesting.utils.platformwrapper import PlatformWrapper

@pytest.fixture(scope="module")
def volttron_instance_1(request):
    print('getting instance 1')
    vh = '/tmp/instance1home'
    if os.path.exists(vh):
        os.removedirs(vh)
    os.makedirs(vh)
    wrapper = PlatformWrapper("/tmp/instance1home")
    def fin():
        wrapper.shutdown_platform(cleanup=True)
        print('teardown instance 1')
    return wrapper


@pytest.fixture(scope="module")
def volttron_instance_2(request):
    print('getting instance 2')
    vh = '/tmp/instance2home'
    if os.path.exists(vh):
        os.removedirs(vh)
    os.makedirs(vh)
    wrapper = PlatformWrapper("/tmp/instance2home")
    def fin():
        wrapper.shutdown_platform(cleanup=True)
        print ('teardown instance 2')
    return wrapper
