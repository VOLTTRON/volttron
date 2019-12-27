#!/usr/bin/env bash

echo "installing sqlite historian"
python scripts/install-agent.py --force -s services/core/SQLHistorian \
  --config services/core/SQLHistorian/config.sqlite \
  --vip-identity sqlite.historian --start
