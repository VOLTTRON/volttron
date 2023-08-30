import sys, yaml, json

y=yaml.safe_load(sys.stdin.read())
print(json.dumps(y))
