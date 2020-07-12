import copy
import datetime
import mock
from mock import MagicMock
import os
import requests
from requests.exceptions import HTTPError
import pytest

from services.core.MasterDriverAgent.master_driver.interfaces import ecobee
from volttron.platform.agent import utils

API_KEY = os.environ.get("ECOBEE_KEY")
DEVICE_ID = os.environ.get("ECOBEE_DEVICE_ID")
PERFORM_INTEGRATION = API_KEY and DEVICE_ID

VALID_ECOBEE_CONFIG = {
    "API_KEY": "TEST_KEY",
    "DEVICE_ID": 8675309,
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

REMOTE_RESPONSE = {
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
            ],
            "equipmentStatus": "testEquip1,testEquip3"
        }
    ]
}


class MockEcobee(ecobee.Interface):

    def __init__(self):
        super(MockEcobee, self).__init__()
        self.auth_config_stored = False
        self.authorization_code = False
        self.access_token = False
        self.refresh_token = False
        self.refresh_state = False
        self.poll_greenlet_thermostats = "test"

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
        self.auth_config_stored = True

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

    def get_data_remote(self, request_type, url, **kwargs):
        if self.authorization_stage != "AUTHORIZED" or not self.access_token:
            self.update_authorization()
        if self.authorization_stage == "AUTHORIZED" and self.access_token:
            return REMOTE_RESPONSE
        else:
            raise HTTPError("Failed to get remote Ecobee data")


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
    auth_config_path = ecobee.AUTH_CONFIG_PATH.format(VALID_ECOBEE_CONFIG.get("DEVICE_ID"))
    assert mock_ecobee.auth_config_path == auth_config_path
    assert mock_ecobee.authorization_stage == "AUTHORIZED"
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    registers = {register.point_name for register in
                 mock_ecobee.get_registers_by_type("byte", False) + mock_ecobee.get_registers_by_type("byte", True)}
    assert {"testNoRead", "testSetting", "testHold", "Programs", "Vacations", "Status"} == registers


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
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    registers = {register.point_name for register in
                 mock_ecobee.get_registers_by_type("byte", False) + mock_ecobee.get_registers_by_type("byte", True)}
    assert {"testSetting", "Programs", "Vacations", "Status"} == registers

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
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    registers = {register.point_name for register in
                 mock_ecobee.get_registers_by_type("byte", False) + mock_ecobee.get_registers_by_type("byte", True)}
    assert {"testSetting", "Programs", "Vacations", "Status"} == registers


def test_get_thermostat_data_success(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    curr_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))

    # Check that we get cached data when possible
    mock_ecobee.get_thermostat_data()
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    refresh_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))
    assert refresh_timestamp == curr_timestamp

    # cause a request_tokens request to occur during get_ecobee_data
    mock_ecobee.authorization_code = True
    mock_ecobee.refresh_token = True
    mock_ecobee.access_token = True
    mock_ecobee.ecobee_data = None
    cleanup_mock_cache(mock_ecobee)
    mock_ecobee.get_thermostat_data()
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    refresh_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))
    assert refresh_timestamp > curr_timestamp

    # should handle having to get a new refresh token and still fetch data
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REFRESH_TOKENS"
    mock_ecobee.ecobee_data = None
    cleanup_mock_cache(mock_ecobee)
    mock_ecobee.get_thermostat_data()
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    assert mock_ecobee.access_token is True
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    refresh_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))
    assert refresh_timestamp > curr_timestamp

    # should handle having to get a new refresh token and still fetch data
    mock_ecobee.refresh_token = False
    mock_ecobee.access_token = False
    mock_ecobee.authorization_stage = "REQUEST_TOKENS"
    mock_ecobee.ecobee_data = None
    cleanup_mock_cache(mock_ecobee)
    mock_ecobee.get_thermostat_data()
    assert mock_ecobee.thermostat_data == REMOTE_RESPONSE
    assert mock_ecobee.access_token is True
    assert mock_ecobee.refresh_token is True

    # now should pull from cache again
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    timestamp = data_cache.get("request_timestamp")
    mock_ecobee.get_thermostat_data()
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    next_timestamp = data_cache.get("request_timestamp")
    assert timestamp == next_timestamp

