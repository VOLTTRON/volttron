Configuration Store Command Line Tools
======================================

Command line management of the Configuration Store is done with the `volttron-ctl config` sub-commands.

Store Configuration
-------------------

To store a configuration in the Configuration Store use the `store` sub-command:

.. code-block:: bash

    volttron-ctl config store <agent vip identity> <configuration name> <infile>

- **agent vip identity** - The agent store to add the configuration to.
- **configuration name** - The name to give the configuration in the store.
- **infile** - The file to ingest into the store.

Optionally you may specify the file type of the file. Defaults to ``--json``.

- ``--json`` - Interpret the file as JSON.
- ``--csv`` - Interpret the file as CSV.
- ``--raw`` - Interpret the file as raw data.

Delete Configuration
--------------------

To delete a configuration in the Configuration Store use the `delete` sub-command:

.. code-block:: bash

    volttron-ctl config delete <agent vip identity> <configuration name>

- **agent vip identity** - The agent store to delete the configuration from.
- **configuration name** - The name of the configuration to delete.

To delete all configurations for an agent in the Configuration Store use ``--all``
switch in place of the configuration name:

.. code-block:: bash

    volttron-ctl config delete <agent vip identity> --all


Get Configuration
-----------------

To get the current contents of a configuration in the Configuration Store use the `get` sub-command:

.. code-block:: bash

    volttron-ctl config get <agent vip identity> <configuration name>

- **agent vip identity** - The agent store to retrieve the configuration from.
- **configuration name** - The name of the configuration to get.

By default this command will return the json representation of what is stored.

- ``--raw`` - Return the raw version of the file.

List Configurations
-------------------

To get the current list of agents with configurations in the Configuration Store use the `list` sub-command:

.. code-block:: bash

    volttron-ctl config list


To get the current list of configurations for an agent include the Agent's VIP IDENTITY:

.. code-block:: bash

    volttron-ctl config list <agent vip identity>

- **agent vip identity** - The agent store to retrieve the configuration from.


Edit Configuration
------------------

To edit a configuration in the Configuration Store use the `edit` sub-command:

.. code-block:: bash

    volttron-ctl config edit <agent vip identity> <configuration name>

- **agent vip identity** - The agent store containing the configuration.
- **configuration name** - The name of the configuration to edit.

The configuration must exist in the store to be edited.

By default `edit` will try to open the file with the `nano` editor.
The `edit` command will respect the `EDITOR` environment variable.
You may override this with the `--editor` option.



