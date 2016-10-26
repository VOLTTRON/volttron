

import unittest
import CEA_2045

cea =  CEA_2045.CEA2045_API("Fake",0)
#cea =  CEA_2045.CEA2045_API("/dev/cu.usbserial-A603Y394",19200)
cea.initialize(1)

class CEA2045TestCase(unittest.TestCase):

    def test_normal(self):
        '''Test normal run'''
        return_query = {}
        cea.send_msg('normal')
        cea.recv_msg()
        cea.recv_msg()
        cea.send_msg('link_ack')
        cea.send_msg('query')
        cea.recv_msg()
        return_query = cea.recv_msg()
        cea.send_msg('link_ack')
        self.assertEqual(CEA_2045.switch_query_response(return_query['opcode2']), "Running Normal")

    def test_emergency(self):
        '''Test emergency command'''
        return_query = {}
        cea.send_msg('emergency')
        cea.recv_msg()
        cea.recv_msg()
        cea.send_msg('link_ack')
        cea.send_msg('query')
        cea.recv_msg()
        return_query = cea.recv_msg()
        cea.send_msg('link_ack')
        self.assertEqual(CEA_2045.switch_query_response(return_query['opcode2']), "Idle Grid")

    def test_shed(self):
        '''Test shed command'''
        return_query = {}
        cea.send_msg('shed')
        cea.recv_msg()
        cea.recv_msg()
        cea.send_msg('link_ack')
        cea.send_msg('query')
        cea.recv_msg()
        return_query = cea.recv_msg()
        cea.send_msg('link_ack')
        self.assertEqual(CEA_2045.switch_query_response(return_query['opcode2']), "Running Curtailed Grid")
