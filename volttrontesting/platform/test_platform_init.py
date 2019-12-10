# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
import pytest

from volttron.platform import get_platform_config, update_platform_config, get_config_path
from volttron.utils import get_random_key
from volttrontesting.utils.web_utils import get_test_web_env, get_test_volttron_home
from volttron.platform import jsonapi
import os


def test_update_platform_config():
    my_config = {"bind-web-address": "http://v2:8080",
                 "vip-address": "tcp://127.0.0.1:22196"}
    with get_test_volttron_home() as vhome:
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
    with get_test_volttron_home():
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
