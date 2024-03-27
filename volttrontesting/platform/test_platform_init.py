# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
import pytest

from volttron.platform import get_platform_config, update_platform_config, get_config_path
from volttron.utils import get_random_key
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home


def test_update_platform_config():
    my_config = {"bind-web-address": "http://v2:8080",
                 "vip-address": "tcp://127.0.0.1:22196"}
    with get_test_volttron_home(messagebus='zmq') as vhome:
        # Empty platform config currently (note this wouldn't be if the platform actually has started)
        config = get_platform_config()

        assert 0 == len(config)

        # Test the config is updated
        update_platform_config(my_config)

        # Tests that we get back the correct data.
        config = get_platform_config()

        for k, v in my_config.items():
            assert v == config.get(k)

        assert 0 == len(set(my_config) - set(config))

        # Make sure that it persisted in the correct file.
        from configparser import ConfigParser
        cfg = ConfigParser()
        cfg.read(get_config_path())
        assert cfg.has_section("volttron")
        for k, v in my_config.items():
            assert v == cfg.get("volttron", k)


def test_get_random_key():
    with get_test_volttron_home(messagebus='zmq'):
        key = get_random_key()
        # According to docs the default length is 65
        #
        # Note 2x default is what we should get due to hex encoding.
        assert 130 == len(key)

        with pytest.raises(ValueError) as err:
            key = get_random_key(0)

        with pytest.raises(ValueError) as err:
            key = get_random_key(-1)

        key = get_random_key(20)
        # note 2x the passed random key
        assert 40 == len(key)
