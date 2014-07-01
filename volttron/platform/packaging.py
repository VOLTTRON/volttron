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
        The folder where the wheel was extracted to.
    '''
    real_dir = install_dir
        
    # Only include the uuid if the caller wants it.
    if include_uuid:
        if uuid == None:
            real_dir = os.path.join(real_dir, uuid.uuid4())
        else:
            real_dir = os.path.join(real_dir, uuid)
    
    if not os.path.isdir(real_dir):
        os.makedirs(real_dir)
        
    wf = WheelFile(wheel_file)
    namever = wf.parsed_filename.group('namever')
    destination = os.path.join(real_dir, namever)
    sys.stderr.write("Unpacking to: %s\n" % (destination))
    wf.zipfile.extractall(destination)
    wf.zipfile.close()
    return destination
            
            
        
def repackage(agent_name):
    raise AgentPackageError('Repackage is not available')

def create_package(agent_package_dir, wheelhouse='/tmp/volttron_wheels'):
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
        wheel_path = _create_initial_package(agent_package_dir, wheelhouse)
    else:
        raise NotImplementedError("Packaging extracted wheels not available currently")
        wheel_path = None
        
    return wheel_path


def _create_initial_package(agent_dir_to_package, wheelhouse):
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
    tmp_build_dir = '/tmp/whl_bld'
    
    unique_str = str(uuid.uuid4())
    tmp_dir = os.path.join(tmp_build_dir, os.path.basename(agent_dir_to_package))
    tmp_dir_unique = tmp_dir + unique_str
    tries = 0
    
    while os.path.exists(tmp_dir_unique) and tries < 5:
        tmp_dir_unique = tmp_dir + hashlib.sha224(str(time.gmtime())).hexdigest()
        tries += 1
        time.sleep(1)
        
    shutil.copytree(agent_dir_to_package, tmp_dir_unique)
    
    distdir = tmp_dir_unique
    os.chdir(distdir)
    wheel_name = None
    try:
        print(distdir)
        sys.argv = ['', 'bdist_wheel']
        exec(compile(open('setup.py').read(), 'setup.py', 'exec'))
        
        wheel_name = os.listdir('./dist')[0]
        
        wheel_file_and_path = os.path.join(os.path.abspath('./dist'), wheel_name)
    finally:
        os.chdir(pwd)     
    
    if not os.path.exists(wheelhouse):
        os.makedirs(wheelhouse)
        
    final_dest = os.path.join(wheelhouse, wheel_name)
#     print("moving {} to {}".format(wheel_file_and_path, final_dest))
#     print("removing {}".format(tmp_dir_unique))
    shutil.move(wheel_file_and_path, final_dest)       
    shutil.rmtree(tmp_dir_unique, False)

    return final_dest

