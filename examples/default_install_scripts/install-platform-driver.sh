#!/usr/bin/env bash

echo "storing fake.csv"
vctl config store platform.driver fake.csv examples/configurations/drivers/fake.csv --csv
echo "storing devices/foo/bar"
vctl config store platform.driver devices/foo/bar examples/configurations/drivers/fake.config --json
echo "installing platform driver"
python scripts/install-agent.py --force -s services/core/PlatformDriverAgent --vip-identity platform.driver --start
