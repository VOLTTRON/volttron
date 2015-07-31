import sys
import MPC
import CBC_Gui
import datetime
from volttron.platform.agent import BaseAgent, PublishMixin, periodic, matching, utils
from volttron.platform.messaging import headers as headers_mod

class MpcAgent(PublishMixin, BaseAgent):

	def __init__(self, config_path, **kwargs):
		super(MpcAgent, self).__init__(**kwargs)
		self.config = utils.load_config(config_path)
		# Create the control object
		self.mpc = MPC.MPC()
		self.mpc.make_gui()

	def setup(self):
		self._agent_id = self.config['agentid']
		super(MpcAgent,self).setup()

	@matching.match_exact('weather/temperature/temp_f')
	def on_match(self, topic, headers, message, match):
		self.mpc.set_outdoor_temp(float(message[0]))
		print "MPC: outdoor temp = ",self.mpc.get_outdoor_temp()

	# Demonstrate periodic decorator and settings access
	@periodic(MPC.PERIOD)
	def run_control(self):
		now = str(datetime.datetime.now())
		print "MPC: run control @ ",now
		self.mpc.run_control(MPC.PERIOD)

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(MpcAgent,
                       description='RTU Control Cat',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
