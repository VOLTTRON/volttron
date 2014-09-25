import unittest
from base import BasePlatformTest

class PlatformTests(BasePlatformTest):
    
    def setUp(self):
        #Config file is relative to root of project
        super(PlatformTests, self).setUp()
        self.startup_platform("base-platform-test.json")
    
    def test_platform_startup(self):
        self.assertIsNotNone(self.p_process, "Platform process is none")
        self.assertIsNotNone(self.t_process, "Twistd process is none")


    def tearDown(self):
        super(PlatformTests, self).tearDown()
 

if __name__ == "__main__":
    unittest.main()