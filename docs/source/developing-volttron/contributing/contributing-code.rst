.. _Contributing-Code:

================================
Contributing to Eclipse VOLTTRON
================================

As an open source project Eclipse VOLTTRON requires input from the community to keep development focused on new and
useful features.  To that end we are revising our commit process to hopefully allow more contributors to be apart of the
community.  The following document outlines the process for source code and documentation to be submitted.
There are GUI tools that may make this process easier, however this document will focus on what is required from the
command line.

The only requirement is that you sign the Eclipse Contributor agreement: https://www.eclipse.org/legal/ECA.php
before making a pull request.
The only technical requirements for contributing are Git (version control software) and your
favorite web browser.


Forking the main VOLTTRON repository
====================================

The first step to editing the repository is to fork it into your own user space.  This is done by pointing
your favorite web browser to http://github.com/VOLTTRON/volttron and then clicking "Fork" on the upper right of the
screen.  (Note: You must have a GitHub account to fork the repository. If you don't have one, we encourage you to
`sign up https://github.com/join?source_repo=VOLTTRON%2Fvolttron`.)


Cloning 'YOUR' VOLTTRON forked repository
=========================================

The next step in the process is to copy your forked repository onto your computer to work on.  This will create an
identical copy of the GitHub repository on your local machine.  To do this you need to know the address of your
repository.  The URL to your repository address will be "https://github.com/<YOUR USERNAME>/volttron.git".  From a
terminal execute the following commands:

.. note::

  VOLTTRON uses develop as its main development branch rather than the standard master branch (the default).

.. code-block:: bash

    # Here, we are assuming you are doing develop work in a folder called `git`. If you'd rather use something else, that's OK.
    mkdir -p ~/git
    cd ~/git
    git clone -b develop https://github.com/<YOUR USERNAME>/volttron.git
    cd volttron


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


Creating a Pull Request to the main VOLTTRON repository
=======================================================

Now we want our changes to be added into the main VOLTTRON repository.  After all, our `foo.py` can cure a lot of the
world's problems and of course it is always good to have a copyright with the correct year.  Open your browser
to https://github.com/VOLTTRON/volttron/compare/develop...YOUR_USERNAME:develop.

On that page the base fork should always be VOLTTRON/volttron with the base develop, the head fork should
be <YOUR USERNAME>/volttron and the compare should be the branch in your repository to pull from.  Once you have
verified that you have got the right changes made then, click on create pull request, enter a title and description that
represent your changes and submit the pull request.

.. note::

    The VOLTTRON repository includes a stub for completing your pull request. Please follow the stub to facilitate the
    reviewing and merging processes.


What happens next?
==================

Once you create a pull request, one or more VOLTTRON team members will review your changes and either accept them as is
ask for modifications in order to have your commits accepted.  You will be automatically emailed through the GitHub
notification system when this occurs (assuming you haven't changed your GitHub preferences).


Next Steps
----------


Merging changes from the main VOLTTRON repository
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
