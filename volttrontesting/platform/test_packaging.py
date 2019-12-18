# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

"""
unit test cases for packaging.py (volttron-pkg package). This does not yet
cover test cases for restricted code as volttron-restricted is currently
broken. This test class needs to be updated once volttron-restricted in updated
"""
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

import os
import pytest
import stat

from volttron.platform import get_examples
from volttron.platform.packaging import AgentPackageError
from volttron.platform.packaging import (create_package, repackage,
                                         extract_package)


@pytest.fixture(scope="module")
def test_package():
    """
    Fixture to create a test package and test wheel used by this test suite

    :return: (parent directory of test package, distribution name,
    version, name of test package)
    """

    # now change to the newly created tmpdir
    print("cwd {}".format(os.getcwd()))
    cwd = os.getcwd()
    try:
        tmpdir = tempfile.mkdtemp()
        os.chdir(tmpdir)

        # create a test package
        os.mkdir('packagetest')
        with open(os.path.join('packagetest', '__init__.py'), 'w') as f:
            pass
        with open(os.path.join(
                'packagetest', 'packagetest.py'), 'w') as f:
            f.write('''
import sys

if __name__ == '__main__':
sys.stdout.write('Hello World!\n')
''')
        with open(os.path.join('setup.py'), 'w') as f:
            f.write('''
from setuptools import setup

setup(
name = 'distribution_name',
version = '0.1',
packages = ['packagetest'],
zip_safe = False,
)
''')
        p = subprocess.Popen([sys.executable, 'setup.py', 'bdist_wheel'], universal_newlines=True)
        p.wait()
        os.path.join('dist', '-'.join(['distribution_name',
                                               '0.1', 'py3-none-any.whl']))
    finally:
        os.chdir(cwd)
    return tmpdir, 'distribution_name', '0.1', 'packagetest'


@pytest.mark.packaging
def test_create_package_no_id(test_package):
    """
    Test if we can create a wheel file given a valid agent directory.
    Expected result: wheel file with the name
    <distribution_name>-<version>-py3-none-any.whl

    :param test_package: fixture that creates the fake agent directory
    and returns the directory name, distribution name, version of
    the fake/test package, and package name

    """
    print("cwd {}".format(os.getcwd()))
    tmpdir, distribution_name, version, package_name = test_package
    wheel_dir = os.path.join(tmpdir, "wheel_dir")
    result = create_package(tmpdir, wheel_dir)
    assert result == os.path.join(wheel_dir, '-'.join(
        [distribution_name, version, 'py3-none-any.whl']))


@pytest.mark.packaging
def test_create_package_with_id(test_package):
    """
    Test if we can create a wheel file given a agent directory and vip id
    Expected result:

    1. wheel file with the name
       <distribution_name>-<version>-py3-none-any.whl
    2. Wheel file should contains the identity passed in a file called
    'IDENTITY_TEMPLATE' in <distribution_name>-<version>.dist-info folder

    :param test_package: fixture that creates the fake agent directory
    and returns the directory name, distribution name, version of
    the fake/test package, and package name

    """
    tmpdir, distribution_name, version, package_name = test_package
    wheel_dir = os.path.join(tmpdir, "wheel_dir")
    result = create_package(tmpdir, wheel_dir, "test_vip_id")
    assert result == os.path.join(wheel_dir, '-'.join(
        [distribution_name, version, 'py3-none-any.whl']))

    extract_dir = tempfile.mkdtemp()
    result2 = extract_package(result, extract_dir)
    dist_info_dir = os.path.join(result2,
                                 distribution_name + "-" + version +
                                 ".dist-info")
    files = os.listdir(dist_info_dir)
    assert 'IDENTITY_TEMPLATE' in files
    with open(os.path.join(dist_info_dir, 'IDENTITY_TEMPLATE'), 'r') as f:
        data = f.read().replace('\n', '')
        assert data == "test_vip_id"


@pytest.mark.packaging
def test_create_package_invalid_input():
    """
    Test error handling in create_package when invalid package directory
    is passed

    """

    wheel_dir = os.path.join(tempfile.mkdtemp(), "wheel_dir")
    try:
        create_package("/abc/def/ghijkl", wheel_dir)
        pytest.fail("Expecting AgentPackageError got none")
    except AgentPackageError as e:
        assert e.args[0] == "Invalid agent package directory specified"

    try:
        create_package(tempfile.mkdtemp(), wheel_dir)
        pytest.fail("Expecting NotImplementedError got none")
    except NotImplementedError:
        pass


