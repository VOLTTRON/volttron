.. _Contributing-Code:

=================
Contributing Code
=================

As an open source project VOLTTRON requires input from the community to keep development focused on new and useful
features.  To that end we are revising our commit process to hopefully allow more contributors to be a part of the
community.  The following document outlines the process for source code and documentation to be submitted.
There are GUI tools that may make this process easier, however this document will focus on what is required from the
command line.

The only requirements for contributing are Git (Linux version control software) and your favorite web browser.

.. note::

   The following guide assumes the user has already created a fork of the core VOLTTRON repository.  Please review the
   :ref:`docs <Fork-Repository>` if you have not yet created a fork.

The only technical requirements for contributing are Git (version control software) and your
favorite web browser.

As a part of VOLTTRON joining the Eclipse community, Eclipse requires that all contributors sign the
`Eclipse Contributor agreement <https://www.eclipse.org/legal/ECA.php>`_ before making a pull request.


Reviewing Changes
=================

Okay, we've written a cool new `foo.py` script to service `bar` in our deployment.  Let's make sure our code is
up-to-snuff.

Code
----

First, go through the code.

.. note::

    We on the VOLTTRON team would recommend an internal code review - it can be really hard to catch small mistakes,
    typos, etc. for code you just finished writing.

* Does the code follow best-practices for Python, object-oriented programming, unit and integration testing, etc.?
* Does the code contain any typos and does it follow `Pep8 guidelines <https://www.python.org/dev/peps/pep-0008/>`_?
* Does the code follow the guidelines laid out in the VOLTTRON documentation?


Docs
----

Next, Check out the documentation.

* Is it complete?

    * Has an introduction describing purpose
    * Describes configuration including all parameters
    * Includes installation instructions
    * Describes behavior at runtime
    * Describes all available endpoints (JSON-RPC, pub/sub messages, Web-API endpoints, etc.)

* Does it follow the  :ref:`VOLTTRON documentation guidelines <Contributing-Documentation>`?


Tests
-----

You've included tests, right?  Unit and integration tests show users that `foo.py` is better than their wildest
dreams - all of the features work, and include components they hadn't even considered themselves!

* Are the unit tests thorough?

    * Success and failure cases
    * Tests for each independent component of the code

* Do the integration tests capture behavior with a running VOLTTRON platform?

    * Success and Failure cases
    * Tests for each endpoint
    * Tests for interacting with other agents if necessary
    * Are status, health, etc. updating as expected when things go wrong or the code recovers?

* Can the tests be read to describe the behavior of the code?

Structure
---------

For agents and drivers, the VOLTTRON team has some really simple structure recommendations.  These make your project
structure nice and tidy, and integrate nicely with the core repository.

For agents:

::

    TestAgent/
    ├── setup.py
    ├── config
    ├── README.rst
    ├── tester
    |   ├── agent.py
    |   └── __init__.py
    └── tests
        └── test_agent.py

For drivers, the interface should be a file named after the driver in the Platform Driver's interfaces directory:

::

    ├── platform_driver
    │         ├── agent.py
    │         ├── driver.py
    │         ├── __init__.py
    │         ├── interfaces
    │         │         ├── __init__.py
    │         │         ├── bacnet.py
    |         |         ├── csvdriver.py
    │         │         └── new_driver.py

Or in the `__init__.py` file in a directory named after the driver in the Platform Driver's interfaces directory:

::

    ├── platform_driver
    │         ├── agent.py
    │         ├── driver.py
    │         ├── __init__.py
    │         ├── interfaces
    │         │         ├── __init__.py
    │         │         ├── bacnet.py
    │         │         ├── new_driver
    │         │         |   └── __init__.py

This option is ideal for adding additional code files, and including documentation and tests.


Creating a Pull Request to the main VOLTTRON repository
=======================================================

After reviewing changes to our fork of the VOLTTRON repository, we want our changes to be added into the main VOLTTRON
repository.  After all, our `foo.py` can cure a lot of the world's problems and of course it is always good to have a
copyright with the correct year.  Open your browser to
https://github.com/VOLTTRON/volttron/compare/develop...YOUR_USERNAME:develop.

On that page the base fork should always be VOLTTRON/volttron with the base develop, the head fork should
be <YOUR USERNAME>/volttron and the compare should be the branch in your repository to pull from.  Once you have
verified that you have got the right changes made then, click on create pull request, enter a title and description that
represent your changes and submit the pull request.

The VOLTTRON repository has a description template to use to format your PR:

