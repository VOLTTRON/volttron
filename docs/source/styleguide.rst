.. _styleguide:
.. Reference anchor should be the same as the filename


==================================
This is the main title of the page
==================================

.. _code blocks:

Example Code Blocks
--------------------

Use bash for commands or user actions

.. code-block:: bash

   ls -al


Use this for the results of a command

.. code-block:: console

   total 5277200
   drwxr-xr-x 22 volttron volttron       4096 Oct 20 09:44 .
   drwxr-xr-x 23 volttron volttron       4096 Oct 19 18:39 ..
   -rwxr-xr-x  1 volttron volttron        164 Sep 29 17:08 agent-setup.sh
   drwxr-xr-x  3 volttron volttron       4096 Sep 29 17:13 applications


Use this when Python source code is displayed

.. code-block:: python

    @RPC.export
    def status_agents(self):
        return self._aip.status_agents()


Directives
----------

Taken from this `reference <http://docutils.sourceforge.net/docs/ref/rst/directives.html>`_

.. DANGER::

   Something very bad!

.. tip::

   This is something good to know

Some other directives
~~~~~~~~~~~~~~~~~~~~~

"attention", "caution", "danger", "error", "hint", "important", "note", "tip", "warning", "admonition"

You can use anchors for internal :ref:`references <code blocks>` too

Other resources
---------------

- http://pygments.org/docs/lexers/
- http://documentation-style-guide-sphinx.readthedocs.io/en/latest/style-guide.html
- http://www.sphinx-doc.org/en/stable/markup/code.html
