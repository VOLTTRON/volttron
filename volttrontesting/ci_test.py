import os
import pytest

def test_ci_env_value():
    print(f"CI is: {os.getenv('CI', None)}")
    print(f"ENV is: {os.environ}")
    assert os.getenv('CI', None) is True
