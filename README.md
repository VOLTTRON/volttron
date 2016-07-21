![image](docs/source/images/volttron-webimage.jpg)

Distributed Control System Platform.

|Branch|Status|
|:---:|---|
|Master Branch| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=master)|
|3.x| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=3.x)|
|develop| ![image](https://travis-ci.org/VOLTTRON/volttron.svg?branch=develop)|

## Dependencies
A few external dependencies are required to bootstrap the development
environment:
  - Essential build tools (gcc, make, autodev-tools, etc.)
  - Python development files (headers)
  - Openssl.

On **Debian-based systems**,
these can all be installed with the following command:

```sh
  $ sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev
```

> **NOTE:** If you wish to use cryptographic authentication or
  point-to-point encryption, libsodium must also be installed.
  However, libsodium is not currently in the official Ubuntu or Debian
  repositories, so it must be installed manually or from an unofficial
  repository, such as https://launchpad.net/~shnatsel/+archive/dnscrypt.
  The libsodium source code is found at https://github.com/jedisct1/libsodium.

On **Arch Linux**, the following command will install the dependencies:

```sh
  $ sudo pacman -S base-devel python2 openssl libssl-dev libsodium
```

## Installation

To create a development environment,
execute the following in the project root directory:

```sh
  $ python2.7 bootstrap.py
```

That's it! You can now start an interpreter that includes Volttron in the
Python path using `env/bin/python` or run Volttron using `env/bin/volttron`.
The bootstrap script will also create `env/bin/activate` which can be sourced
to setup a developer environment with the appropriate paths set.
It also creates a deactivate function to revert the settings.

```sh
  $ . env/bin/activate
  (volttron)$ echo $PATH
  ... do development work
  (volttron)$ deactivate
  $ echo $PATH
```

To update the scripts after modifying `setup.py` or after a repository update,
use the following command:

```sh
(volttron) user@machine $ python bootstrap.py
```

The bootstrap script creates a virtual Python environment, using virtualenv,
and installs Volttron as an editable (or developer mode) package using pip.

## Testing

VOLTTRON uses py.test as a framework for executing tests.  py.test is not installed
with the distribution by default.  To install py.test and it's dependencies
execute the following:

```
(volttron) user@machine $ python bootstrap.py --testing
```

To run all of the tests in the volttron repository execute the following in the
root directory:

```
(volttron) user@machine $ py.test
```

## Configuration

To add project dependencies, add the dependent package to the
`install_requires` list in `setup.py` and run `env/bin/python bootstrap.py`.
Add agent or other external dependencies to `requirements.txt`.

----

## Open source licensing info
  - [TERMS](TERMS.md)
