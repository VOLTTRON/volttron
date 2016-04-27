'''
Copyright (c) 2015, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met: 

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer. 
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies, 
either expressed or implied, of the FreeBSD Project.
'''

'''
This material was prepared as an account of work sponsored by an 
agency of the United States Government.  Neither the United States 
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization 
that has cooperated in the development of these materials, makes 
any warranty, express or implied, or assumes any legal liability 
or responsibility for the accuracy, completeness, or usefulness or 
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or 
service by trade name, trademark, manufacturer, or otherwise does 
not necessarily constitute or imply its endorsement, recommendation, 
r favoring by the United States Government or any agency thereof, 
or Battelle Memorial Institute. The views and opinions of authors 
expressed herein do not necessarily state or reflect those of the 
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''

import sys
import os

from fabric.api import *

import test_settings
import config_builder   

env.hosts = [test_settings.virtual_device_host]
env.user='volttron'

command_lines = None
reg_config_files = None

def build_configs():
    global command_lines, reg_config_files
    command_lines = []
    config_paths = []
    reg_config_files = []
    config_full_path = os.path.abspath(test_settings.config_dir)
    for device_type, settings in test_settings.device_types.items():
        count, reg_config = settings
        
        reg_path = os.path.abspath(reg_config)
        reg_config_files.append(reg_path)
        
        configs, commands = config_builder.build_device_configs(device_type, 
                                                                env.host,
                                                                count,
                                                                reg_path,
                                                                config_full_path,
                                                                60,
                                                                True)
        
        
        config_paths.extend(configs)
        command_lines.extend(commands)
        
    #config_builder.build_master_config(test_settings.master_driver_file, config_dir, config_paths)
    config_builder.build_master_config(test_settings.master_driver_file,
                                       config_full_path,
                                       config_paths,
                                       True,
                                       5,
                                       None)

def get_command_lines():
    global command_lines
    if command_lines is None:
        build_configs()
        
    return command_lines
        
def get_reg_configs():
    global reg_config_files
    if reg_config_files is None:
        build_configs()
        
    return reg_config_files

def get_remote_path(path):
    # command to find the path to the remote volttron.
    path_template = 'python -c "import os; print(os.path.expanduser(\'{}\'))"'
    # Get the remote volttron
    return run(path_template.format(path))

@task
def deploy_virtual_devices():
 
    
    volttron_path = 'python -c "import os; print(os.path.expanduser(\'' \
                                + test_settings.volttron_install + '\'))"'
    
    remote_volttron = get_remote_path(test_settings.volttron_install)
    # Get the remote config location to put the registry configs for the
    # virtual drivers to use.
    remote_device_configs = get_remote_path(test_settings.host_config_location)
    python_exe = os.path.join(remote_volttron, 'env/bin/python')
    
    # The volttron scalabiility-testing directory that is located on the
    # remote host in the remote volttron directory.
    scalability_dir = os.path.join(remote_volttron, 'scripts/scalability-testing')
    # location of the bacnet.py and modbus.py folders and the shutdown.py script
    virtual_driver_dir = os.path.join(scalability_dir, 'virtual-drivers')
    
    
    local_device_configs = os.path.abspath('device-configs')
    
    try:
        # Remove remote directory 
        run('rm -rf {}'.format(remote_device_configs))
    except:
        pass
    
    # Make remote directory for configs.
    run('mkdir -p {}'.format(remote_device_configs))
    
    # move the files to the remote configuration directory. Only
    # move files in the top level and then all directories (though
    # none are currently used).
    put(local_device_configs+'/*', remote_device_configs)
    
    # Assume working from root volttron folder
    for cmd in get_command_lines():
        print(cmd)
        # Translate commands into the remote context for execution of the scripts.
        parts = cmd.split(' ')
        script_name, reg_filename, address = parts[0], parts[1], parts[2]
        port = ''
        if len(parts) > 3:
            port = parts[3]
        reg_filename = os.path.join(remote_device_configs, reg_filename)
        script_name = os.path.join(virtual_driver_dir, script_name)
        run_script = ' '.join([python_exe, 
                                script_name, 
                                reg_filename,
                                address, 
                                port])
        
        # Execute the virtual devices.
        result = run(run_script)
        print('result: {}'.format(result))

@task
def stop_virtual_devices():
    
    volttron = get_remote_path(test_settings.volttron_install)
    python_exe = os.path.join(volttron, 'env/bin/python')
    shutdown_script = os.path.join(volttron, 'scripts/scalability-testing/virtual-drivers/shutdown.py')
    run(python_exe + ' ' + shutdown_script)
        
