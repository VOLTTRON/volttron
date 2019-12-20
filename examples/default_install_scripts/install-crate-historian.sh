#!/usr/bin/env bash

echo "installing crate historian"
python scripts/install-agent.py --force -s services/core/CrateHistorian \
  --config services/core/CrateHistorian/config \
  --vip-identity crate.historian --start