@pytest.mark.packaging
def test_repackage_output_to_cwd(volttron_instance):
    """
    Test if we can create a wheel file given an installed agent directory.
    Test without any explicit destination directory for the wheel file.
    Wheel file should be created in current working directory

    :param volttron_instance: platform wrapper used to install a test
                              agent and test installation of wheel file
                              generated by repackage

    """
    dest_dir = None
    cwd = os.getcwd()
    try:
        dest_dir = tempfile.mkdtemp()
        os.chdir(dest_dir)
        agent_uuid = volttron_instance.install_agent(
            agent_dir=os.path.join(cwd, get_examples("ListenerAgent")))
        agent_dir = os.path.join(volttron_instance.volttron_home, 'agents',
            agent_uuid, 'listeneragent-3.3')
        print(agent_dir)
        wheel_name = repackage(agent_dir)
        assert wheel_name == 'listeneragent-3.3-py3-none-any.whl'

        wheel = os.path.join(dest_dir, wheel_name)
        # Check wheel exists and it can be used to install the agent again
        assert os.path.isfile(wheel)
        volttron_instance.install_agent(agent_wheel=wheel)
    finally:
        os.chdir(cwd)
        if dest_dir:
            shutil.rmtree(dest_dir)


@pytest.mark.packaging
def test_repackage_valid_dest_dir(volttron_instance):
    """
    Test if we can create a wheel file given an installed agent directory.
    Test with valid destination directory

    :param volttron_instance: platform wrapper used to install a test
                              agent and test installation of wheel file
                              generated by repackage

    """
    dest_dir = None
    try:
        dest_dir = tempfile.mkdtemp()
        agent_uuid = volttron_instance.install_agent(
            agent_dir=os.path.join(get_examples("ListenerAgent")))
        agent_dir = os.path.join(volttron_instance.volttron_home, 'agents',
            agent_uuid, 'listeneragent-3.3')
        print(agent_dir)
        wheel_path = repackage(agent_dir, dest=dest_dir)
        expected_wheel = os.path.join(dest_dir,
                                      'listeneragent-3.3-py3-none-any.whl')
        assert wheel_path == expected_wheel
        # Check wheel exists and it can be used to install the agent again
        assert os.path.isfile(wheel_path)
        volttron_instance.install_agent(agent_wheel=wheel_path)
    finally:
        if dest_dir:
            shutil.rmtree(dest_dir)


@pytest.mark.packaging
def test_repackage_new_dest_dir(volttron_instance):
    """
    Test if we can create a wheel file given an installed agent directory.
    Test with valid destination directory

    :param volttron_instance: platform wrapper used to install a test
                              agent and test installation of wheel file
                              generated by repackage

    """
    dest_dir = None
    try:
        dest_dir = tempfile.mkdtemp()
        dest_dir = os.path.join(dest_dir, "subdir")
        print("cwd {}".format(os.getcwd()))

        agent_uuid = volttron_instance.install_agent(
            agent_dir=os.path.join(get_examples("ListenerAgent")))
        agent_dir = os.path.join(volttron_instance.volttron_home, 'agents',
            agent_uuid, 'listeneragent-3.3')
        print(agent_dir)
        wheel_path = repackage(agent_dir, dest=dest_dir)
        expeceted_wheel = os.path.join(
            dest_dir, 'listeneragent-3.3-py3-none-any.whl')
        assert wheel_path == expeceted_wheel
        # Check wheel exists and it can be used to install the agent again
        assert os.path.isfile(wheel_path)
        volttron_instance.install_agent(agent_wheel=wheel_path)
    finally:
        if dest_dir:
            shutil.rmtree(dest_dir)


