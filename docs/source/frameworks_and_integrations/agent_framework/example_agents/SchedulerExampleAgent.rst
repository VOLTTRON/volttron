.. _SchedulerExampleAgent:

SchedulerExampleAgent
=====================

The SchedulerExampleAgent demonstrates how to use the scheduling feature
of the [[ActuatorAgent]] as well as how to send a command. This agent
publishes a request for a reservation on a (fake) device then takes an
action when it's scheduled time appears. The ActuatorAgent must be
running to exercise this example.

Note: Since there is no actual device, an error is produced when the
agent attempts to take its action.

::

    def publish_schedule(self):
        '''Periodically publish a schedule request'''
        headers = {
            'AgentID': agent_id,
            'type': 'NEW_SCHEDULE',
            'requesterID': agent_id, #The name of the requesting agent.
            'taskID': agent_id + "-ExampleTask", #The desired task ID for this task. It must be unique among all other scheduled tasks.
            'priority': 'LOW', #The desired task priority, must be 'HIGH', 'LOW', or 'LOW_PREEMPT'
            } 

        start = str(datetime.datetime.now())
        end = str(datetime.datetime.now() + datetime.timedelta(minutes=1))


        msg = [
           ['campus/building/unit',start,end]
        ]
        self.vip.pubsub.publish(
        'pubsub', topics.ACTUATOR_SCHEDULE_REQUEST, headers, msg)

The agent listens to schedule announcements from the actuator and then
issues a command

::

        @PubSub.subscribe('pubsub', topics.ACTUATOR_SCHEDULE_ANNOUNCE(campus='campus',
                                             building='building',unit='unit'))
        def actuate(self, peer, sender, bus,  topic, headers, message):
            print ("response:",topic,headers,message)
            if headers[headers_mod.REQUESTER_ID] != agent_id:
                return
            '''Match the announce for our fake device with our ID
            Then take an action. Note, this command will fail since there is no 
            actual device'''
            headers = {
                        'requesterID': agent_id,
                       }
            self.vip.pubsub.publish(
            'pubsub', topics.ACTUATOR_SET(campus='campus',
                                             building='building',unit='unit',
                                             point='point'),
                                             headers, 0.0)