def test_get_thermostat_data_no_auth(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    mock_ecobee.authorization_code = False
    mock_ecobee.refresh_token = False
    mock_ecobee.access_token = False
    mock_ecobee.ecobee_data = None
    cleanup_mock_cache(mock_ecobee)
    with pytest.raises(HTTPError, match=r""):
        mock_ecobee.get_thermostat_data()
    assert mock_ecobee.ecobee_data is None


def cleanup_mock_cache(mock_ecobee):
    pop_keys = list(mock_ecobee.cache.keys())
    for key in pop_keys:
        mock_ecobee.cache.pop(key)


@pytest.mark.parametrize("point_name,expected_value", [("testSetting", 0),
                                                       ("testHold", 0),
                                                       ("Programs", [{"test1": "test1", "type": "program"}]),
                                                       ("Vacations", [{"test2": "test2", "type": "vacation"}]),
                                                       ("Status", ["testEquip1", "testEquip3"])
                                                       ])
def test_ecobee_get_point_success(mock_ecobee, point_name, expected_value):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    assert mock_ecobee.get_point(point_name) == expected_value
    # Set the Ecobee data to None to try to force to the ValueError check which resets the Ecobee data
    mock_ecobee.thermostat_data = None
    assert mock_ecobee.get_point(point_name) == expected_value


def test_ecobee_empty_values(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    empty_response = copy.deepcopy(REMOTE_RESPONSE)
    empty_response["thermostatList"][0]["equipmentStatus"] = ""
    empty_response["thermostatList"][0]["events"] = []
    mock_ecobee.thermostat_data = empty_response

    assert mock_ecobee.get_point("Status") == []
    assert mock_ecobee.get_point("Vacations") == []
    assert mock_ecobee.get_point("Programs") == []


def test_ecobee_get_point_unreadable(mock_ecobee):
    mixed_readable_registry = [{
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
        "Point Name": "hold2",
        "Volttron Point Name": "testHoldNoRead",
        "Units": "%",
        "Type": "hold",
        "Writable": "True",
        "Readable": "False"
    }, {
        "Point Name": "setting2",
        "Volttron Point Name": "testSettingNoRead",
        "Units": "degC",
        "Type": "setting",
        "Writable": "False",
        "Readable": "False"
    }]
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, mixed_readable_registry)
    assert mock_ecobee.get_point("testHold") == 0
    assert mock_ecobee.get_point("testSetting") == 0
    with pytest.raises(RuntimeError, match=r"Requested read of write-only point testHoldNoRead"):
        mock_ecobee.get_point("testHoldNoRead")
    with pytest.raises(RuntimeError, match=r"Requested read of write-only point testSettingNoRead"):
        mock_ecobee.get_point("testSettingNoRead")


@pytest.mark.parametrize("point_name,expected_value", [("testSetting", 0),
                                                       ("testHold", 0),
                                                       ("Programs", [{"test1": "test1", "type": "program"}]),
                                                       ("Vacations", [{"test2": "test2", "type": "vacation"}]),
                                                       ("Status", ["testEquip1", "testEquip3"])
                                                       ])
def test_get_point_malformed_data(mock_ecobee, point_name, expected_value):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    curr_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))

    # Malformed data should cause ValueErrors, which then trigger the data to be refreshed
    mock_ecobee.thermostat_data = { }
    assert mock_ecobee.get_point(point_name) == expected_value
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    refresh_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))
    assert refresh_timestamp > curr_timestamp
    curr_timestamp = refresh_timestamp
    mock_ecobee.thermostat_data = {
        "thermostatsList": [{
            "identifier": 8675309,
        }]
    }
    assert mock_ecobee.get_point(point_name) == expected_value
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    refresh_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))
    assert refresh_timestamp > curr_timestamp
    curr_timestamp = refresh_timestamp
    mock_ecobee.thermostat_data = {
        "thermostatsList": [{
            "identifier": 8675309,
            "settings": {},
            "runtime": {},
            "events": [""]
        }]
    }
    assert mock_ecobee.get_point(point_name) == expected_value
    data_cache = mock_ecobee.cache.get('https://api.ecobee.com/1/thermostat')
    refresh_timestamp = utils.parse_timestamp_string(data_cache.get("request_timestamp"))
    assert refresh_timestamp > curr_timestamp


