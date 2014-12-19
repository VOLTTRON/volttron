import os
import sys
import unittest

from os.path import dirname

from platform_wrapper import PlatformWrapper

_VOLTRON = dirname(dirname(dirname(os.path.join(os.path.realpath(__file__)))))

class PlatformTests(unittest.TestCase):

    def setUp(self):
        print("V: ",_VOLTRON)
        self.platform = PlatformWrapper()

    def test_platform_startup(self):
        self.platform.startup_platform(
                    os.path.join(_VOLTRON, "base-platform-test.json"),
                    use_twistd=True)
        self.assertIsNotNone(self.platform.p_process, "Platform process is none")
        self.assertIsNotNone(self.platform.t_process, "Twistd process is none")

    def test_platform_startup_no_twistd(self):
        self.platform.startup_platform(
                    os.path.join(_VOLTRON, "base-platform-test.json"))
        self.assertIsNotNone(self.platform.p_process, "Platform process is none")



    def tearDown(self):
        self.platform.shutdown_platform()

if __name__ == "__main__":
    unittest.main()