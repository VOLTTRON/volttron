#!python

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
'''
    A simple shutdown script for shutting down all bacnet and modbus
    virtual drivers.
'''
import psutil
import os
import signal

def stop_all():
    '''Stop both modbus and bacnet devices.'''

    stop_modbus()
    stop_bacnet()

def stop_modbus():
    '''Stop all virtual modbus devices'''

    for pid in psutil.pids():
        proc = psutil.Process(pid)

        for opt in proc.cmdline():
            if 'modbus' in opt:
                print('Killing:', opt)
                os.kill(pid, signal.SIGTERM)
                break

def stop_bacnet():
    '''Stop all virtual bacnet devices'''

    for pid in psutil.pids():
        proc = psutil.Process(pid)

        for opt in proc.cmdline():
            if 'bacnet' in opt:
                print('Killing:', opt)
                os.kill(pid, signal.SIGTERM)
                break

if __name__ == '__main__':
    stop_all()
