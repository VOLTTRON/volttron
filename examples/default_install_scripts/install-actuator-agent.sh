#!/usr/bin/env bash

echo "installing actuator agent"
python scripts/install-agent.py --force -s services/core/ActuatorAgent \
  --config services/core/ActuatorAgent/actuator-deploy.service \
  --vip-identity platform.actuator --start
