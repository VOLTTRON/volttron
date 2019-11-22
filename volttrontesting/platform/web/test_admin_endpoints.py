import gevent
from mock import patch
import pytest
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from mock import patch
from volttron.utils.rmq_config_params import RMQConfig
from volttrontesting.utils.platformwrapper import create_volttron_home
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.platform import jsonapi
import contextlib
import os
import shutil


___WEB_USER_FILE_NAME__ = 'web-users.json'

@contextlib.contextmanager
def get_test_volttron_home():
    volttron_home = create_volttron_home()
    original_home = os.environ.get('VOLTTRON_HOME')
    os.environ['VOLTTRON_HOME'] = volttron_home
    yield volttron_home
    if original_home is None:
        os.environ.unsetenv('VOLTTRON_HOME')
    else:
        os.environ['VOLTTRON_HOME'] = original_home
    shutil.rmtree(volttron_home, ignore_errors=True)


def test_add_user():
    with get_test_volttron_home() as vhome:
        webuserpath = os.path.join(vhome, ___WEB_USER_FILE_NAME__)
        assert not os.path.exists(webuserpath)

        username_test = "test"
        username_test_passwd = "passwd"
        adminep = AdminEndpoints()
        adminep.add_user(username_test, username_test_passwd, ['admin'])

        # since add_user is async with persistance we use sleep to allow the write
        # gevent.sleep(0.01)
        assert os.path.exists(webuserpath)

        with open(webuserpath) as fp:
            users = jsonapi.load(fp)

        assert len(users) == 1
        assert users.get(username_test) is not None
        user = users.get(username_test)
        objid = id(user)
        assert ['admin'] == user['groups']
        assert user['hashed_password'] is not None
        original_hashed_passwordd = user['hashed_password']

        # raise ValueError if not overwrite == True
        with pytest.raises(ValueError,
                           match=f"The user {username_test} is already present and overwrite not set to True"):
            adminep.add_user(username_test, username_test_passwd, ['admin'])

        # make sure the overwrite works because we are changing the group
        adminep.add_user(username_test, username_test_passwd, ['read_only', 'jr-devs'], overwrite=True)
        assert os.path.exists(webuserpath)

        with open(webuserpath) as fp:
            users = jsonapi.load(fp)

        assert len(users) == 1
        assert users.get(username_test) is not None
        user = users.get(username_test)
        assert objid != id(user)
        assert ['read_only', 'jr-devs'] == user['groups']
        assert user['hashed_password'] is not None
        assert original_hashed_passwordd != user['hashed_password']


def test_construction():

    # within rabbitmq mgmt this is used
    with patch("volttron.platform.agent.utils.get_platform_instance_name",
               return_value="volttron"):
        mgmt = RabbitMQMgmt()
        assert mgmt is not None

