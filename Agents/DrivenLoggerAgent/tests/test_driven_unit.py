import os
import sys

import volttron
AGENT_PATH = os.path.join(os.path.dirname(os.path.dirname(volttron.__file__)),
                          'Agents','DrivenLoggerAgent', 'drivenlogger')

AGENT_PATH = sys.path.append(AGENT_PATH)

import drivenlogger


#print(sys.path)
#from drivenlogger.drivenagent import DrivenAgent

#print(DrivenAgent)

