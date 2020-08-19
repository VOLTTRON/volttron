.. _Contributing-Documentation:

==========================
Contributing Documentation
==========================

The Community is encouraged to contribute documentation back to the project as they work through use cases the
developers may not have considered or documented.  By contributing documentation back, the community can
learn from each other and build up a more extensive knowledge base.

|VOLTTRON| documentation utilizes ReadTheDocs: http://volttron.readthedocs.io/en/develop/ and is built
using the `Sphinx <http://www.sphinx-doc.org/en/stable/>`_ Python library with static content in
`Restructured Text <http://docutils.sourceforge.net/docs/user/rst/quickref.html>`_.


Building the Documentation
==========================

Static documentation can be found in the `docs/source` directory.  Edit or create new .rst files to add new content
using the `Restructured Text <http://docutils.sourceforge.net/docs/user/rst/quickref.html>`_ format.  To see the results
of your changes the documentation can be built locally through the command line using the following instructions:

If you've already :ref:`bootstrapped <setup>` |VOLTTRON|, do the following while activated. If not,
this will also pull down the necessary |VOLTTRON| libraries.

.. code-block:: bash

   python bootstrap.py --documentation
   cd docs
   make html

Then, open your browser to the created local files:

.. code-block:: bash

   file:///home/<USER>/git/volttron/docs/build/html/overview/index.html


When complete, changes can be contributed back using the same process as code :ref:`contributions <contributing>` by
creating a pull request.  When the changes are accepted and merged, they will be reflected in the ReadTheDocs site.

.. |VOLTTRON| unicode:: VOLTTRON U+2122


.. _Documentation-Styleguide:

Documentation Styleguide
========================


Naming Conventions
------------------

* File names and directories should be all lower-case and use only dashes/minus signs (-) as word separators

::

    index.rst
    ├── first-document.rst
    ├── more-documents
    │   ├──second-document.rst

* Reference Labels should be Capitalized and dash/minus separated:

::

    .. _Reference-Label:

* Headings and Sub-headings should be written like book titles:

::

    ==============
    The Page Title
    ==============


Headings
--------

Each page should have a main title:

::

    ==================================
    This is the Main Title of the Page
    ==================================

It can be useful to include reference labels throughout the document to use to refer back to that section of
documentation.  Include reference labels above titles and important headings:

::

    .. _Main-Title:

    ==================================
    This is the main title of the page
    ==================================


Heading Levels
~~~~~~~~~~~~~~

* Page titles and documentation parts should use over-line and underline hashes:

::

    =====
    Title
    =====

* Chapter headings should be over-lined and underlined with asterisks

::

    *******
    Chapter
    *******

* For sections, subsections, sub-subsections, etc. underline the heading with the following:

    * =, for sections
    * -, for subsections
    * ^, for sub-subsections
    * “, for paragraphs


In addition to following guidelines for styling, please separate headers from previous content by two newlines.

::

    =====
    Title
    =====

        Content


    Subheading
    ==========


Example Code Blocks
--------------------

Use bash for commands or user actions:

.. code-block:: bash

   ls -al


Use this for the results of a command:

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
