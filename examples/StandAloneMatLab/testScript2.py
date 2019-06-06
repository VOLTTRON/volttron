import sys

if len(sys.argv) >= 2:
    start = 0
    sum1 = 0
    for x in range(len(sys.argv)):
        if start == 0:
            start += 1
        else:
            sum1 += int(sys.argv[x])
    print(sum1)
else:
    print(sys.argv[0])
