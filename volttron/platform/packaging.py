'''
Agent Packaging Helper Class for Agent Transport


'''
import os
import shutil
import sys
import wheel
import logging
import hashlib
import time
import uuid

from wheel.install import WheelFile
from wheel.tool import unpack

# The temporary directory for creating the wheel files.
TMP_AGENT_BUILD_DIR = '/tmp/volttron_wheel_builds'

class AgentPackageError(Exception):
    '''
    A class for errors that are created during packaging/extracting
    and signing agent package wheels.
    '''
    pass

def extract_package(wheel_file, install_dir, include_uuid=False, specific_uuid=None):
    '''
    Extracts a wheel file to the specified location.
    
    If include_uuid is True then a uuid will be generated under the passed
    location directory.  
    
    The agent final directory will be based upon the wheel's data directory 
    name in the following formats:
        
        if include_uuid == True
            install_dir/datadir_name/uuid
        else
            install_dir/datadir_name
    
    Arguments
        wheel_file     - The wheel file to extract.
        install_dir    - The root directory where to extract the wheel
        include_uuid   - Auto-generates a uuuid under install_dir to place
                         the wheel file data
        specific_uuid  - A specific uuid to use for extracting the agent to.
        
    Returns 
        Full path to the extracted wheel file.
    '''
    whl = WheelFile(wheel_file)
    
    # The next lines are  building up the real_dir to be
    #
    #    install_dir/agent_dir/uuid 
    #        or
    #    install_dir/agent_dir
    #
    # depending on the options specified.
    real_dir = os.path.join(install_dir, whl.datadir_name)
        
    # Only include the uuid if the caller wants it.
    if include_uuid:
        if uuid == None:
            real_dir = os.path.join(real_dir, uuid.uuid4())
        else:
            real_dir = os.path.join(real_dir, uuid)
    
    unpack(wheel_file, dest = real_dir)
    
    return real_dir
            
            
        

def create_package(agent_package_dir, storage_dir='/tmp/volttron_wheels'):
    '''
    Creates a packaged whl file from the passed agent_package_dir.  
    
    If the passed directory doesn't exist or there isn't a setup.py file 
    the directory then AgentPackageError is raised.
    
    Parameters
        agent_package_dir - The directory to package in the wheel file.
        signature         - An optional signature file to sign the RECORD file.
    
    Returns    
        string - The full path to the created whl file.
    '''
    if not os.path.isdir(agent_package_dir):
        raise AgentPackageError("Invalid agent package directory specified")
    
    setup_file_path = os.path.join(agent_package_dir, 'setup.py')
    
    if os.path.exists(setup_file_path):
        wheel_path = _create_initial_package(agent_package_dir, storage_dir)
    else:
        raise NotImplementedError("Packaging extracted wheels not available currently")
        wheel_path = None
        
    return wheel_path


def _create_initial_package(agent_dir_to_package, storage_dir):
    '''
    Creates an initial whl file from the passed agent_dir_to_package.  
    
    The function produces a wheel from the setup.py file located in 
    agent_dir_to_package. 

    Parameters:
        agent_dir_to_package - The root directory of the specific agent that is to be
                               packaged.
    
    Returns The path and file name of the packaged whl file.               
    '''
    pwd = os.path.abspath(os.curdir)
    
    unique_str = hashlib.sha224(str(time.gmtime())).hexdigest()
    tmp_dir = os.path.join(TMP_AGENT_BUILD_DIR, os.path.basename(agent_dir_to_package))
    tmp_dir_unique = tmp_dir + unique_str
    tries = 0
    
    while os.path.exists(tmp_dir_unique) and tries < 5:
        tmp_dir_unique = tmp_dir + hashlib.sha224(str(time.gmtime())).hexdigest()
        tries += 1
        time.sleep(1)
        
    shutil.copytree(agent_dir_to_package, tmp_dir_unique)
    
    distdir = tmp_dir_unique
    os.chdir(distdir)
    try:
        sys.argv = ['', 'bdist_wheel']
        exec(compile(open('setup.py').read(), 'setup.py', 'exec'))
        
        wheel_file_and_path = os.path.abspath('./dist')
        wheel_file_and_path = os.path.join(wheel_file_and_path, os.listdir('./dist')[0])        
    finally:
        os.chdir(pwd)            

    return wheel_file_and_path

