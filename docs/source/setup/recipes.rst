.. _recipes:

VOLTTRON Deployment Recipes
===========================

Begining with version 7.1, VOLTTRON introduces the concept of recipes. This system leverages
`ansible <https://docs.ansible.com/ansible/latest/index.html>`_ to orchestrate the deployment and
configuration process for VOLTTRON. These recipes can be used for any deployment, but are
especially useful for larger scale or distributed systems, where it is necessary to manage
many platforms in an organized way. Some of the key features are:

1. Organize recipes in roles and playbooks so that they can both be used as is, or as
   components for customized playbooks specific to a particular use case.
2. Abstract the host-system differences so that the installation process is consistent
   across supported architectures and operating systems.
3. Leverage ansible's inventory system so that the marginal burden of managing additional
   deployments is low, and confidence of uniformity among those deployments is high.

Getting started with recipes
----------------------------

The recipes system is designed to be executed from a user workstation or other server with ssh
access to the hosts which will be running the VOLTTRON platforms being configured. In order to do
so, you require a python environment with ansible installed. You can do this using pip in whatever
environment you like; it is included as an optional feature when bootstrapping the VOLTTRON environment,
to do that use the :ref:`Bootstrap-Options` and include the ``--deployment`` flag.

Available recipes
-----------------

All provided recipes are ansible playbooks and can be executed directly using the the ``ansible-playook``
command line tool. Each of the available playbooks are discussed in the following subsections, they
can all be found in the ``$VOLTTRON_ROOT/deployment/recipes`` directory.

Ensure host key entries
~~~~~~~~~~~~~~~~~~~~~~~

The ``ensure-host-keys.yml`` playbook provides a recipe which updates your local user's ``known_hosts``
file with the remote host keys for each remote listed in your inventory file. This is most
commonly useful in cases where VOLTTRON is being deployed to virtual machines which are being
provisioned automatically and therefore may have chaning host keys and automatically included
ssh keys. It makes changes in your user's local ``~/.ssh/known_hosts`` file. This playbook has
no VOLTTRON-specific content but is provided as a convenience.

Host configuration
~~~~~~~~~~~~~~~~~~

The ``host-config.yml`` playbook conducts system-level package installation and configuration
changes required for installing and running VOLTTRON. The playbook uses the inventory and associated
host configuration files to determine which optional dependencies are are required for the
particular deployment (for example, dependencies for rabbitMQ when using that message bus).
The playbook also allows the user to specify extra system-level dependencies to be included,
this can be used as a convenience, to avoid needing to write an additional playbook for installing
packages, or to cover the case where custom agents may have additional requirements that the
recipes is otherwise unaware of.

Note that because this playbook installs system packages, it must be passed a sudo password
when run (this is done with the standard ansible system and so the features provided by apply).

Install platform
~~~~~~~~~~~~~~~~

The ``install-platform.yml`` playbook installs the VOLTTRON source in the configured location,
creates the virtual environment with both dependencies and VOLTTRON installed, and configures
the platform itself. The recipe detects optional dependencies required by the platform (for
example, support for rabbitMQ message bus or web support), as well asl supporting extra bootstrap
options and PyPI packages to be included. It also creates an activation script which will set
VOLTTRON-related environmental variables as well as activating the virtual environment, making
it easy to interact with the platfor locally if required.
