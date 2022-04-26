"""
Test cases to test agent configuration
"""
import pytest
from volttron.platform.agent.utils import load_config

def test_load_config_with_valid_config():
    """
    Test that load_config correctly loads a valid config file and path
    """
    config_path = "./test_config"
    expected_json = {
        "testKey": "testValue"
    }

    assert load_config(config_path) == expected_json


def test_load_config_with_nonexistent_path():
    """
    Test that the load_config function will raise an 
    error if given a nonexistent path to the config file
    """
    fake_path = "/hello/world"

    with pytest.raises(ValueError) as e:
        load_config(fake_path)
    assert f"Config file specified by AGENT_CONFIG path {fake_path} does not exist." in str(e.value)


def test_load_config_with_none_path():
    """
    Test that load_config returns an empty json if given 
    None for the config path
    """
    assert load_config(None) == {}