::

    # Description

    Please include a summary of the change and which issue is fixed. Please also include relevant motivation and context. List any dependencies that are required for this change.

    Fixes # (issue)

    ## Type of change

    Please delete options that are not relevant.

    - [ ] Bug fix (non-breaking change which fixes an issue)
    - [ ] New feature (non-breaking change which adds functionality)
    - [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
    - [ ] This change requires a documentation update

    # How Has This Been Tested?

    Please describe the tests that you ran to verify your changes. Provide instructions so we can reproduce. Please also list any relevant details for your test configuration

    - [ ] Test A
    - [ ] Test B

    **Test Configuration**:
    * Firmware version:
    * Hardware:
    * Toolchain:
    * SDK:

    # Checklist:

    - [ ] My code follows the style guidelines of this project
    - [ ] I have performed a self-review of my own code
    - [ ] I have commented my code, particularly in hard-to-understand areas
    - [ ] I have made corresponding changes to the documentation
    - [ ] My changes generate no new warnings
    - [ ] I have added tests that prove my fix is effective or that my feature works
    - [ ] New and existing unit tests pass locally with my changes
    - [ ] Any dependent changes have been merged and published in downstream modules

.. note::

    The VOLTTRON repository includes a stub for completing your pull request. Please follow the stub to facilitate the
    reviewing and merging processes.


What happens next?
==================

Once you create a pull request, one or more VOLTTRON team members will review your changes and either accept them as is
ask for modifications in order to have your commits accepted.  Typical response time is approximately two weeks; please
be patient, your pull request will be reviewed.  You will be automatically emailed through the GitHub notification
system when this occurs (assuming you haven't changed your GitHub preferences).


Merging changes from the main VOLTTRON repository
-------------------------------------------------

As time goes on the VOLTTRON code base will continually be modified so the next time you want to work on a change to
your files the odds are your local and remote repository will be out of date.  In order to get your remote VOLTTRON
repository up to date with the main VOLTTRON repository you could simply do a pull request to your remote repository
from the main repository.  To do so, navigate your browser to
https://github.com/YOUR_USERNAME/volttron/compare/develop...VOLTTRON:develop.

Click the 'Create Pull Request' button.  On the following page click the 'Create Pull Request' button.  On the next page
click 'Merge Pull Request' button.

Once your remote is updated you can now pull from your remote repository into your local repository through the
following command:

.. code-block:: bash

    git pull

The other way to get the changes into your remote repository is to first update your local repository with the
changes from the main VOLTTRON repository and then pushing those changes up to your remote repository.  To do that you
need to first create a second remote entry to go along with the origin.  A remote is simply a pointer to the url of a
different repository than the current one.  Type the following command to create a new remote called 'upstream':

.. code-block:: bash

    git remote add upstream https://github.com/VOLTTRON/volttron

To update your local repository from the main VOLTTRON repository then execute the following command where upstream is
the remote and develop is the branch to pull from:

.. code-block:: bash

    git pull upstream develop

Finally to get the changes into your remote repository you can execute:

.. code-block:: bash

    git push origin


.. _Git-Commands:

Other commands to know
^^^^^^^^^^^^^^^^^^^^^^

At this point in time you should have enough information to be able to update both your local and remote repository
and create pull requests in order to get your changes into the main VOLTTRON repository.  The following commands are
other commands to give you more information that the preceding tutorial went through


Viewing what the remotes are in our local repository
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git remote -v


Stashing changed files so that you can do a merge/pull from a remote
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git stash save 'A comment to be listed'


Applying the last stashed files to the current repository
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git stash pop


Finding help about any git command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git help
    git help branch
    git help stash
    git help push
    git help merge


Creating a branch from the branch and checking it out
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git checkout -b newbranchname


Checking out a branch (if not local already will look to the remote to checkout)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git checkout branchname


Removing a local branch (cannot be current branch)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git branch -D branchname


Determine the current and show all local branches
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git branch


Using Travis Continuous Integration Tools
-----------------------------------------

The main VOLTTRON repository is hooked into an automated build tool called travis-ci.  Your remote repository can be
automatically built with the same tool by hooking your account into travis-ci's environment. To do this go to
https://travis-ci.org and create an account.  You can using your GitHub login directly to this service.  Then you will
need to enable the syncing of your repository through the travis-ci service.  Finally you need to push a new change to
the repository.  If the build fails you will receive an email notifying you of that fact and allowing you to modify the
source code and then push new changes out.
