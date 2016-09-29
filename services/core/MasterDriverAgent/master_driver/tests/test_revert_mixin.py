# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

from master_driver.interfaces.fakedriver import Interface
import pytest
from volttron.platform.store import process_raw_config

registry_config_string = """Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
Float,Float,F,-100 to 300,TRUE,50,float,CO2 Reading 0.00-2000.0 ppm
FloatNoDefault,FloatNoDefault,F,-100 to 300,TRUE,,float,CO2 Reading 0.00-2000.0 ppm
"""

registry_config = process_raw_config(registry_config_string, config_type="csv")

@pytest.mark.revert
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
    
@pytest.mark.revert
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
    
@pytest.mark.revert
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
    
    #Do it twice to make sure it restores state after revert
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == initial_value
    
@pytest.mark.revert
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
    
    #Do it twice to make sure it restores state after revert
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_all()
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == initial_value
    
@pytest.mark.revert
def test_revert_no_default_changing_value():
    interface = Interface()
    interface.configure({}, registry_config)
    initial_value = interface.get_point("FloatNoDefault")
    
    #Initialize the revert value.
    interface.scrape_all()
        
    new_value = initial_value + 1.0
    
    #Manually update the register values to give us something different to revert to.
    register = interface.get_register_by_name("FloatNoDefault")
    register.value = new_value
    
    #Update the revert value.
    interface.scrape_all()
    
    test_value = new_value + 1.0
    
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == new_value
    
    assert temp_value != initial_value
    
    #Do it twice to make sure it restores state after revert
    interface.set_point("FloatNoDefault", test_value)
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == test_value
    
    interface.revert_point("FloatNoDefault")
    temp_value = interface.get_point("FloatNoDefault")
    assert temp_value == new_value
