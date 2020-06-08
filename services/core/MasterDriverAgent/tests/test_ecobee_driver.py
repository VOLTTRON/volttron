import requests
import pytest

from volttron.platform.jsonrpc import RemoteError
from services.core.MasterDriverAgent.master_driver.interfaces import BaseInterface
from services.core.MasterDriverAgent.master_driver.interfaces import ecobee

BaseInterface.__abstractmethods__ = frozenset()

VALID_ECOBEE_CONFIG = {
    "API_KEY": "TEST_KEY",
    "DEVICE_ID": 8675309,
    "GROUP_ID": "test",
    "CACHE_IDENTITY": "platform.drivercache"
}

VALID_ECOBEE_REGISTRY = [
    {
        "Point Name": "hold1",
        "Volttron Point Name": "testHold",
        "Units": "%",
        "Type": "hold",
        "Writable": "True",
        "Readable": "True"
    }, {
        "Point Name": "setting1",
        "Volttron Point Name": "testSetting",
        "Units": "degC",
        "Type": "setting",
        "Writable": "False",
        "Readable": "True"
    }, {
        "Point Name": "testNoRead",
        "Volttron Point Name": "testNoRead",
        "Units": "degC",
        "Type": "setting",
        "Writable": "True",
        "Readable": "False"
    }
]


class MockEcobee(ecobee.Interface):

    def __init__(self):
        super(MockEcobee, self).__init__()
        self.auth_config_stored = False
        self.authorization_code = False
        self.access_token = False
        self.refresh_token = False
        self.refresh_state = False
        self.poll_greenlet = "test"

    def get_auth_config_from_store(self):
        if not self.auth_config_stored:
            return None
        else:
            return {
                "AUTH_CODE": self.authorization_code,
                "ACCESS_TOKEN": self.access_token,
                "REFRESH_TOKEN": self.refresh_token
            }

    def update_auth_config(self):
        return

    def authorize_application(self):
        self.authorization_code = True
        self.authorization_stage = "REQUEST_TOKENS"

    def request_tokens(self):
        if self.authorization_code:
            self.refresh_token = True
            self.access_token = True
            self.authorization_stage = "AUTHORIZED"
        else:
            raise requests.exceptions.HTTPError("Not authorized to request tokens")

    def refresh_tokens(self):
        if self.refresh_token:
            self.refresh_token = True
            self.access_token = True
            self.authorization_stage = "AUTHORIZED"
        else:
            raise requests.exceptions.HTTPError("Not authorized to refresh tokens")

    def get_ecobee_data_from_cache(self, refresh=False):
        if self.access_token is True:
            self.ecobee_data = {
                "thermostatList": [
                    {
                        "identifier": 8675309,
                        "settings": {
                            "setting1": 0,
                            "setting2": 1
                        },
                        "runtime": {
                            "hold1": 0,
                            "hold2": 1
                        },
                        "events": [
                            {"test1": "test1", "type": "program"},
                            {"test2": "test2", "type": "vacation"}
                        ]
                    }, {
                        "identifier": 1,
                        "settings": {
                            "setting1": 3,
                            "setting2": 4
                        },
                        "runtime": {
                            "hold1": 3,
                            "hold2": 4
                        }
                    }, {
                        "events": [
                            {"test3": "test3", "type": "program"},
                            {"test4": "test4", "type": "vacation"}
                        ]
                    }
                ]
            }
        else:
            raise RemoteError("Time to refresh tokens")


@pytest.fixture()
def mock_ecobee():
    return MockEcobee()


def test_configure_ecobee_success(mock_ecobee):
    # TODO test configure from all new auth
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    assert mock_ecobee.authorization_code
    assert mock_ecobee.refresh_token
    assert mock_ecobee.access_token
    # Test configure from existing auth


def test_ecobee_get_point_success(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    hold_data = mock_ecobee.get_point("testHold")
    setting_data = mock_ecobee.get_point("testSetting")
    status_data = mock_ecobee.get_point("Status")
    vacation_data = mock_ecobee.get_point("Vacation")
    program_data = mock_ecobee.get_point("Program")

    assert hold_data
    assert setting_data
    assert status_data
    assert vacation_data
    assert program_data