# Mock the set state from the Setting class so we don't trigger the HTTP request
@mock.patch.object(ecobee.Setting, 'set_state', MagicMock(name="set_point_callback"))
def test_set_setting_success(mock_ecobee):
    success_registry_config = [{
        "Point Name": "setting1",
        "Volttron Point Name": "testSetting",
        "Units": "degC",
        "Type": "setting",
        "Writable": "True",
        "Readable": "True"
    }]
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, success_registry_config)
    assert mock_ecobee._set_point("testSetting", "test_value") == 0
    assert mock_ecobee.get_register_by_name("testSetting").set_state.call_count == 1
    # call args should be (<set value>, <access token>)
    assert mock_ecobee.get_register_by_name("testSetting").set_state.call_args.args == ("test_value", True)


def test_set_setting_no_write(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    with pytest.raises(IOError, match=r"Trying to write to a point configured read only: testSetting"):
        mock_ecobee._set_point("testSetting", "test_value")


# Mock the set state from the Setting class so we don't trigger the HTTP request
@mock.patch.object(ecobee.Setting, 'set_state', MagicMock(name="set_point_callback"))
def test_set_setting_no_read(mock_ecobee):
    no_read_registry_config = [{
        "Point Name": "setting1",
        "Volttron Point Name": "testSetting",
        "Units": "degC",
        "Type": "setting",
        "Writable": "True",
        "Readable": "False"
    }]
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, no_read_registry_config)
    # None returned if the point is not configured readable
    assert mock_ecobee._set_point("testSetting", "test_value") is None
    assert mock_ecobee.get_register_by_name("testSetting").set_state.call_count == 1
    # call args should be (<set value>, <access token>)
    assert mock_ecobee.get_register_by_name("testSetting").set_state.call_args.args == ("test_value", True)


def test_set_hold_bad_structure(mock_ecobee):
    # holds should be dicts containing at least a "holdType" key which is used by the remote
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    hold_not_dict = "test_value"
    with pytest.raises(ValueError, match=r"Hold register set_state expects dict, received <class 'str'>"):
        assert mock_ecobee._set_point("testHold", hold_not_dict)

    hold_no_type = {
        "test": "test"
    }
    with pytest.raises(ValueError, match=r'Hold register requires "holdType" in value dict'):
        assert mock_ecobee._set_point("testHold", hold_no_type)

    hold_missing_point_name = {
        "holdType": "testHoldType"
    }
    with pytest.raises(ValueError, match=r"Point name testHold not found in Hold set_state value dict"):
        assert mock_ecobee._set_point("testHold", hold_missing_point_name)


def test_set_vacation_bad_structure(mock_ecobee):
    # Vacations should be dictionary containing at least the minimal set of keys below
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    vacation_not_dict = "test_value"
    with pytest.raises(ValueError, match=r"Creating vacation on Ecobee thermostat requires dict:.*"):
        assert mock_ecobee._set_point("Vacations", vacation_not_dict)

    vacation_missing_required = {
        "name": "test_name",
        "heatHoldTemp": -1,
        "startDate": "2020-07-01",
        "startTime": "00:00:00",
        "endDate": "2020-07-01",
        "endTime": "23:59:59"
    }
    with pytest.raises(ValueError, match=r"Creating vacation on Ecobee thermostat requires dict:.*"):
        assert mock_ecobee._set_point("Vacations", vacation_missing_required)


