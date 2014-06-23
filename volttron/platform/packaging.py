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
import setup

from wheel.install import WheelFile

# The temporary directory for creating the wheel files.
TMP_AGENT_BUILD_DIR = '/tmp/volttron-package-builds'

class AgentPackageError(Exception):
    '''
    A class for errors that are created during packaging/extracting
    and signing agent package wheels.
    '''
    pass


def create_package(agent_package_dir):
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
        wheel_path = _create_initial_package(agent_package_dir)
    else:
        raise NotImplementedError("Packaging extracted wheels not available currently")
        wheel_path = None
        
    return wheel_path


def _create_initial_package(agent_dir_to_package):
    '''
    Creates an initial whl file from the passed agent_dir_to_package.  
    
    

    After this function ...
    The initial packaging signs the contents of the immutable data using a
    certificate 

    Parameters:
        agent_dir_to_package - The root directory of the specific agent that is to be
                               packaged.
        signature_function - The signature_function to use when signing the RECORD
    
    Returns The path and file name of the packaged whl file.               
    '''
    pwd = os.path.abspath(os.curdir)
    
    unique_str = hashlib.sha224(str(time.gmtime())).hexdigest()
    tmp_dir = os.path.join(TMP_AGENT_BUILD_DIR, os.path.basename(agent_dir_to_package))
    tmp_dir += unique_str
    
    shutil.copytree(agent_dir_to_package, tmp_dir)
    
    distdir = tmp_dir
    os.chdir(distdir)
    try:
        sys.argv = ['', 'bdist_wheel']
        exec(compile(open('setup.py').read(), 'setup.py', 'exec'))
        
        wheel_file_and_path = os.path.abspath('./dist')
        wheel_file_and_path = os.path.join(wheel_file_and_path, os.listdir('./dist')[0])        
    finally:
        os.chdir(pwd)            

    return wheel_file_and_path

