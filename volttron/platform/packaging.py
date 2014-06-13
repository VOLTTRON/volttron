'''
Agent Packaging Helper Class for Agent Transport


'''
import os
import wheel
import logging

from wheel.install import WheelFile

# TODO Once available will be used instead of
# the current hack 
#from .config import settings as global_settings

class AgentPackageError(Exception): pass

class AgentPackage:
    '''

    '''
    def __init__(self, settings=None):
        '''
        Initializes an AgentPackage instance.  

        Parameters:
            settings - If specified uses the passed settings rather than the
                       settings from the config module.
        '''
        # TODO change to using the following instead when config is ready
        #self._settings = global_settings
        self._settings = settings

        if settings:
            self._settings = settings
        
        # Make sure settings available and agent_dir exists.
        if (self._settings == None or
                getattr(self._settings, 'agent_dir', None) == None or
                not os.path.isdir(getattr(self._settings, 'agent_dir'))):
            raise AgentPackageError('Invalid settings specified')

        
    def create_package(self, agent_dir):
        '''
        Packages the passed agent_dir into a whl file.

        If the agent_dir contains a setup.py file then it is assumed that this 
        is a first time packaging of the agent.  
    
        TODO If the agent_dir doesn't contain a setup.py file then package and
             ready for transport.
        '''
        pass


    def _create_initial_package(self, agent_dir):
        '''
        Creates an initial whl file from the passed agent_dir.  

        If the passed directory doesn't exist or there isn't a setup.py file 
        the directory then AgentPackageError is raised.

        After this function ...
        The initial packaging signs the contents of the immutable data using a
        certificate 

        Parameters:
            agent_dir - The root directory of the specific agent that is to be
                        packaged.
               
        '''
        pass
#        pwd = os.path.abspath(os.curdir)
#        distdir = pkg_resources.resource_filename('wheel.test', dist)
#       os.chdir(distdir)
#        try:
#            sys.argv = ['', 'bdist_wheel']
#            exec(compile(open('setup.py').read(), 'setup.py', 'exec'))
#        finally:
#            os.chdir(pwd)

