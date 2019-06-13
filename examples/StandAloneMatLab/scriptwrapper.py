#Script to take in a string, run the program, 
#and output the results of the command as a string.

import time
import sys
from StringIO import StringIO


def script_runner(message):
    original = sys.stdout
#    print(message)
#    print(sys.argv)
    sys.argv = message.split(',')
#    print(sys.argv)

    try:
        out = StringIO()
        sys.stdout = out
        execfile(sys.argv[0])
        sys.stdout = original
        return out.getvalue()
    except Exception as ex:
        out = str(ex)
        sys.stdout = original
        return out




