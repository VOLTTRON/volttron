.. _volttron_recipes:

===============
Ansible Recipes
===============

:std:doc:`Deployment Recipes <volttron-ansible:index>`

Begining with version 7, VOLTTRON introduces the concept of recipes. This system leverages
`ansible <https://docs.ansible.com/ansible/latest/index.html>`_ to orchestrate the deployment and
configuration process for VOLTTRON. These recipes can be used for any deployment, but are
especially useful for larger scale or distributed systems, where it is necessary to manage
many platforms in an organized way. Some of the key features are:

1. Platform management logic is implemented using custom ansible modules, which each perform narrow units of work.
2. The roles and modules are composed in playbooks which implement more complete workflows or procedures.
   These can be used as they are, or taken as starting point for building playbooks specific to a particular use case.
3. Implementation details specific to host-system differences (such as hardware architecture or linux distribution) are
   abstracted so that the user experience is consistent across supported systems.
4. Ansible's inventory system is leveraged so that the marginal burden of managing additional VOLTTRON
   deployments is low, and confidence of uniformity among those deployments is high.

:std:doc: `Getting started with recipes <volttron-ansible:index#getting-started-with-recipes>`
