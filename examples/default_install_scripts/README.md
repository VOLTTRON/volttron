#Example Installation Scripts

The scripts contained within this folder are examples that can be modified to fit
the users specific intent.  Most of the scripts will follow the following structure:

```shell script
#!/usr/bin/env bash

echo "installing crate historian"
python scripts/install-agent.py --force -s services/core/CrateHistorian \
  --config services/core/CrateHistorian/config \
  --vip-identity crate.historian --start

```

## NOTES

- Scripts are intended to be run from the base volttron directory.

- Using these scripts provides a repeatable pattern for upgrading your agents within the
volttron environment.

- There are default configs in most agents' directories and these scripts can use those.