@pytest.mark.packaging
def test_repackage_invalid_dest_dir(volttron_instance):
    """
    Test if we can create a wheel file given an installed agent agent_dir.
    Test with invalid destination agent_dir.
    Expected result - AgentPackageError

    :param volttron_instance: platform wrapper used to install a test
                              agent and test installation of wheel file
                              generated by repackage

    """
    dest_dir = "/abcdef/ghijkl"
    try:
        agent_uuid = volttron_instance.install_agent(
            agent_dir=get_examples("ListenerAgent"))
        agent_dir = os.path.join(volttron_instance.volttron_home, 'agents',
                                 agent_uuid, 'listeneragent-3.3')
        repackage(agent_dir, dest=dest_dir)
        pytest.fail("Expecting AgentPackageError but code completed "
                    "successfully")
    except AgentPackageError as a:
        assert a.args[0].find("Unable to create destination directory "
                              "{}".format(dest_dir)) != -1
    try:

        dest_dir = tempfile.mkdtemp()
        os.chmod(dest_dir, stat.S_IREAD)
        agent_uuid = volttron_instance.install_agent(
            agent_dir=get_examples("ListenerAgent"))
        agent_dir = os.path.join(volttron_instance.volttron_home, 'agents',
                                 agent_uuid, 'listeneragent-3.3')
        repackage(agent_dir, dest=dest_dir)
        pytest.fail("Expecting AgentPackageError but code completed "
                    "successfully")
    except Exception as a:
        assert str(a).find("Permission denied") != -1


@pytest.mark.packaging
def test_repackage_invalid_agent_dir():
    """
    Test if we can create a wheel file given an installed agent temp_dir.
    Test with invalid agent temp_dir. Expected result - AgentPackageError

    """
    try:
        repackage("/tmp/abcdefghijklmnopqrstuvwxyz")
        pytest.fail("Expecting AgentPackageError but code completed "
                    "successfully")
    except AgentPackageError as a:
        assert a.args[0] == "Agent directory " \
                            "/tmp/abcdefghijklmnopqrstuvwxyz " \
                            "does not exist"
    temp_dir = ""
    try:
        temp_dir = tempfile.mkdtemp()
        repackage(temp_dir)
        pytest.fail("Expecting AgentPackageError but code completed "
                    "successfully")
    except AgentPackageError as a:
        assert a.args[0] == 'directory does not contain a valid agent ' \
                            'package: {}'.format(temp_dir)
    finally:
        if temp_dir:
            os.rmdir(temp_dir)


@pytest.mark.packaging
def test_extract_valid_wheel_and_dir(test_package):
    """
    Test if we can extract a wheel file, a specific install directory.


    :param test_package: fixture that creates the fake agent directory
                         and returns the directory name, distribution
                         name,  version of the fake/test package,
                         and package name

    """
    install_dir = ""
    try:
        tmpdir, distribution_name, version, package = test_package

        wheel_name = '-'.join(
            [distribution_name, version, 'py3-none-any.whl'])
        wheel_file = os.path.join(tmpdir, 'dist', wheel_name)
        install_dir = tempfile.mkdtemp()

        destination = extract_package(wheel_file, install_dir,
                                      include_uuid=False,
                                      specific_uuid=None)

        print("destination {}".format(destination))
        name_version = distribution_name + "-" + version
        assert destination == os.path.join(install_dir, name_version)
        assert Counter(os.listdir(destination)) == Counter(
            [name_version + '.dist-info', package])

        dist = os.path.join(destination, name_version + '.dist-info')
        assert Counter(os.listdir(dist)) == Counter(
            ['DESCRIPTION.rst', 'METADATA', 'metadata.json', 'RECORD',
             'top_level.txt', 'WHEEL'])
    finally:
        if install_dir:
            shutil.rmtree(install_dir)


@pytest.mark.packaging
def test_extract_include_uuid(test_package):
    """
    Test if we can extract a wheel file, a specific install directory.
    Specify include_uuid as True and verify that the extraction happens
    within given install_dir/uuid directory

    :param test_package: fixture that creates the fake agent directory
                         and returns the directory name, distribution
                         name,  version of the fake/test package,
                         and package name

    """
    install_dir = ""
    try:
        tmpdir, distribution_name, version, package = test_package

        wheel_name = '-'.join(
            [distribution_name, version, 'py3-none-any.whl'])
        wheel_file = os.path.join(tmpdir, 'dist', wheel_name)
        install_dir = tempfile.mkdtemp()

        destination = extract_package(wheel_file, install_dir,
                                      include_uuid=True,
                                      specific_uuid=None)

        print("destination {}".format(destination))
        name_version = distribution_name + "-" + version
        assert os.path.basename(destination) == name_version
        assert os.path.dirname(os.path.dirname(destination)) == install_dir

        assert Counter(os.listdir(destination)) == Counter(
            [name_version + '.dist-info', package])

        dist = os.path.join(destination, name_version + '.dist-info')
        assert Counter(os.listdir(dist)) == Counter(
            ['DESCRIPTION.rst', 'METADATA', 'metadata.json', 'RECORD',
             'top_level.txt', 'WHEEL'])
    finally:
        if install_dir:
            shutil.rmtree(install_dir)


