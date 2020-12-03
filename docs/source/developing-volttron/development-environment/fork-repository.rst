.. _Fork-Repository:

======================
Forking the Repository
======================

The first step to editing the repository is to fork it into your own user space.  Creating a fork makes a copy of the
repository in your GitHub for you to make any changes you may require for your use-case.  This allows you to make
changes without impacting the core VOLTTRON repository.

Forking is done by pointing your favorite web browser to http://github.com/VOLTTRON/volttron and then clicking "Fork" on
the upper right of the screen.  (Note: You must have a GitHub account to fork the repository. If you don't have one, we
encourage you to `sign up <https://github.com/join?source_repo=VOLTTRON%2Fvolttron>`_.)

.. note::

   After making changes to your repository, you may wish to contribute your changes back to the Core VOLTTRON
   repository.  Instructions for contributing code may be found :ref:`here <Contributing-Code>`.


Cloning 'YOUR' VOLTTRON forked repository
=========================================

The next step in the process is to copy your forked repository onto your computer to work on.  This will create an
identical copy of the GitHub repository on your local machine.  To do this you need to know the address of your
repository.  The URL to your repository address will be ``https://github.com/<YOUR USERNAME>/volttron.git``.  From a
terminal execute the following commands:

.. code-block:: bash

    # Here, we are assuming you are doing develop work in a folder called `git`. If you'd rather use something else, that's OK.
    mkdir -p ~/git
    cd ~/git
    git clone -b develop https://github.com/<YOUR USERNAME>/volttron.git
    cd volttron

.. note::

  VOLTTRON uses develop as its main development branch rather than the standard `main` branch (the default).


Adding and Committing files
===========================

Now that you have your repository cloned, it's time to start doing some modifications.  Using a simple text editor
you can create or modify any file in the volttron directory.  After making a modification or creating a file
it is time to move it to the stage for review before committing to the local repository.  For this example let's assume
we have made a change to `README.md` in the root of the volttron directory and added a new file called `foo.py`.  To get
those files in the staging area (preparing for committing to the local repository) we would execute the following
commands:

.. code-block:: bash

    git add foo.py
    git add README.md

    # Alternatively in one command
    git add foo.py README.md

After adding the files to the stage you can review the staged files by executing:

.. code-block:: bash

    git status

Finally, in order to commit to the local repository we need to think of what change we actually did and be able to
document it.  We do that with a commit message (the -m parameter) such as the following.

.. code-block:: bash

    git commit -m "Added new foo.py and updated copyright of README.md"


Pushing to the remote repository
================================

The next step is to share our changes with the world through GitHub.  We can do this by pushing the commits
from your local repository out to your GitHub repository.  This is done by the following command:

.. code-block:: bash

    git push
