'''
Agent Packaging Helper Class for Agent Transport


'''
import os
import wheel

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

    
        

