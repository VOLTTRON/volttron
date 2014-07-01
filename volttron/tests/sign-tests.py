'''
Created on Jun 30, 2014

@author: craig
'''
import unittest
import os
import shutil

from OpenSSL import crypto, SSL
from volttron.restricted.key import create_self_signed_cert
from volttron.restricted.auth import (sign_wheel, 
                                      verify_wheel_signature)
from os.path import exists, join
from wheel.install import WheelFile

KEY_DIR = '/tmp/test_auth_key'
KEY_ROOT = 'test'
PRIVATE_KEY_NAME = KEY_ROOT+'.key'
PUBLIC_KEY_NAME = KEY_ROOT+'.crt'

class TestAuth(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(KEY_DIR):
            os.makedirs(KEY_DIR)
            assert(create_self_signed_cert(KEY_DIR, KEY_ROOT) == True)
    
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(KEY_DIR):
            shutil.rmtree(KEY_DIR)

    def test_self_signed_cert_are_created(self):
        self.assertTrue(exists(join(KEY_DIR, PRIVATE_KEY_NAME)))
        self.assertTrue(exists(join(KEY_DIR, PUBLIC_KEY_NAME)))

    def test_can_sign_wheel(self):
        test_wheel = 'listeneragent-0.1-py2-none-any.whl'
        wheel_copy = join('/tmp', test_wheel)
        try:
            if exists(wheel_copy):
                os.remove(wheel_copy)

            shutil.copy(join('fixtures', test_wheel), wheel_copy)
            self.assertTrue(exists(wheel_copy))
            self.assertTrue(sign_wheel(wheel_copy, join(KEY_DIR, PRIVATE_KEY_NAME)))
            self.assertTrue(verify_wheel_signature(wheel_copy, join(KEY_DIR, PUBLIC_KEY_NAME)))
        finally:
            if exists(wheel_copy):
                os.remove(wheel_copy)
        
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()