

'''CEA-2045 API Interface:
 To open serial ports and communicate the CEA-2045 appliance
 Currently it supports conversations initiated by UCM only.

'''

import time
import sys
import serial
import initialization_scripts

import hexdump

def msg_decode(msg):
    '''Decode a hex message to dict'''
    # Initialize dictionary
    msg_dict = {
        'msg_type_ms_byte': '',
        'msg_type_ls_byte': '',
        'payload_len': '',
        'opcode1': '',
        'opcode2': '',
        'checksum': '',
        'size' : '',
        }
    time_sleep = 0.0
    # Decode the message and specify waiting time
    if len(msg) >= 4:  # 2 bytes: data-link message
        msg_dict['msg_type_ms_byte'] = msg[0:2]
        msg_dict['msg_type_ls_byte'] = msg[2:4]
        time_sleep = 0.1
    if len(msg) >= 12:  # 6 bytes: message type supported query
        msg_dict['payload_len'] = int(msg[6:8])
        time_sleep = 0.04
    if len(msg) >= 16:  # 8 bytes: application layer message
        msg_dict['opcode1'] = msg[8:10]
        msg_dict['opcode2'] = msg[10:12]
        msg_dict['checksum'] = msg[12:16]
        time_sleep = 0.1
    if len(msg)>=44: #Commodity read's response message
        msg_dict['opcode1'] = msg[8:10]
        msg_dict['opcode2'] = msg[10:12]
        msg_dict['checksum'] = msg[40:44]
        msg_dict['instantenous'] = msg[16:28]
        msg_dict['cumulative']=msg[28:40]

    msg_dict['size'] = len(msg)
    return msg_dict, time_sleep

def switch_query_response(opcode2):
    '''Return query response code mapped to status string'''
    switcher = {
        '00': "Idle Normal",
        '01': "Running Normal",
        '02': "Running Curtailed Grid",
        '03': "Running Heightened Grid",
        '04': "Idle Grid",
        '05': "SGD Error Condition",
        '06': "Idle Heightned",
        '07': "Cycling On",
        '08': "Cycling Off",
        '09': "Variable Following",
        '0a': "Variable Not Following",
        '0b': "Idle Opted Out",
        '0c': "Running Opted Out"
        }
    return switcher.get(opcode2, "Nothing")

## encode a custom message
def encode_checksum(msg):
    '''
        encode a message with checksum and return a hex string
    '''
    check1 = 0xAA
    check2 = 0x00
    length = len(msg)
    msg_dec = 0
    index = 0
    send_str = ""
    while index < length:
        msg_dec = int(msg[index : index + 2], 16)
        index = index + 2
        check1 = (check1 + msg_dec) % 255
        check2 = (check2 + check1) % 255
        send_str = send_str + "\\" + str((hex(msg_dec)))

    msb = 255 - (check1 + check2)%255
    lsb = 255 - (check1 + msb)%255
    send_str = send_str + "\\" + str(hex(msb)) + "\\" + str(hex(lsb))
    print send_str
    return send_str

## Decode checksum
def decode_checksum(msg):
    '''
        decode checksum and Check if the message has been tampered
    '''

    check1 = 0xAA
    check2 = 0x00
    length = len(msg)
    if(length < 16):
        return 0
    else:
        msg_dec = 0
        index = 0
        while index < length:
            msg_dec = int(msg[index :index + 2], 16)
            index = index + 2
            check1 = (check1 + msg_dec) % 255
            check2 = (check2 + check1) % 255
        if check1 == 0x0 and check2 == 0x0:
            return 0
        else:
            return -1


def CEA2045_API(usb_port ="Fake",baud_rate=0):
    ''' Chooses a Fake device or real device based on url'''
    if  usb_port == "Fake" and baud_rate == 0:
        return FakeSerial()
    else :
        return CEA2045Interface(usb_port,baud_rate)



