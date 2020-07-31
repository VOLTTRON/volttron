.. _documentation:

Contributing Documentation
=============================

The Community is encouraged to contribute documentation back to the project as they work through use cases the
developers may not have considered or documented. By contributing documentation back, the community can
learn from each other and build up a much more extensive knowledge base.

|VOLTTRON| documentation utilizes ReadTheDocs: http://volttron.readthedocs.io/en/develop/ and is built
using the `Sphinx <http://www.sphinx-doc.org/en/stable/>`_ Python library with static content in
`Restructured Text <http://docutils.sourceforge.net/docs/user/rst/quickref.html>`_.

Building the Documentation
---------------------------

Static documentation can be found in the `docs/source` directory. Edit or create new .rst files to add new content
using the `Restructured Text <http://docutils.sourceforge.net/docs/user/rst/quickref.html>`_ format. To see the results
of your changes. the documentation can be built locally through the command line using the following instructions.

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
creating a pull request. When the changes are accepted and merged, they will be reflected in the ReadTheDocs site.

.. |VOLTTRON| unicode:: VOLTTRON U+2122
