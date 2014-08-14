import unittest
from base_platform_test import BasePlatformTest

class PlatformTests(BasePlatformTest):
    
    def setUp(self):
        pass
    
    def test_platform_startup(self):
        self.assertIsNotNone(self.p_process, "Platform process is none")
        self.assertIsNotNone(self.t_process, "Twistd process is none")


    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()