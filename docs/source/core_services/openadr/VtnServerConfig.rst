.. _VtnServerConfig:

OpenADR VTN Server: Installation and Configuration
==================================================

The Kisensum VTN server is a Django application written in Python 3 and utilizing a Postgres database.

Get Source Code
---------------

To install the VTN server, first get the code by cloning volttron-applications from github
and checking out the openadr software.
::

    $ cd ~/repos
    $ git clone https://github.com/volttron/volttron-applications
    $ cd volttron-applications
    $ git checkout master

Install Python 3
----------------

After installing Python3 on the server, configure an openadr virtual environment:
::

    $ sudo pip install virtualenvwrapper
    $ mkdir ~/.virtualenvs (if it doesn’t exist already)

Edit **~/.bashrc** and add these lines:
::

    export WORKON_HOME=$HOME/.virtualenvs
    export PROJECT_HOME=$HOME/repos/volttron-applications/kisensum/openadr
    source virtualenvwrapper.sh

Create the openadr project’s virtual environment:
::

    $ source ~/.bashrc
    $ mkvirtualenv -p /usr/bin/python3 openadr
    $ setvirtualenvproject openadr ~/repos/volttron-applications/kisensum/openadr
    $ workon openadr

From this point on, use **workon openadr** to operate within the openadr virtual environment.

Create a local site override for Django’s base settings file as follows. First,
create **~/.virtualenvs/openadr/.settings** in a text editor, adding the following line to it:
::

    openadr.settings.site

Then, edit **~/.virtualenvs/openadr/postactivate**, adding the following lines:
::

    PROJECT_PATH=`cat "$VIRTUAL_ENV/$VIRTUALENVWRAPPER_PROJECT_FILENAME"`
    PROJECT_ROOT=`dirname $PROJECT_PATH`
    PROJECT_NAME=`basename $PROJECT_PATH`
    SETTINGS_FILENAME=".settings"
    ENV_FILENAME=".env_postactivate.sh"

    # Load the default DJANGO_SETTINGS_MODULE from a .settings
    # file in the django project root directory.
    export OLD_DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
    if [ -f $VIRTUAL_ENV/$SETTINGS_FILENAME ]; then
       export DJANGO_SETTINGS_MODULE=`cat "$VIRTUAL_ENV/$SETTINGS_FILENAME"`
    fi

Finally, create **$PROJECT_HOME/openadr/openadr/openadr/settings/site.py**, which holds overrides
to base.py, the Django base settings file. At a minimum, this file should contain the following:
::

    from .base import *
    ALLOWED_HOSTS = [‘*’]

A more restrictive ALLOWED_HOSTS setting (e.g. ‘ki-evi.com’) should be used in place of ‘*’ if it is known.

Use Pip to Install Third-Party Software
---------------------------------------
::

    $ workon openadr
    $ pip install -r requirements.txt

Set up a Postgres Database
--------------------------

Install postgres.

Create a postgres user.

Create a postgres database named openadr.

(The user name, user password, and database name must match what is in
**$PROJECT_HOME/openadr/openadr/settings/base.py** or the override settings
in **$PROJECT_HOME/openadr/openadr/settings/local.py**.)

Migrate the Database and Create an Initial Superuser
----------------------------------------------------
::

    $ workon openadr
    $ cd openadr
    $ python manage.py migrate
    $ python manage.py createsuperuser

This is the user that will be used to login to the VTN application for the first time,
and will be able to create other users and groups.

Configure Rabbitmq
------------------

rabbitmq is used by celery, which manages the openadr server’s periodic tasks.

Install and run rabbitmq as follows (for further information, see http://www.rabbitmq.com/download.html):
::

    $ sudo apt-get install rabbitmq-server
    $ sudo rabbitmq-server -detached (note the single dash)

Start the VTN Server
--------------------

This process is executed from **screen** so that it remains active if the shell’s ssh session ends:
::

    $ screen -t openadr-server
    $ workon openadr
    $ cd openadr
    $ python manage.py runserver 0.0.0.0:8000

Start Celery
------------

This process is executed from **screen** so that it remains active if the shell’s ssh session ends:
::

    $ screen -t openadr-celery
    $ workon openadr
    $ cd openadr
    $ celery -A openadr worker -B