class CEA2045Interface(object):
    '''Base interface to controllers that adhere to the CEA-2045 specification.
    '''
    def __init__(self, usb_port=None, baud_rate=19200, ser=None):
        '''Initialize the interface.
        Args: ser - serial.Serial object.
        If None, create the default using settings made available by volttron
        If None, use the usb_port name and baud_rate and open a serial link
        '''
        if ser is None:
            self.ser = serial.Serial(
                port=usb_port,
                baudrate=baud_rate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            if self.ser.isOpen() == 'False':
                self.ser.open()
            else:
                print 'Serial Port is Open'
        else:
            self.ser = ser

        # Time to sleep after sending a message
        self.default_sleep_time = 0.1
        # Set the messages allowed to be sent
        self.allowed_send_messages = {
            'link_ack': "\x06\x00",
            'link_nak_unsupported_msg_type': "\x15\x06",
            'query': "\x08\x01\x00\x02\x12\x00\xD8\x5F",
            'shed': "\x08\x01\x00\x02\x01\x00\x0C\x3D",
            'emergency': "\x08\x01\x00\x02\x0B\x00\xED\x51",
            'normal': "\x08\x01\x00\x02\x02\x00\x09\x3F",
            'comm_status_good': "\x08\x01\x00\x02\x0E\x01\xE2\x58",
            'query_supported_msg_basic_dr': "\x08\x01\x00\x00\x7E\xCD",
            'query_supported_msg_intermediate_dr': "\x08\x02\x00\x00\x7A\xD0",
            'send_max_payload_length': "\x08\x03\x00\x02\x19\x23\xA9\x7E",
            'customer_override_ack': "\x08\x01\x00\x02\x03\x11\xE3\x52",
            'critical_peak_event': "\x08\x01\x00\x02\x0A\x00\xF0\x4F",
            'load_up': "\x08\x01\x00\x02\x17\x00\xC9\x69",
            'query_supported_msg_data_link': "\x08\x03\x00\x00\x76\xD3",
            'link_nak_checksum_error' : "\x15\x03",
            'link_nak_message_timeout' : "\x15\x05",
            'comm_status_poor' : "\x08\x01\x00\x02\x0E\x02\xE0\x59",
            'comm_status_lost' : "\x08\x01\x00\x02\x0E\x02\xE4\x57",
            'power_level' : "0801000206",
            'query_power' : "\x08\x02\x00\x02\x06\x00\xF6\x4C"

        }
        self.special_sleep_time = {'comm_status_good': 0.04}

    def initialize(self,device_type):
        '''Initialize the device'''
        import initialization_scripts
        if device_type ==  1:
            import initialization_scripts
            initialization_scripts.initialize_type1(self)
        else :
            print "No such device_type found"
        # You can implement other initialization functions based on your
        #  appliance and add it to initialization_scripts.py

    def recv_msg(self):
        '''Receive a message one byte at a time while there are bytes waiting.
        Converts the message to a dict.
        Returns dict of message'''

        msg = ''
        msg_dict = ''
        while self.ser.inWaiting() > 0:
            msg += self.ser.read(1).encode('hex')

        if msg != '':  # Done reading the message
            if decode_checksum(msg) == 0:
                pass
            msg_dict, time_sleep = msg_decode(msg)
            time.sleep(time_sleep)
            return msg_dict

    def set_power_level(self,msg):
        self.power_level = str(msg)

    def send_msg(self, msg_option):
        '''Send one of the hard-coded messages and sleep for message required time

        Args: msg_option - String that must be key in allowed_send_messages
        '''

        if msg_option == 'power_level':
            encoded_message  = encode_checksum((self.allowed_send_messages[msg_option]+self.power_level))
            msg_send = self.allowed_send_messages[msg_option]+self.power_level+encoded_message[28:30]+encoded_message[33:]
            self.ser.write(msg_send.decode('hex'))
        elif msg_option in self.allowed_send_messages:
            self.ser.write(self.allowed_send_messages[msg_option])
        else:
            self.ser.write(msg_option.decode('hex'))
        if msg_option in self.special_sleep_time:
            time.sleep(self.special_sleep_time[msg_option])
        elif msg_option in self.allowed_send_messages:
            time.sleep(self.default_sleep_time)
        # for custom message the time_sleep will be the 'opcode2' filed [10:12]
        else:
            time.sleep(float(msg_option[10:12]))

class FakeSerial(object):
    '''Class that implements the functions used by serial.Serial to run the
    test cases'''
    def __init__(self, read_list=None):
        self.write_list = []
        self.read_list = read_list
        if self.read_list is None:
            self.read_list = []
        self.curr_msg = []


    def initialize(self, device_type):
        '''initialize the API_test device'''
        print "Initializtion called for virtual device."




    def send_msg(self,msg):
        '''Append the message to the write list, update the read list
        '''
        self.read_list = []
        self.write_list.append(msg)
        if msg == 'query':
            self.read_list = []
            self.read_list.append("\x06\x00")
            self.read_list.append(self.status_push)
        elif msg == 'shed':
            self.read_list = []
            self.read_list.append("\x06\x00")
            self.read_list.append("\x08\x01\x00\x02\x03\x01\x04\x42")
            self.status_push = "\x08\x01\x00\x02\x13\x02\xD1\x63"
        elif msg == 'normal':
            self.read_list = []
            self.read_list.append("\x06\x00")
            self.read_list.append("\x08\x01\x00\x02\x03\x01\x04\x42")
            self.status_push = "\x08\x01\x00\x02\x13\x01\xD1\x63"
        elif msg == 'emergency':
            self.read_list = []
            self.read_list.append("\x06\x00")
            self.read_list.append("\x08\x01\x00\x02\x03\x01\x04\x42")
            self.status_push = "\x08\x01\x00\x02\x13\x04\xCD\x65"
        elif msg == 'comm_status_good':
            self.read_list = []
            self.read_list.append("\x06\x00")
            self.read_list.append("\x08\x01\x00\x02\x03\x01\x04\x42")
            self.status_push = "\x08\x01\x00\x02\x13\x04\xCD\x65"
        elif msg == 'link_ack':
            pass
        else:
            # # print "Not a recognized message; Ignoring"
            # self.read_list.append("\x15\x03")
            # self.read_list.append("\x15\x03")
            pass

    def recv_msg(self):
        '''Pop the first item in curr_msg and return it'''
        message = self.read_list.pop(0)
        msg_dict, time_sleep = msg_decode(message.encode('hex'))
        return msg_dict
