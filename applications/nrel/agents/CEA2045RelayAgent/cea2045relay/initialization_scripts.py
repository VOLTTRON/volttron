
def initialize_type1(self):
    print "Initialize device type 1"
    self.send_msg('comm_status_good')
    print "G --- comm_status_good --->> D"
    self.send_msg('comm_status_good')
    self.recv_msg()
    self.recv_msg()
    self.send_msg('link_ack')
    print "G ----ACK---->>D"
    print " G waiting for message form D"
    self.ser.flushInput()
    self.ser.flushOutput()
    good = 0
    init_setup = 0
    while(init_setup < 2):
        msg3 = ''
        while(msg3 == '' or msg3 == None):
            msg3 = self.recv_msg()
        print "G <<------Message----D"
        if(msg3['size'] == 16):
            if((msg3['msg_type_ms_byte']== '08') and (msg3['msg_type_ls_byte'] == '03') and(msg3['opcode1'] == '18') and (msg3['opcode2'] == '00') ):
                print "G <<----Payload length query----D"
                self.send_msg('link_ack')
                print "G -----ACK----->>D "
                self.send_msg('send_max_payload_length')
                print "G -----Payload length----->>D "
                msg4 = ''
                while(msg4 == '' or msg4 == None ):
                    msg4 = self.recv_msg()
                print "G <<-----ACK----- D"
                init_setup = init_setup + 1
            elif((msg3['msg_type_ms_byte']== '08') and (msg3['msg_type_ls_byte'] == '02') and(msg3['opcode1'] == '01') and (msg3['opcode2'] == '01') ):
                print "G <<----Request Device Info----D"
                self.send_msg('link_nak_unsupported_msg_type')
                print "G -----NAK----->>D "
            elif((msg3['msg_type_ms_byte']== '08') and (msg3['msg_type_ls_byte'] == '01') and(msg3['opcode1'] == '11')  ):
                print "G <<----Customer Override??----D"
                self.send_msg('link_ack')
                print "G -----ACK----->>D "
                self.send_msg('send_customer_override_status')
                print "G -----Override status----->>D "
                msg4 = ''
                good =0
                while (good == 0):
                    msg1 = ''
                    while(msg1 == ''  and msg1 == None):
                        msg1 = self.recv_msg()
                    if(msg1['size'] == '4'):
                        good = 1
                        break;
                print "G <<-----ACK----- D"
            else:
                print "G <<----Unsupported Message----D"
        elif(msg3['size'] == 12):
            if((msg3['msg_type_ms_byte']== '08') and (msg3['msg_type_ls_byte'] == '03') ):
                print "G <<----Message type support 3?----D"
                self.send_msg('link_ack')
                print "G -----ACK----->>D "
                init_setup = init_setup +1
            elif((msg3['msg_type_ms_byte']== '08') and (msg3['msg_type_ls_byte'] == '02') ):
                print "G <<----Message type support 2?----D"
                self.send_msg('link_nak_unsupported_msg_type')
                print "G -----NAK----->>D "
                init_setup = init_setup +1
            elif((msg3['msg_type_ms_byte']== '08') and (msg3['msg_type_ls_byte'] == '01') ):
                print "G <<----Message type support 1?----D"
                self.send_msg('link_ack')
                print "G -----ACK----->>D "
                init_setup = init_setup +1
            else :
                print "G <<----Message type support X?----D   NO!"
        else :
            print "ignoring message"
    print "Initialization complete"
    return 0
