# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

"""
unit test cases for packaging.py (volttron-pkg package)
"""
import tempfile
import subprocess
import zipfile
import pytest
import os
import sys
from wheel.install import (WheelFile, VerifyingZipFile)

from volttron.platform.packaging import (create_package,
                                         extract_package)

from volttron.platform.packaging import AgentPackageError

try:
    from volttron.restricted import (auth, certs)
except ImportError:
    auth = None
    certs = None

class TestVolttronPackage:

    @pytest.fixture(scope="module")
    def test_package(self):
        print "*****In setup****"
        #self.fixtureDir = os.path.join(os.path.dirname(__file__), "fixtures")

        # now change to the newly created tmpdir
        self.tmpdir = tempfile.mkdtemp()
        self.delete_temp = True
        os.chdir(self.tmpdir)
        # only do the certs stuf if the restricted are available.
        if certs:
            self.certificate_dir = os.path.join(self.tmpdir, 'certs')
            self.certs_dir = os.path.join(self.tmpdir, 'certs/certs')
            self.private_dir = os.path.join(self.tmpdir, 'certs/private')

            os.makedirs(self.certs_dir)
            os.makedirs(self.private_dir)

            assert(os.path.isdir(self.certificate_dir))
            assert(os.path.isdir(self.certs_dir))
            assert(os.path.isdir(self.private_dir))

            self.admin_cert_name = 'admin'
            self.creator_cert_name = 'creator'
            self.initiator_cert_name = 'initiator'

            admin = {'C': 'US', 'CN': self.admin_cert_name}
            creator = {'C': 'US', 'CN': self.creator_cert_name}
            initiator = {'C': 'US', 'CN': self.initiator_cert_name}

            self.certsobj = certs.Certs(self.certificate_dir)
            self.certsobj.create_root_ca()
            self.certsobj.create_ca_signed_cert(self.admin_cert_name, **admin)
            self.certsobj.create_ca_signed_cert(self.creator_cert_name, **creator)
            self.certsobj.create_ca_signed_cert(self.initiator_cert_name, **initiator)

            from os.path import join
            assert(os.path.isfile(join(self.certs_dir,
                                       self.admin_cert_name+".crt")))
            assert(os.path.isfile(join(self.private_dir,
                                       self.admin_cert_name+".pem")))

            assert(os.path.isfile(join(self.certs_dir,
                                       self.creator_cert_name+".crt")))
            assert(os.path.isfile(join(self.private_dir,
                                       self.creator_cert_name+".pem")))

            assert(os.path.isfile(join(self.certs_dir,
                                       self.initiator_cert_name+".crt")))
            assert(os.path.isfile(join(self.private_dir,
                                       self.initiator_cert_name+".pem")))


        #create a test package
        os.mkdir('packagetest')
        with open(os.path.join('packagetest', '__init__.py'), 'w') as file:
            pass
        with open(os.path.join('packagetest', 'packagetest.py'), 'w') as file:
            file.write('''
import sys

if __name__ == '__main__':
    sys.stdout.write('Hello World!\n')
''')
        with open(os.path.join('setup.py'), 'w') as file:
            file.write('''
from setuptools import setup

setup(
name = 'distribution_name',
version = '0.1',
packages = ['packagetest'],
zip_safe = False,
)
''')
        return self.tmpdir, 'distribution_name', '0.1'
        # p = subprocess.Popen([sys.executable, 'setup.py', 'bdist_wheel'])
        # p.wait()
        # self.wheel = os.path.join('dist', 'packagetest-0.1-py2-none-any.whl')

    def test_create_package_no_id(self, test_package):
        """
        Test if we can create a wheel file given a agent directory
        :param setup: fixture that creates the fake agent packaged
        :return:
        """
        tmpdir, distribution_name, version = test_package
        wheel_dir = os.path.join(tmpdir, "wheel_dir")
        result = create_package(tmpdir, wheel_dir)
        assert result == os.path.join(wheel_dir, '-'.join([
            distribution_name, version, 'py2-none-any.whl']))

    def test_create_package_with_id(self, test_package):
        """
        Test if we can create a wheel file given a agent directory
        :param setup: fixture that creates the fake agent packaged
        :return:
        """
        tmpdir, distribution_name, version = test_package
        wheel_dir = os.path.join(tmpdir, "wheel_dir")
        result = create_package(tmpdir, wheel_dir, "test_vip_id")
        assert result == os.path.join(wheel_dir, '-'.join([
            distribution_name, version, 'py2-none-any.whl']))

        extract_dir = tempfile.mkdtemp()
        result2 = extract_package(result, extract_dir)
        dist_info_dir = os.path.join(result2,
                            distribution_name + "-" + version + ".dist-info")
        files = os.listdir(dist_info_dir)
        assert 'IDENTITY_TEMPLATE' in files
        with open(os.path.join(dist_info_dir,'IDENTITY_TEMPLATE'), 'r') as f:
            data = f.read().replace('\n', '')
            assert data == "test_vip_id"

    @pytest.mark.dev
    def test_create_package_invalid_input(self):
        """
        Test if we can create a wheel file given a agent directory
        :param setup: fixture that creates the fake agent packaged
        :return:
        """

        wheel_dir = os.path.join(tempfile.mkdtemp(), "wheel_dir")
        try:
            create_package("/abc/def/ghijkl", wheel_dir)
            pytest.fail("Expecting AgentPackageError got none")
        except AgentPackageError as e:
            assert e.message == "Invalid agent package directory specified"

        try:
            create_package(tempfile.mkdtemp(), wheel_dir)
            pytest.fail("Expecting NotImplementedError got none")
        except NotImplementedError:
            pass




