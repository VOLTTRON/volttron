.. _Speeding-Builds:

Speeding Up VOLTTRON™ Builds
============================

The VOLTTRON_ build process is straightforward enough, but it can be a bit slow. It relies on pip_ to download, build, and install required third-party packages. The problem is that pip does very little to cache the results of builds, especially those which require compilation. In fact, the only thing `pip caches`_ is the downloaded source archives. While this speeds up the download process and lightens the burden of the Python package index (PyPi_) server(s), it does little to improve the overall build speed. The majority of this document will focus on three techniques for improving VOLTTRON build times, including the pip download cache. But before we begin, let's discuss what is involve in building VOLTTRON.

.. _VOLTTRON: https://github.com/VOLTTRON/volttron
.. _pip: https://pip.pypa.io/en/latest/index.html
.. _pip caches: https://pip.pypa.io/en/latest/reference/pip_install.html#caching
.. _Pypi: https://pypi.python.org


Introducing bootstrap.py
------------------------

VOLTTRON can actually be built just like any other Python project. It includes a ``setup.py`` script in the project root so one can perform the standard *build*, *install*, *sdist_*\*, and *bdist_*\*, etc. commands. That's great if we have some project which requires VOLTTRON, but that is not the typical use case for VOLTTRON. Usually, and especially for developers, VOLTTRON is run in a virtual environment so its dependencies can be easily met. Enter ``bootstrap.py``.

Sitting next to ``setup.py`` in the project root is ``bootstrap.py``, a script designed to *bootstrap* a virtual environment and make dependency installation a repeatable process. Bootstrapping occurs in two stages: download ``virtualenv``, using it to create a virtual environment, and download and install dependencies. The first, or bootstrap, stage typically happens once. The second, or update, stage happens many times as dependencies are added or updated. It is the update stage that takes the majority of the time and is the stage we focus on in this document.

To perform the bootstrap stage, ``bootstrap.py`` must be executed using the system Python interpreter.

.. code::

  $ python2.7 bootstrap.py

The above command assumes ``python2.7`` is in the ``PATH`` and creates the virtual environment in the default ``env`` directory. After the virtual environment is created, the update stage is automatically started by executing ``bootstrap.py`` using the python interpreter in the newly created virtual environment. Subsequent updates must also use the interpreter in the virtual environment.

.. code::

  $ env/bin/python bootstrap.py

Multiple options are available to alter the behavior of *bootstrap.py*. Use the ``--help`` option to list options and show the script's usage message.

.. code::

  $ env/bin/python bootstrap.py --help
  usage: 
    bootstrap: python2.7 bootstrap.py [options]
    update:    $VIRTUAL_ENV/bin/python bootstrap.py [options]

  Bootstrap and update a virtual Python environment for VOLTTRON development.

  optional arguments:
    -h, --help            show this help message and exit
    -q, --quiet           produce less output
    -v, --verbose         produce extra output

  bootstrap options:
    --envdir VIRTUAL_ENV  alternate location for virtual environment
    --force               force installing in non-empty directory
    -o, --only-virtenv    create virtual environment and exit (skip install)
    --prompt PROMPT       provide alternate prompt in activated environment
                          (default: (volttron))

  update options:
    -u, --upgrade         upgrade installed packages
    -w, --wheel           build wheels in the pip wheelhouse

  The first invocation of this script, which should be made using the system
  Python, will create a virtual Python environment in the 'env' subdirectory in
  the same directory as this script or in the directory given by the --envdir
  option. Subsequent invocations of this script should use the Python executable
  installed in the virtual environment.
  
Enough about ``bootstrap.py``. Let's move on to the magic. As we do, please note the following about the output of commands:

* Ellipses (...) are used to denote where excessive drivel was cut out to make this document shorter and more readable
* Lines beginning with a plus (+) in ``bootstrap.py`` output show the actual calls to pip or easy_install, including all arguments.

Oh, yeah. That reminds me that two packages require special handling. BACpypes must be installed using easy_install because it is only offered as an egg and pip doesn't install from eggs. It will always be downloaded, if it isn't already installed, and will not benefit from any of the speedups below. And pyzmq is handled separately to pass options to its setup.py.

  Note: As of 26 Feb 2015, BACpypes provides a wheel. Yay! Next step: Python 3.