def test_set_status_read_only(mock_ecobee):
    # Status registers are hard-coded and read-only by default
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    with pytest.raises(IOError, match=r"Trying to write to a point configured read only: Status"):
        assert mock_ecobee._set_point("Status", "set status")


def test_scrape_all_success(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    all_scrape = mock_ecobee._scrape_all()
    result = {
        "testSetting": 0,
        "testHold": 0,
        "Status": ["testEquip1", "testEquip3"],
        "Vacations": [{"test2": "test2", "type": "vacation"}],
        "Programs": [{"test1": "test1", "type": "program"}]
    }
    assert result == all_scrape


def test_scrape_all_trigger_refresh(mock_ecobee):
    mock_ecobee.configure(VALID_ECOBEE_CONFIG, VALID_ECOBEE_REGISTRY)
    mock_ecobee.thermostat_data = None
    cleanup_mock_cache(mock_ecobee)
    all_scrape = mock_ecobee._scrape_all()
    result = {
        "testSetting": 0,
        "testHold": 0,
        "Status": ["testEquip1", "testEquip3"],
        "Vacations": [{"test2": "test2", "type": "vacation"}],
        "Programs": [{"test1": "test1", "type": "program"}]
    }
    assert result == all_scrape


# TODO currently building agents times out
# @pytest.mark.skipif(not PERFORM_INTEGRATION, reason="ECOBEE_KEY (Ecobee API key) or DEVICE_ID (Ecobee thermostat serial"
#                                                     " number) not found in environment variables during test. These "
#                                                     "values are required to run integration tests.")
# def test_ecobee_driver(volttron_instance):
#     # 1: Start a fake agent to track callbacks
#     query_agent = volttron_instance.build_agent()
#     query_agent.poll_callback = MagicMock(name="poll_callback")
#     # subscribe to weather poll results
#     query_agent.vip.pubsub.subscribe(
#         peer='pubsub',
#         prefix="devices/campus/building/ecobee",
#         callback=query_agent.poll_callback).get()
#
#     assert volttron_instance.is_agent_running(query_agent.core.agent_uuid)
#
#     volttron_instance.install_agent()
#
#     # create a master driver
#     master_driver = volttron_instance.install_agent(
#         agent_dir=get_services_core("MasterDriverAgent"),
#         start=False,
#         config_file={
#             "publish_breadth_first_all": False,
#             "publish_depth_first": False,
#             "publish_breadth_first": False
#         })
#
#     driver_config = {
#         "driver_config": {
#             "API_KEY": API_KEY,
#             "DEVICE_ID": DEVICE_ID
#         }
#     }
#     ecobee_driver_config = jsonapi.load(get_examples("configurations/drivers/ecobee.config"))
#     ecobee_driver_config["interval"] = 3
#     query_agent.vip.rpc.call(CONFIGURATION_STORE, "manage_store", PLATFORM_DRIVER,
#                              "devices/campus/building/test_ecobee", driver_config)
#
#     with open("configurations/drivers/ecobee.csv") as registry_file:
#         registry_string = registry_file.read()
#     registry_path = re.search("(?!config:\/\/)[a-zA-z]+\.csv", ecobee_driver_config.get("registry_config"))
#
#     query_agent.vip.rpc.call(CONFIGURATION_STORE, "manage_store", PLATFORM_DRIVER, registry_path, registry_string,
#                              config_type="csv")
#
#     ecobee_driver_config.update(driver_config)
#     volttron_instance.start_agent(master_driver)
#
#     # the user must validate the pin in the VOLTTRON log for this run using the Ecobee web UI, see docs for details
#     # this process is allotted 60 seconds, add a couple more to make sure all of the callbacks have had a time to take
#     # effect
#     gevent.sleep(65)
#
#     assert 1 <= query_agent.poll_callback.call_count <= 2
#     print(query_agent.poll_callback.call_args_list)
#
#     # Close agents after test
#     query_agent.core.stop()
#     volttron_instance.stop_agent(master_driver)

# TODO integration tests for set point registers
