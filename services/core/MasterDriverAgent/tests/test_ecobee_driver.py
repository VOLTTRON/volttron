import copy
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


def test_request_tokens(mock_ecobee):
    # should set request token and access token to true
    mock_ecobee.authorization_code = True
    mock_ecobee.refresh_token = False
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REQUEST_TOKENS"
    # make sure this fails with the correct failure mode
    mock_ecobee.update_authorization()
    assert mock_ecobee.authorization_code is True
    assert mock_ecobee.refresh_token is True
    assert mock_ecobee.access_token is True


def test_request_tokens_bad_auth_code(mock_ecobee):
    # should only fail if auth code is bad
    mock_ecobee.authorization_code = False
    mock_ecobee.refresh_token = False
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REQUEST_TOKENS"
    # make sure this fails with the correct failure mode
    with pytest.raises(requests.exceptions.HTTPError, match=r'Not authorized to request tokens'):
        mock_ecobee.update_authorization()
    assert mock_ecobee.authorization_code is False
    assert mock_ecobee.refresh_token is False
    assert mock_ecobee.access_token is False


def test_refresh_tokens(mock_ecobee):
    # should set request token and access token to true
    mock_ecobee.authorization_code = True
    mock_ecobee.refresh_token = True
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REFRESH_TOKENS"
    # make sure the code token is set properly
    mock_ecobee.update_authorization()
    assert mock_ecobee.authorization_code is True
    assert mock_ecobee.refresh_token is True
    assert mock_ecobee.access_token is True


def test_refresh_tokens_bad_auth_code(mock_ecobee):
    # should still be able to refresh if the existing refresh token is valid even if the auth code is not
    mock_ecobee.authorization_code = False
    mock_ecobee.refresh_token = True
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REFRESH_TOKENS"
    # should still work as the only token that's needed for refresh is the refresh token
    mock_ecobee.update_authorization()
    assert mock_ecobee.authorization_code is False
    assert mock_ecobee.refresh_token is True
    assert mock_ecobee.access_token is True


def test_refresh_tokens_bad_refresh_token(mock_ecobee):
    mock_ecobee.authorization_code = True
    mock_ecobee.refresh_token = False
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REFRESH_TOKENS"
    # make sure this fails with the correct failure mode
    with pytest.raises(requests.exceptions.HTTPError, match=r'Not authorized to refresh tokens'):
        mock_ecobee.update_authorization()
    assert mock_ecobee.authorization_code is True
    assert mock_ecobee.refresh_token is False
    assert mock_ecobee.access_token is False


def test_configure_ecobee_success(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    assert mock_ecobee.authorization_code
    assert mock_ecobee.refresh_token
    assert mock_ecobee.access_token
    # Test configure from existing auth
    assert mock_ecobee.group_id == "test"
    auth_config_path = ecobee.AUTH_CONFIG_PATH.format("test")
    assert mock_ecobee.auth_config_path == auth_config_path
    # TODO compare list of registers
    assert mock_ecobee.authorization_stage == "AUTHORIZED"
    settings = {register.point_name for register in
                mock_ecobee.get_registers_by_type("setting", True) + mock_ecobee.get_registers_by_type("setting", False)}
    holds = {register.point_name for register in
             mock_ecobee.get_registers_by_type("hold", True) + mock_ecobee.get_registers_by_type("hold", False)}
    program = mock_ecobee.get_register_by_name("Programs").point_name
    vacation = mock_ecobee.get_register_by_name("Vacations").point_name
    status = mock_ecobee.get_register_by_name("Status").point_name
    assert {"testNoRead", "testSetting"} == settings
    assert {"testHold"} == holds
    assert program == "Programs"
    assert vacation == "Vacations"
    assert status == "Status"


def test_configure_ecobee_invalid_id(mock_ecobee):
    invalid_ecobee_config = copy.deepcopy(VALID_ECOBEE_CONFIG)
    invalid_ecobee_config["DEVICE_ID"] = "woops"
    with pytest.raises(ValueError, match=r"Ecobee driver requires Ecobee device identifier as int, got: .*"):
        mock_ecobee.configure(invalid_ecobee_config, VALID_ECOBEE_REGISTRY)


def test_configure_ecobee_invalid_registers(mock_ecobee):
    # Not having a "point_name" entry should cause no point to be added, but no error to be thrown
    # all other registers should still be built
    no_point_name = [{
        "Volttron Point Name": "testHold",
        "Units": "%",
        "Type": "hold",
        "Writable": "True",
        "Readable": "True"
    }, VALID_ECOBEE_REGISTRY[1]]
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, no_point_name)
    settings = {register.point_name for register in
                mock_ecobee.get_registers_by_type("setting", True) + mock_ecobee.get_registers_by_type("setting",
                                                                                                       False)}
    holds = {register.point_name for register in
             mock_ecobee.get_registers_by_type("hold", True) + mock_ecobee.get_registers_by_type("hold", False)}
    program = mock_ecobee.get_register_by_name("Programs").point_name
    vacation = mock_ecobee.get_register_by_name("Vacations").point_name
    status = mock_ecobee.get_register_by_name("Status").point_name
    assert {"testSetting"} == settings
    assert not holds
    assert program == "Programs"
    assert vacation == "Vacations"
    assert status == "Status"

    # An unsupported type should cause no point to be added, but no error to be thrown
    # all other registers should still be built
    no_point_name = [{
        "Volttron Point Name": "testHold",
        "Units": "%",
        "Type": "test",
        "Writable": "True",
        "Readable": "True"
    }, VALID_ECOBEE_REGISTRY[1]]
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, no_point_name)
    settings = {register.point_name for register in
                mock_ecobee.get_registers_by_type("setting", True) + mock_ecobee.get_registers_by_type("setting",
                                                                                                       False)}
    holds = {register.point_name for register in
             mock_ecobee.get_registers_by_type("hold", True) + mock_ecobee.get_registers_by_type("hold", False)}
    program = mock_ecobee.get_register_by_name("Programs").point_name
    vacation = mock_ecobee.get_register_by_name("Vacations").point_name
    status = mock_ecobee.get_register_by_name("Status").point_name
    assert {"testSetting"} == settings
    assert not holds
    assert program == "Programs"
    assert vacation == "Vacations"
    assert status == "Status"


@pytest.mark.parametrize("point_name,expected_value", [("testSetting", 0),
                                                       ("testHold", 0),
                                                       ("Programs", [{"test1": "test1", "type": "program"}]),
                                                       ("Vacations", [{"test2": "test2", "type": "vacation"}])
                                                       ]
                         )
def test_ecobee_get_point_success(mock_ecobee, point_name, expected_value):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    assert mock_ecobee.get_point(point_name) == expected_value




# def test_get_ecobee_data_success(mock_ecobee):
#     # cause a request_tokens request to occur during get_ecobee_data
#     mock_ecobee.authorization_code = True
#     mock_ecobee.refresh_token = True
#     mock_ecobee.access_token = Truet
#     mock_ecobee.authorization_stage = "REFRESH_TOKENS"
#     mock_ecobee.ecobee_data = None
#     # should handle having to get a new refresh token and still fetch data
#     mock_ecobee.get_ecobee_data()
#     assert mock_ecobee.refresh_token is True
#     assert mock_ecobee.access_token is True
#     assert isinstance(mock_ecobee, dict)
#
#
# def test_ecobee_get_point_success(mock_ecobee):
#     mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
#     hold_data = mock_ecobee.get_point("testHold")
#     setting_data = mock_ecobee.get_point("testSetting")
#     status_data = mock_ecobee.get_point("Status")
#     vacation_data = mock_ecobee.get_point("Vacation")
#     program_data = mock_ecobee.get_point("Program")
#
#     assert hold_data
#     assert setting_data
#     assert status_data
#     assert vacation_data
#     assert program_data

