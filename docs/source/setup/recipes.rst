.. _recipes:

VOLTTRON Deployment Recipes
===========================

Begining with version 7.1, VOLTTRON introduces the concept of recipes. This system leverages
`ansible <https://docs.ansible.com/ansible/latest/index.html>`_ to orchestrate the deployment and
configuration process for both the VOLTTRON platform, and installed agents, on remote systems.

The following sections describe the recipes which are currently available individually.

Getting started with recipes
----------------------------

The recipes system is designed to be executed from a user workstation or other server with ssh
access to the hosts which will be running the VOLTTRON platforms being configured. In order to do
so, you require a python environment with both ansible and the core VOLTTRON components installed.
To achieve that, use the :ref:`Bootstrap-Options` and include the ``--deployment`` option. This will
install both the ``vctl`` command-line tool, as well as the ansible package with its command-line
tools.

Recipes used purely as playbooks
--------------------------------

There are a number of recipes which are provided only as ansible playbooks, intended to be run
using the ansible CLI tools along with an inventory which you write. These facilitate common
administrative tasks. All recipes which require administrative access on the remote system are
of this type.

Ensure host key entries
~~~~~~~~~~~~~~~~~~~~~~~

The ``ensure-host-keys.yml`` playbook provides a recipe which updates your local user's knownhosts
file with the remote host keys for each remote listed in your inventory file. This is most
commonly useful in cases where VOLTTRON is being deployed to virtual machines which are being
provisioned automatically. It makes changes in your user's local ``~/.ssh/known_hosts`` file.

Host configuration
~~~~~~~~~~~~~~~~~~

The ``host-config.yml`` playbook conducts system-level package installation and configuration
changes required for installing and running VOLTTRON. The playbook uses the inventory and associated
host configuration files to determine what is required (in particular, installing dependencies
needed for rabbitmq).