Okay. On with the show.


Preparation
-----------

Before building, we need to clone the VOLTTRON_ repository. We make sure to checkout the master branch to get the latest bootstrap script which has the special sauce for the real speed-up.

.. code::

  [volttron@inamatus ~]$ git clone -b master https://github.com/VOLTTRON/volttron
  Cloning into 'volttron'...
  remote: Counting objects: 3268, done.
  remote: Compressing objects: 100% (122/122), done.
  Receiving objects: 100% (3268/3268), 14.25 MiB | 749.00 KiB/s, done.
  Resolving deltas: 100% (2070/2070), done.
  Checking connectivity... done.

Let's move into that directory where the remainder of our time will be spent.

.. code::

  [volttron@inamatus ~]$ cd volttron/

Now that we have the code, we are ready for testing. We'll start with the slow method and work toward the fastest.


Meh (a.k.a. Slow Method)
------------------------

Since version 6.0, `pip caches`_ downloaded source files to speed the download and install process when a package is once again required. The default location for this cache on Linux is in ``$HOME/.cache/pip`` (or ``~/.cache/pip``). As can be seen by the next command, we currently have no cache.

.. code::

  [volttron@inamatus volttron]$ find ~/.cache/pip
  find: `/home/volttron/.cache/pip': No such file or directory

So let's try bootstrapping the environment. We'll use bash's built-in ``time`` command to time the execution of each bootstrap command for comparison.

.. code::

  [volttron@inamatus volttron]$ time python2.7 bootstrap.py
  Creating virtual Python environment
  Downloading virtualenv DOAP record
  Downloading virtualenv 12.0.7
  New python executable in /home/volttron/volttron/env/bin/python2.7
  Also creating executable in /home/volttron/volttron/env/bin/python
  Installing setuptools, pip...done.
  Installing required packages
  + easy_install BACpypes>=0.10,<0.11
    ...
  + pip install --global-option --quiet --install-option --zmq=bundled --no-deps pyzmq>=14.3,<15
    ...
  + pip install --global-option --quiet --editable ./lib/jsonrpc --editable . --requirement ./requirements.txt
    ...
  Successfully installed Smap-2.0.24c780d avro-1.7.7 configobj-5.0.6 ecdsa-0.13 flexible-jsonrpc
  gevent-1.0.1 greenlet-0.4.5 monotonic-0.1 numpy-1.9.1 pandas-0.15.2 paramiko-1.15.2
  pycrypto-2.6.1 pymodbus-1.2.0 pyserial-2.7 python-dateutil-2.4.0 pytz-2014.10 requests-2.5.3
  simplejson-3.6.5 six-1.9.0 twisted-15.0.0 volttron-2.0 wheel-0.24.0 zope.interface-4.1.2

  real  9m2.299s
  user  7m51.790s
  sys   0m14.450s

Whew! The build took just over nine minutes on my nearly-4-year-old MacBook Pro running Arch Linux. In case you are wondering about my system's name, as seen in the bash prompt, *inamatus* is Latin for *unloved*. I'll leave it as an exercise for the user to determine why my system is unloved (hint: it has to do with a wonderful fruit with a bite missing from the side).

Anyway, let's have another look at the pip download cache.

.. code::

  [volttron@inamatus volttron]$ find ~/.cache/pip -type f
  /home/volttron/.cache/pip/http/9/a/b/2/1/9ab21efc4225c8eb9aa41d1c76abef2a53babcefa438a79fa4e981ce
  /home/volttron/.cache/pip/http/9/2/6/7/2/92672ab99ac77960252018fbcb4f40984eef60ba5588229a729f18f5
  /home/volttron/.cache/pip/http/9/e/6/1/9/9e61964f51d8a05a20ecf21eef694877f28cb654a123ce1316ff77e5
  /home/volttron/.cache/pip/http/9/7/7/1/a/9771a6b64f3294ac335fdb8574cd3564e21c130924697381d72fd04d
  /home/volttron/.cache/pip/http/a/a/7/e/8/aa7e8bc2af1068a43747b0f771b426b7dcf7708283ca3ce3d92a2afc
    ...
  /home/volttron/.cache/pip/http/8/f/9/0/d/8f90d7cf09a2b5380a319b0df8eed268be28d590b6b5f71598a3b56f
  /home/volttron/.cache/pip/http/8/d/e/d/a/8deda849bcfd627b8587addf049f79bb333dd8fe1eae1d5053881039
  /home/volttron/.cache/pip/http/8/8/7/a/6/887a67fb460d57a10a50deef3658834b9ac01722244315227d334628
  /home/volttron/.cache/pip/http/5/5/4/e/2/554e2be8d96625aa74a4e0c4ee4a4b1ca10a442c2877bd3fff96e2a6
  /home/volttron/.cache/pip/http/1/d/c/8/3/1dc83c11a861a2bc20d9c0407b41089eba236796ba80c213511f1f74
  /home/volttron/.cache/pip/log/debug.log

The output is truncated because it was long and boring. The important thing is that it now exists. Next let's remove the virtual environment and rebuild to see what effect the download cache has on our build time.

.. code::

  [volttron@inamatus volttron]$ rm -rf env
  [volttron@inamatus volttron]$ time python2.7 bootstrap.py
    ...

  real  8m35.387s
  user  7m50.770s
  sys   0m14.170s

Notice that our CPU time was nearly the same, about 8 minutes (user + sys). So the remaining time was likely spent on I/O, which was reduced by about 30 seconds. We need something else to reduce CPU time. Enter ccache.


Better
------

What is ccache? According to the official ccache_ site,

  ccache is a compiler cache. It speeds up recompilation by caching the result of previous compilations and detecting when the same compilation is being done again.

.. _ccache: https://ccache.samba.org/

Sounds like just the thing we need. ccache is already properly configured on my system, it just needs to be placed early in the ``PATH`` to be found before the official gcc compilers.

.. code::

  [volttron@inamatus volttron]$ which gcc
  /usr/bin/gcc
  [volttron@inamatus volttron]$ export PATH=/usr/lib/ccache/bin:$PATH
  [volttron@inamatus volttron]$ which gcc
  /usr/lib/ccache/bin/gcc

Now to prove to ourselves that the cache will be filled during the next run, let's have a look at the cache status.

.. code::

  [volttron@inamatus volttron]$ ccache -s
  cache directory                     /home/volttron/.ccache
  primary config                      /home/volttron/.ccache/ccache.conf
  secondary config      (readonly)    /etc/ccache.conf
  cache hit (direct)                     0
  cache hit (preprocessed)               0
  cache miss                             0
  files in cache                         0
  cache size                           0.0 kB
  max cache size                       5.0 GB

The cache is indeed empty.

Nothing up my sleeve... Presto!

.. code::

  [volttron@inamatus volttron]$ rm -rf env
  [volttron@inamatus volttron]$ time python2.7 bootstrap.py
    ...

  real  6m3.496s
  user  4m57.960s
  sys   0m10.880s

One might expect a ccache build to take slightly longer than the baseline on the first build within a single project. This build completed about two minutes faster. Let's look at the ccache status to discover why.

.. code::

  [volttron@inamatus volttron]$ ccache -s
  cache directory                     /home/volttron/.ccache
  primary config                      /home/volttron/.ccache/ccache.conf
  secondary config      (readonly)    /etc/ccache.conf
  cache hit (direct)                   204
  cache hit (preprocessed)              23
  cache miss                           633
  called for link                      140
  called for preprocessing              95
  compile failed                      1139
  preprocessor error                     4
  bad compiler arguments                 5
  autoconf compile/link                103
  no input file                         19
  files in cache                      1316
  cache size                          26.1 MB
  max cache size                       5.0 GB

Ah ha. There were a total of 227 cache hits, meaning that some of the files were identical across all the built packages and the cached version could be used rather than recompiling. Let's see how subsequent builds improve with few cache misses.

.. code::

  [volttron@inamatus volttron]$ rm -rf env
  [volttron@inamatus volttron]$ time python2.7 bootstrap.py
    ...

  real  3m15.811s
  user  2m24.890s
  sys   0m7.090s

Wow! Now we're cooking with gas. Build times have been cut to nearly 1/3 of our baseline. This ccache status shows only 14 cache misses over our previous run:

.. code::

  [volttron@inamatus volttron]$ ccache -s
  cache directory                     /home/volttron/.ccache
  primary config                      /home/volttron/.ccache/ccache.conf
  secondary config      (readonly)    /etc/ccache.conf
  cache hit (direct)                  1038
  cache hit (preprocessed)              35
  cache miss                           647
  called for link                      280
  called for preprocessing             190
  compile failed                      2278
  preprocessor error                     8
  bad compiler arguments                10
  autoconf compile/link                206
  no input file                         38
  files in cache                      1365
  cache size                          35.0 MB
  max cache size                       5.0 GB

So using ccache is a big win. Anyone compiling C or C++ on a Linux system should have ccache enabled. Wait, make that *must*. Go, now, and enable it on your Linux boxen. Or maybe finish reading this and then go do it. But do it!

Best
----

Now you're thinking "how could it get any better," right? Well, it can. What if those compiled packages only needed to be rebuilt when a new version was required instead of every time they are installed.

When pip installs a package, it downloads the source and executes the packages ``setup.py`` like so: ``python setup.py install``. The install command builds the package and installs it directly into the file system. What if we could package up the build results into an archive and just extract them to the file system when the package is installed. Enter **wheel**.

pip supports the latest Python packaging format known as wheel. Typically this just means that it can install packages in the `wheel format`_. However, if the wheel_ package is installed, pip can also `build wheels`_ from source, executing ``python setup.py bdist_wheel``. By default, wheels are placed in the *wheelhouse* directory in the current working directory. But we can alter that location by setting an environment variable (read more on configuring pip here_).

.. _wheel format: http://wheel.readthedocs.org/en/latest
.. _wheel: https://pypi.python.org/pypi/wheel
.. _build wheels: https://pip.pypa.io/en/latest/reference/pip_wheel.html

.. code::

  [volttron@inamatus volttron]$ export PIP_WHEEL_DIR=$HOME/.cache/pip/wheelhouse

We also need to tell pip to look for the wheels, again using an environment variable. The directory needs to exist because while the wheel command will create the directory when creating the packages, pip may try to search the directory first.

.. code::

  [volttron@inamatus volttron]$ export PIP_FIND_LINKS=file://$PIP_WHEEL_DIR
  [volttron@inamatus volttron]$ mkdir $PIP_WHEEL_DIR

So to get this all working, bootstrapping now has to occur in three steps: install the virtual environment, build the wheels, and install the requirements. ``bootstrap.py`` takes options that control its behavior. The first pass requires the ``-o`` or ``--only-virtenv`` option to stop bootstrap after installing the virtual environment and prevent the update stage.

.. code::

  [volttron@inamatus volttron]$ rm -rf env
  [volttron@inamatus volttron]$ time python2.7 bootstrap.py --only-virtenv
  Creating virtual Python environment
  Downloading virtualenv DOAP record
  Downloading virtualenv 12.0.7
  New python executable in /home/volttron/volttron/env/bin/python2.7
  Also creating executable in /home/volttron/volttron/env/bin/python
  Installing setuptools, pip...done.

  real  0m3.866s
  user  0m1.480s
  sys   0m0.230s

The second step requires the ``-w`` or ``--wheel`` option to build the wheels. Because the virtual environment already exists, ``bootstrap.py`` must be called with the virtual environment Python, not the system Python.

.. code::

  [volttron@inamatus volttron]$ time env/bin/python bootstrap.py --wheel
  Building required packages
  + pip install --global-option --quiet wheel
    ...
  + pip wheel --global-option --quiet --build-option --zmq=bundled --no-deps pyzmq>=14.3,<15
    ...
  + pip wheel --global-option --quiet --editable ./lib/jsonrpc --editable . --requirement ./requirements.txt
    ...
    Destination directory: /home/volttron/.cache/pip/wheelhouse
  Successfully built numpy pandas gevent monotonic pymodbus simplejson Smap greenlet pycrypto
  twisted pyserial configobj avro zope.interface

  real  3m15.431s
  user  2m17.980s
  sys   0m5.630s

It took 3.25 minutes to build the wheels (with ccache still enabled). Repeating this command results in nothing new being compiled and takes only 4 seconds. Only new versions of packages meeting the requirements will be built.

.. code::

  [volttron@inamatus volttron]$ time env/bin/python bootstrap.py --wheel
  Building required packages
    ...
  Skipping numpy, due to already being wheel.
  Skipping pandas, due to already being wheel.
  Skipping python-dateutil, due to already being wheel.
  Skipping requests, due to already being wheel.
  Skipping flexible-jsonrpc, due to being editable
  Skipping pyzmq, due to already being wheel.
  Skipping gevent, due to already being wheel.
  Skipping monotonic, due to already being wheel.
  Skipping paramiko, due to already being wheel.
  Skipping pymodbus, due to already being wheel.
  Skipping setuptools, due to already being wheel.
  Skipping simplejson, due to already being wheel.
  Skipping Smap, due to already being wheel.
  Skipping wheel, due to already being wheel.
  Skipping volttron, due to being editable
  Skipping pytz, due to already being wheel.
  Skipping six, due to already being wheel.
  Skipping greenlet, due to already being wheel.
  Skipping ecdsa, due to already being wheel.
  Skipping pycrypto, due to already being wheel.
  Skipping pyserial, due to already being wheel.
  Skipping twisted, due to already being wheel.
  Skipping configobj, due to already being wheel.
  Skipping avro, due to already being wheel.
  Skipping zope.interface, due to already being wheel.

  real	0m3.998s
  user	0m3.580s
  sys	0m0.360s

And let's see what is in the wheelhouse.

.. code::

  [volttron@inamatus volttron]$ ls ~/.cache/pip/wheelhouse
  Smap-2.0.24c780d-py2-none-any.whl
  Twisted-15.0.0-cp27-none-linux_x86_64.whl
  avro-1.7.7-py2-none-any.whl
  configobj-5.0.6-py2-none-any.whl
  ecdsa-0.13-py2.py3-none-any.whl
  gevent-1.0.1-cp27-none-linux_x86_64.whl
  greenlet-0.4.5-cp27-none-linux_x86_64.whl
  monotonic-0.1-py2-none-any.whl
  numpy-1.9.1-cp27-none-linux_x86_64.whl
  pandas-0.15.2-cp27-none-linux_x86_64.whl
  paramiko-1.15.2-py2.py3-none-any.whl
  pycrypto-2.6.1-cp27-none-linux_x86_64.whl
  pymodbus-1.2.0-py2-none-any.whl
  pyserial-2.7-py2-none-any.whl
  python_dateutil-2.4.0-py2.py3-none-any.whl
  pytz-2014.10-py2.py3-none-any.whl
  pyzmq-14.5.0-cp27-none-linux_x86_64.whl
  requests-2.5.3-py2.py3-none-any.whl
  setuptools-12.2-py2.py3-none-any.whl
  simplejson-3.6.5-cp27-none-linux_x86_64.whl
  six-1.9.0-py2.py3-none-any.whl
  wheel-0.24.0-py2.py3-none-any.whl
  zope.interface-4.1.2-cp27-none-linux_x86_64.whl

Now ``bootstrap.py`` can be run without options to complete the bootstrap process, again using the virtual environment Python.

.. code::

  [volttron@inamatus volttron]$ time env/bin/python bootstrap.py
  Installing required packages
  + easy_install BACpypes>=0.10,<0.11
    ...
  + pip install --global-option --quiet --install-option --zmq=bundled --no-deps pyzmq>=14.3,<15
    ...
  + pip install --global-option --quiet --editable ./lib/jsonrpc --editable . --requirement ./requirements.txt
    ...
  Successfully installed Smap-2.0.24c780d avro-1.7.7 configobj-5.0.6 ecdsa-0.13 flexible-jsonrpc
  gevent-1.0.1 greenlet-0.4.5 monotonic-0.1 numpy-1.9.1 pandas-0.15.2 paramiko-1.15.2
  pycrypto-2.6.1 pymodbus-1.2.0 pyserial-2.7 python-dateutil-2.4.0 pytz-2014.10 requests-2.5.3
  simplejson-3.6.5 six-1.9.0 twisted-15.0.0 volttron-2.0 zope.interface-4.1.2

  real  0m11.137s
  user  0m8.930s
  sys   0m0.950s

Installing from wheels completes in only 11 seconds. And if we blow away the environment and bootstrap again, it takes under 15 seconds.

.. code::

  [volttron@inamatus volttron]$ rm -rf env
  [volttron@inamatus volttron]$ time python2.7 bootstrap.py
    ...

  real  0m14.644s
  user  0m10.380s
  sys   0m1.240s

Building a clean environment now occurs in less than 15 seconds instead of the 9 minute baseline. That, my friends, is fast.


Why care?
---------

The average VOLTTRON developer probably won't care or see much benefit from the wheel optimization. The typical developer workflow does not include regularly removing the virtual environment and rebuilding. This is, however, very important for continuous integration (CI). With CI, a build server should check out a fresh copy of the source code, build it in a clean environment, and perform unit tests, notifying offending users when their changes break things. Ideally, notification of breakage should happen as soon as possible. We just shaved nearly nine minutes off the turnaround time.  It also reduces the load on a shared CI build server, which is nice for everyone.


Taking it further
-----------------

Two additional use cases present themselves: offline installs and shared builds.


Offline Installs
++++++++++++++++

Let's say we have a system that is not connected to the Internet and, therefore, cannot download packages from PyPi_ or any other package index. Or perhaps it doesn't have a suitable compiler. Wheels can be built on another *similar*, connected system and transferred by USB drive to the offline system, where they can then be installed. Note that the architecture must be identical and the OS must be very similar between the two systems for this to work.

If the two systems differ too much for a compatible binary build and the offline system has a suitable compiler, then source files can be copied from the pip download cache and transferred from the online system to the offline system for building.


Shared Builds
+++++++++++++

If many developers are working on the same project, why not share the results of a build with the rest of the team? Here are some ideas to make it work:

* Put wheels on a shared network drive
* Run a private package index server (maybe with pypiserver_)
* Expose CI built wheels using Apache, Nginx, or SimpleHTTPServer_

.. _pypiserver: https://pypi.python.org/pypi/pypiserver
.. _SimpleHTTPServer: https://docs.python.org/2.7/library/simplehttpserver.html#module-SimpleHTTPServer


Issues
------

Here are some of the issues/drawbacks to the methods described above and some possible solutions.

* Configuring pip using environment variables

  No worries. Pip uses configuration files too. And a benefit to using them is that it makes all these wheels available to other Python projects you may be working on, and vise versa.

  .. code::

    # /home/volttron/.config/pip/pip.conf
    [global]
    wheel-dir = /home/volttron/.cache/pip/wheelhouse
    find-links = file:///home/volttron/.cache/pip/wheelhouse

  Find more on configuring pip here_.

  .. _here: https://pip.pypa.io/en/latest/user_guide.html#configuration

* pip does not clean the wheelhouse

  This is not a deal-breaker. The wheel directory can just be removed and it will be recreated. Or a script can be used to remove all but the latest versions of packages.

* Requires an additional step or two

  That's the price for speed. But it can be mitigated by writing a script or bash alias to perform the steps.


Conclusion
----------

Here is a quick summary of the build times executed above:

=======================  ======  ======
        Method           Time (minutes)
-----------------------  --------------
Each builds on previous   CPU    Total
=======================  ======  ======
baseline                  8:07    9:02
with download cache       8:05    8:35
ccache, first run         5:09    6:03
ccache, subsequent runs   2:32    3:16
wheel, first run          2:35    3:30
wheel, subsequent runs    0:12    0:15
=======================  ======  ======

Not everyone cares about build times, but for those who do, pre-building Python wheels is a great way to improve install times. At a very minimum, every Python developer installing compiled packages will benefit from using ccache.

The techniques used in this document aren't just for VOLTTRON, either. They are generally useful for all moderately sized Python projects.

If you haven't installed ccache yet, go do it. There is no excuse.

.. vim: ft=rst spell wrap:
