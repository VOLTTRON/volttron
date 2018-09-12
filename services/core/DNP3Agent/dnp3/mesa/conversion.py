import sys, yaml, json

y=yaml.load(sys.stdin.read())
print json.dumps(y)