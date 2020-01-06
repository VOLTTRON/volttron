#!/usr/bin/env bash

echo "installing mysql historian"
python scripts/install-agent.py --force -s services/core/SQLHistorian \
  --config services/core/SQLHistorian/config.mysql \
  --vip-identity mysql.historian --start
