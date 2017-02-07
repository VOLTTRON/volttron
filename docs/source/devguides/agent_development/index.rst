.. _Agent_Development:
=================
Agent Development
=================


.. warning::

    Due to changes in how authorization is handled, you will need to authorize agents running outside the platform
    (in Eclipse, PyCharm, etc.). This fix is only for local development of agents
    and should **not** be used on an actual deployment.


    .. code-block:: bash

        volttron-ctl auth add
        domain []:
        address []:
        user_id []:
        capabilities (delimit multiple entries with comma) []:
        roles (delimit multiple entries with comma) []:
        groups (delimit multiple entries with comma) []:
        mechanism [CURVE]:
        credentials []: /.*/
        comments []:
        enabled [True]:
        added entry domain=None, address=None, mechanism='CURVE', credentials=u'/.*/', user_id='ff6fea8e-53bd-4506-8237-fbb718aca70d'

.. toctree::
    :glob:
    :maxdepth: 2

    *
