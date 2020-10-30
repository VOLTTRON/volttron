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

from master_driver.interfaces.fakedriver import Interface
from volttron.platform.store import process_raw_config

registry_config_string = """Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
Float,Float,F,-100 to 300,TRUE,50,float,CO2 Reading 0.00-2000.0 ppm
FloatNoDefault,FloatNoDefault,F,-100 to 300,TRUE,,float,CO2 Reading 0.00-2000.0 ppm
"""

registry_config = process_raw_config(registry_config_string, config_type="csv")


@pytest.mark.driver
def test_revert_point():
    interface = Interface()
    interface.configure({}, registry_config)
    value = interface.get_point("Float")
    assert value == 50.0
    
    interface.set_point("Float", 25.0)
    value = interface.get_point("Float")
    assert value == 25.0
    
    interface.revert_point("Float")
    value = interface.get_point("Float")
    assert value == 50.0


@pytest.mark.driver
def test_revert_device():
    interface = Interface()
    interface.configure({}, registry_config)
    value = interface.get_point("Float")
    assert value == 50.0
    
    interface.set_point("Float", 25.0)
    value = interface.get_point("Float")
    assert value == 25.0
    
    interface.revert_all()
    value = interface.get_point("Float")
    assert value == 50.0


@pytest.mark.driver
def test_revert_point_no_default():
    interface = Interface()
    interface.configure({}, registry_config)
    initial_value = interface.get_point("FloatNoDefault")
    
    scrape_values = interface.scrape_all()
    
    assert scrape_values["FloatNoDefault"] == initial_value
    
    test_value = initial_value + 1.0
    
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == initial_value
    
    # Do it twice to make sure it restores state after revert
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == initial_value


@pytest.mark.driver
def test_revert_all_no_default():
    interface = Interface()
    interface.configure({}, registry_config)
    initial_value = interface.get_point("FloatNoDefault")
    
    scrape_values = interface.scrape_all()
    
    assert scrape_values["FloatNoDefault"] == initial_value
    
    test_value = initial_value + 1.0
    
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_all()
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == initial_value
    
    # Do it twice to make sure it restores state after revert
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_all()
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == initial_value


@pytest.mark.driver
def test_revert_no_default_changing_value():
    interface = Interface()
    interface.configure({}, registry_config)
    initial_value = interface.get_point("FloatNoDefault")
    
    # Initialize the revert value.
    interface.scrape_all()
        
    new_value = initial_value + 1.0
    
    # Manually update the register values to give us something different to revert to.
    register = interface.get_register_by_name("FloatNoDefault")
    register.value = new_value
    
    # Update the revert value.
    interface.scrape_all()
    
    test_value = new_value + 1.0
    
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == new_value
    
    assert temp_value != initial_value
    
    # Do it twice to make sure it restores state after revert
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == new_value
