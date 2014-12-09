import sys
import time
import operator
import logging

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod, topics
import json

import volttron.platform.modbus.TCPModbusClient as TCPModbusClient

DENT_ADDRESS = '8.8.8.8'
DENT_METADATA = """Type: Dent Powerscout3,
                Address: %s,
                Location: ,
                City: """ % DENT_ADDRESS

utils.setup_logging()
_log = logging.getLogger(__name__)

def e_m(val):
    """energy multiplier"""
    if val == 5: return 10
    elif val >= 6: return 100
    else: return None

def e_d(val):
    """energy divisor"""
    if val == 0: return 10000
    elif val == 1: return 1000
    elif val == 2: return 100
    elif val == 3: return 10
    else: return None

def c_d(val):
    """current divisor"""
    if val == 0: return 100
    elif val >=1 and val <= 3: return 10
    else: return None

def v_d(val):
    """voltage divisor"""
    if val >= 0 and val <= 3: return 10
    else: return None


class DentAgent(PublishMixin, BaseAgent):

      def __init__(self, config_path, **kwargs):
         super(DentAgent, self).__init__(**kwargs)
         self.config = utils.load_config(config_path)

      def setup(self):
          _log.info(self.config['message'])
          self._agent_id = self.config['agentid']
          super(DentAgent, self).setup()
          self.register()

          # hostname, port tuple
          self.serverloc = [DENT_ADDRESS, 4660]
          # base modbus address
          self.base_addr = 1
          # min time between device reads
          self.limit = 1.5
          # how often to take a new reading
          # self.rate = 20

          # self.scale_register = 4602 # scale register for Dent3
          self.scale_register = 4601
          self.scalar = None
          self.last_read = None
          self.elt_scales = map(lambda x: ('elt-' + x, None),
                                ['A'])

          for i in range(0, len(self.elt_scales)):
            
              for attempt in xrange(0, 5):
                  try:
                      scale = self.read_scale(self.base_addr + i)
                  except IOError as (errno, strerror):
                      print "I/O error({0}): {1}\n".format(errno, strerror)
                      scale = None
                  if scale != None: break
              if scale == None:
                 raise core.SmapException("Could not read scale from dent: cannot proceed (%s)" %
                                          (str(self.serverloc)))
              self.elt_scales[i] = self.elt_scales[i][0], scale
          
      def register(self):
          headers = {'requesterID' : self._agent_id, "From" : self._agent_id}
          msg = {"agents_to_register" : {self._agent_id : DENT_METADATA} }
          self.publish_json("registration/register", headers, msg)

      def read_scale(self, modbus_addr):
          """Read the scale register on a dent"""
          self.modbus_addr = modbus_addr
          response = self.dev_read(self.scale_register, 3)
          data = [(TCPModbusClient.get_val(response.modbus_reg_val, i) & 0xffff)
                  for i in range(0, response.modbus_val_bytes / 2)]

          if len(data) != 3:
             return None

          # return the scaling indicator expressed by the dent
          return data[0]
      
      def to_word(self, seg):
          return seg[0] | (seg[1] << 16)

      def dev_sleep(self):
          now = time.time()
          if not self.last_read or now - self.last_read > self.limit:
             self.last_read = now
          else:
             time.sleep(self.limit - now + self.last_read)
             self.last_read = time.time()
                
      def dev_read(self, *args):
          try:
              self.dev_sleep()
              return TCPModbusClient.dev_read(self.serverloc[0], self.serverloc[1],self.modbus_addr,*args)
          except:
              return None

      def dev_write(self, *args):
          try:
              self.dev_sleep()
              return TCPModbusClient.dev_write(self.serverloc[0], self.serverloc[1],self.modbus_addr,*args)
          except:
              return None

      @periodic(30)
      def update_all(self):
          for i in range(0, len(self.elt_scales)):
              try:
                  self.update(self.elt_scales[i][0], self.elt_scales[i][1], self.base_addr + i)
              except IOError, e:
                  print "Failed to update", self.serverloc, ":", str(e)
          self.post_test()

      def update(self, elt, scale, modbus_addr):
          self.modbus_addr = modbus_addr
          response = self.dev_read(4000, 70)
          time.sleep(2)
          data = [(TCPModbusClient.get_val(response.modbus_reg_val, i) & 0xffff)
                  for i in range(0, response.modbus_val_bytes / 2)]
          if len(data) != 70:
             print "Short read from", self.serverloc,  modbus_addr
             return

          self.reading_time = int(time.time())
          #self.add('/Three Phase (ABC)/Power', reading_time,
          #         float(data[2]) / e_d(scale))
          try:
              self.pwrABC = float(data[2]) / e_d(scale)
              self.post_test()
          except:
              print "data = %s, scale = %s" % (str(data),str(scale))

      def post_test(self):
          headers = {headers_mod.CONTENT_TYPE : headers_mod.CONTENT_TYPE.JSON, 'requesterID' : self._agent_id, "SourceName" : "LBNL DENT B90"}
          msg = "(%s, %s)" % (str(self.reading_time),str(self.pwrABC))
          #msg = "(" + str(self.reading_time) + ", " + str(self.pwrABC) + ")"
          self.publish(topics.BASE_ARCHIVER_REQUEST + "/Meter1/elt-A/ABC/true_power", headers, msg)
          
      @matching.match_start('heartbeat/listeneragent')
      def on_heartbeat_topic(self, topic, headers, message, match):
          print "DentAgent got\nTopic: {topic}, {headers}, Message: {message}".format(topic=topic, headers=headers, message=message)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.default_main(DentAgent,
                           description='Dent Agent',
                           argv=argv)
    except Exception as e:
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
