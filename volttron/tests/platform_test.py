import unittest
from platform_wrapper import PlatformWrapper

class PlatformTests(unittest.TestCase):
    
    def setUp(self):
        self.platform = PlatformWrapper()
        
    def test_platform_startup(self):
        self.platform.startup_platform("base-platform-test.json")
        self.assertIsNotNone(self.platform.p_process, "Platform process is none")
        self.assertIsNotNone(self.platform.t_process, "Twistd process is none")


    def tearDown(self):
        self.platform.shutdown_platform()

if __name__ == "__main__":
    unittest.main()