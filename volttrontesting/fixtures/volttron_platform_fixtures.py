import pytest

@pytest.fixture(scope="module")
def volttron_instance_1(request):
    print('getting instance 1')
    def fin():
        print('teardown instance 1')
    return {'result': 'volttron platform instance'}


@pytest.fixture(scope="module")
def volttron_instance_2(request):
    print('getting instance 2')
    def fin():
        print ('teardown instance 2')
    return {'result':'volttron platform instance'}
