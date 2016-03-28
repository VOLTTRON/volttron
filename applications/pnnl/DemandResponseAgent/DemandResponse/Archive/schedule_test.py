# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

import math
import logging

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

def schedule_builder(current_time, start_time, end_time,
                     current_spacetemp=77.0,
                     pre_csp=67.0,
                     building_thermal_constant=4.0,
                     normal_coolingstpt=76.0,
                     timestep_length=15*60,
                     dr_csp=80.0):
    """get and format DR signal and schedule DR proc."""
    
    if current_time > end_time:
        _log.debug('Too Late!')
        return
    
    ideal_cooling_window = int(((current_spacetemp - pre_csp)/building_thermal_constant) *3600)  
    ideal_precool_start_time = start_time - ideal_cooling_window
    
    max_cooling_window = start_time - current_time
    
    cooling_window = ideal_cooling_window if ideal_cooling_window < max_cooling_window else max_cooling_window
    
    precool_start_time = start_time - cooling_window
    
    

    if (max_cooling_window > 0):
        _log.debug("Normal pre-cool")
        num_cooling_timesteps = int(math.ceil(float(cooling_window) / float(timestep_length)))         
        cooling_step_delta = (normal_coolingstpt - pre_csp) / num_cooling_timesteps
        
        for step_index in range (1, num_cooling_timesteps+1):
            event_time = start_time - (step_index * timestep_length)
            csp = pre_csp + ((step_index-1)*cooling_step_delta)
            
            _log.debug('Precool step: {} {}'.format(event_time, csp))
    
    else:
        _log.debug("Too late to pre-cool!")
    
    restore_window = int(((dr_csp - normal_coolingstpt)/building_thermal_constant) *3600)  
    restore_start_time = end_time
    num_restore_timesteps = int(math.ceil(float(restore_window) / float(timestep_length)))         
    restore_step_delta = (dr_csp - normal_coolingstpt) / num_restore_timesteps
        
    _log.debug('DR Event: {} {}'.format(start_time, dr_csp))
    _log.debug('DR End Event: {} {}'.format(end_time, dr_csp-restore_step_delta))
        
    for step_index in range (1, num_restore_timesteps):
        event_time = end_time + (step_index * timestep_length)
        csp = dr_csp - ((step_index+1)*restore_step_delta)
        
        _log.debug('Restore step: {} {}'.format(event_time, csp))
    
    event_time = end_time + (num_restore_timesteps * timestep_length)
    _log.debug('Cleanup Event: {} {}'.format(event_time, normal_coolingstpt))

def test_scheduler():
    _log.debug('Normal scheduling')
    schedule_builder(0, 5*3600, 11*3600,
                         current_spacetemp=77.0,
                         pre_csp=67.0,
                         building_thermal_constant=4.0,
                         normal_coolingstpt=76.0,
                         timestep_length=15*60,
                         dr_csp=80.0)

    _log.debug('In precool start normal scheduling')
    schedule_builder(0, 4*3600, 10*3600,
                         current_spacetemp=77.0,
                         pre_csp=67.0,
                         building_thermal_constant=4.0,
                         normal_coolingstpt=76.0,
                         timestep_length=15*60,
                         dr_csp=80.0)

    _log.debug('In precool short scheduling')
    schedule_builder(0, 3600, 7*3600,
                         current_spacetemp=77.0,
                         pre_csp=67.0,
                         building_thermal_constant=4.0,
                         normal_coolingstpt=76.0,
                         timestep_length=15*60,
                         dr_csp=80.0)

    _log.debug('In precool short offset scheduling')
    schedule_builder(0, 3600-200, (7*3600)-200,
                         current_spacetemp=77.0,
                         pre_csp=67.0,
                         building_thermal_constant=4.0,
                         normal_coolingstpt=76.0,
                         timestep_length=15*60,
                         dr_csp=80.0)

    _log.debug('In precool short offset scheduling')
    schedule_builder(100, 0, 6*3600,
                         current_spacetemp=77.0,
                         pre_csp=67.0,
                         building_thermal_constant=4.0,
                         normal_coolingstpt=76.0,
                         timestep_length=15*60,
                         dr_csp=80.0)

    _log.debug('In precool short offset scheduling')
    schedule_builder(3601, 0, 3600,
                         current_spacetemp=77.0,
                         pre_csp=67.0,
                         building_thermal_constant=4.0,
                         normal_coolingstpt=76.0,
                         timestep_length=15*60,
                         dr_csp=80.0)
    
