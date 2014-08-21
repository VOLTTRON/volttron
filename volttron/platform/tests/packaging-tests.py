import unittest
import os
import shutil
import sys
import tempfile
import uuid
import subprocess

from collections import namedtuple
from wheel.install import (WheelFile, VerifyingZipFile)

from volttron.platform.packaging import (create_package,
                                         extract_package)

from volttron.platform.packaging import AgentPackageError

try:
    from volttron.restricted import (auth, certs)
except:
    auth = None
    certs = None



# this is located in the tests/fixtures directory.
AGENT_TESTCASE1_NAME = 'test-agent-package'


class TestPackaging(unittest.TestCase):

    def get_agent_fixture(self, agent_name):
        return os.path.join(self.fixtureDir, agent_name)

    def setUp(self):
        self.fixtureDir = os.path.join(os.path.dirname(__file__), "fixtures")

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
name = 'packagetest',
version = '0.1',
packages = ['packagetest'],
zip_safe = False,
)
''')
        p = subprocess.Popen([sys.executable, 'setup.py', 'bdist_wheel'])
        p.wait()
        self.wheel = os.path.join('dist', 'packagetest-0.1-py2-none-any.whl')

    def tearDown(self):
        if self.delete_temp:
            shutil.rmtree(self.tmpdir, True)
        else:
            print('leaving tempdir: {}'.format(self.tmpdir))

    if auth != None:
        def test_can_sign_as_creator(self):



            print('successful!')

    def test_can_extract_package(self):
        wheelhouse = os.path.join(self.tmpdir, 'extract_package')
        expected_install_at = os.path.join(wheelhouse, 'listeneragent-0.1')
        test_wheel_name = 'listeneragent-0.1-py2-none-any.whl'
        wheel_file = os.path.join(self.fixtureDir, test_wheel_name)

        installed_at = extract_package(wheel_file, wheelhouse)

        try:
            self.assertIsNotNone(installed_at)
            self.assertTrue(os.path.isdir(installed_at))
            self.assertEqual(expected_install_at, installed_at)

            # use the wheel file to verify that everything was extracted
            # properly.
            wf = WheelFile(wheel_file)
            self.assertIsNone(wf.verify())

            for o in wf.zipfile.infolist():
                self.assertTrue(
                    os.path.exists(os.path.join(expected_install_at, o.filename)))

            wf.zipfile.close()
        finally:
            shutil.rmtree(installed_at)
            shutil.rmtree(wheelhouse)

    def test_can_create_package(self):
        '''
        Tests that a proper wheel package is created from the create_package method of
        the AgentPackage class.
        '''
        agent_name = AGENT_TESTCASE1_NAME
        package_tmp_dir = os.path.join(self.tmpdir, 'create_package')
        expected_package_name = 'listeneragent-0.1-py2-none-any.whl'

        returned_package = create_package(
            self.get_agent_fixture(agent_name), package_tmp_dir)

        self.assertIsNotNone(
            returned_package, "Invalid package name {}".format(returned_package))
        self.assertTrue(os.path.exists(returned_package))
        self.assertEqual(
            expected_package_name, os.path.basename(returned_package))
        # Wheel is in the correct location.
        self.assertEqual(
            os.path.join(package_tmp_dir, expected_package_name), returned_package)
        self.assertTrue(os.path.exists(returned_package))

        try:
            wf = WheelFile(returned_package)
            # sets up the expected hashes for all of the wheel directory.
            self.assertIsNone(wf.verify())

            # Reading the files
            # if the hash doesn't match it will throw an exception.
            for o in wf.zipfile.infolist():
                wf.zipfile.open(o).read()

            wf.zipfile.close()
        finally:
            shutil.rmtree(package_tmp_dir)

    def test_raises_error_if_agent_dir_not_exists(self):
        '''
        This test passes under the following conditions:
            1. An AgentPackageError is thrown if the passed agent directory
               doesen't exists.
        '''
        #
        fake_agent = package_tmp_dir = os.path.join(self.tmpdir, 'fake')
        if os.path.exists(fake_agent):
            shutil.rmtree(fake_agent, True)

        self.assertRaises(
            AgentPackageError, lambda: create_package(fake_agent))
