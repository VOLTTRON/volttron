import matlab.engine
import sys


eng = matlab.engine.start_matlab()

if len(sys.argv) == 2:
    result = eng.testPy(float(sys.argv[1]))
else:
    result = eng.testPy(0.0)

print(result)