@pytest.mark.packaging
def test_extract_specific_uuid(test_package):
    """
    Test if we can extract a wheel file, a specific install directory and
    a specific uuid

    :param test_package: fixture that creates the fake agent directory
                         and returns the directory name, distribution
                         name,  version of the fake/test package,
                         and package name

    """
    install_dir = ""
    try:
        tmpdir, distribution_name, version, package = test_package

        wheel_name = '-'.join(
            [distribution_name, version, 'py3-none-any.whl'])
        wheel_file = os.path.join(tmpdir, 'dist', wheel_name)
        install_dir = tempfile.mkdtemp()

        destination = extract_package(wheel_file, install_dir,
                                      include_uuid=True,
                                      specific_uuid="123456789")

        print("destination {}".format(destination))
        name_version = distribution_name + "-" + version
        assert os.path.basename(destination) == name_version
        assert os.path.dirname(destination) == os.path.join(install_dir,
                                                            "123456789")

        assert Counter(os.listdir(destination)) == Counter(
            [name_version + '.dist-info', package])

        dist = os.path.join(destination, name_version + '.dist-info')
        assert Counter(os.listdir(dist)) == Counter(
            ['DESCRIPTION.rst', 'METADATA', 'metadata.json', 'RECORD',
             'top_level.txt', 'WHEEL'])
    finally:
        if install_dir:
            shutil.rmtree(install_dir)


@pytest.mark.packaging
def test_extract_invalid_wheel():
    """
    Test extract_package with invalid wheel file name.
    """
    install_dir = ""
    f = None
    try:
        f = tempfile.NamedTemporaryFile(suffix=".whl")
        install_dir = tempfile.mkdtemp()
        extract_package(f.name, install_dir, include_uuid=True,
                        specific_uuid="123456789")

    except Exception as e:
        assert e.args[0] == "Bad filename '{}'".format(f.name)
    finally:
        if install_dir:
            shutil.rmtree(install_dir)


@pytest.mark.packaging
def test_extract_invalid_install_dir(test_package):
    """
     Test extract_package with invalid install directory

    :param test_package: fixture that creates the fake agent directory
                         and returns the directory name, distribution
                         name,  version of the fake/test package,
                         and package name

    """
    install_dir = ""
    try:
        tmpdir, distribution_name, version, package = test_package

        wheel_name = '-'.join(
            [distribution_name, version, 'py3-none-any.whl'])
        wheel_file = os.path.join(tmpdir, 'dist', wheel_name)
        install_dir = tempfile.mkdtemp()
        os.chmod(install_dir, stat.S_IREAD)
        extract_package(wheel_file, install_dir, include_uuid=True,
                        specific_uuid="123456789")

    except Exception as e:
        print(e)
        assert str(e).find("Permission denied") != -1
    finally:
        if install_dir:
            shutil.rmtree(install_dir)


@pytest.mark.packaging
def test_extract_new_install_dir(test_package):
    """
     Test extract_package with invalid install directory

    :param test_package: fixture that creates the fake agent directory
                         and returns the directory name, distribution
                         name,  version of the fake/test package,
                         and package name

    """
    install_dir = ""

    try:
        tmpdir, distribution_name, version, package = test_package

        wheel_name = '-'.join(
            [distribution_name, version, 'py3-none-any.whl'])
        wheel_file = os.path.join(tmpdir, 'dist', wheel_name)
        install_dir = tempfile.mkdtemp()
        install_dir = os.path.join(install_dir, 'newdir')

        destination = extract_package(wheel_file, install_dir,
                                      include_uuid=True,
                                      specific_uuid="123456789")
        print("destination {}".format(destination))
        name_version = distribution_name + "-" + version
        assert os.path.basename(destination) == name_version
        assert os.path.dirname(destination) == os.path.join(install_dir,
                                                            "123456789")

        assert Counter(os.listdir(destination)) == Counter(
            [name_version + '.dist-info', package])

        dist = os.path.join(destination, name_version + '.dist-info')
        assert Counter(os.listdir(dist)) == Counter(
            ['DESCRIPTION.rst', 'METADATA', 'metadata.json', 'RECORD',
             'top_level.txt', 'WHEEL'])

    finally:
        if install_dir:
            shutil.rmtree(install_dir)
