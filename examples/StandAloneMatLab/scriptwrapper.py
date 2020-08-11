#Script to take in a string, run the program, 
#and output the results of the command as a string.

import time
import sys
from io import StringIO


def script_runner(message):
    original = sys.stdout
#    print(message)
#    print(sys.argv)
    sys.argv = message.split(',')
#    print(sys.argv)

    try:
        out = StringIO()
        sys.stdout = out
        exec(open(sys.argv[0]).read())
        sys.stdout = original
        return out.getvalue()
    except Exception as ex:
        out = str(ex)
        sys.stdout = original
        return out




