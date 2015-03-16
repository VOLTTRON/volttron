import uuid
import os
import json

from collections import namedtuple

class Manager:

    def __init__(self):
        '''
        Initialize the available platform with the current platform
        '''
        Platform = namedtuple('Platform', "name uuid agents methods")
        Agent = namedtuple('Agent', "name uuid methods")
        Method = namedtuple("Method", "name arguments docstring invoke")
        platform1_agents = [
                                Agent(
                                    name="HelloAgent",
                                    uuid = "85cb45b2-cae9-4629-93fc-ce5d4b6d4fae",
                                    methods=[
                                        Method(
                                            name="say",
                                            arguments="str",
                                            docstring="A simple hello agent example",
                                            invoke = lambda x: "hello: "+x
                                        )
                                    ]
                                ),
                                Agent(
                                    name="ProcessorAgent",
                                    uuid = "852345b2-cae9-4629-93fc-ce5d4b6d4fae",
                                    methods=[
                                        Method(
                                            name="list",
                                            arguments=None,
                                            docstring="Returns list of processes running on system.",
                                            invoke = lambda x: """ PID TTY          TIME CMD
15425 pts/4    00:00:00 bash
15641 pts/4    00:00:02 volttron
19171 pts/4    00:00:00 ps
"""
                                        )
                                    ]
                                )
                            ]

        platform1 = Platform(
                            name='platform1',
                            uuid="0bcb45b2-cae9-4629-93fc-ce5d4b6d4fae",
                            methods = [
                                Method(
                                    name = "listAgents",
                                    arguments = [],
                                    docstring = "Lists the agents available.",
                                    invoke = lambda x: [[y.name, y.uuid] for y in platform1_agents]
                                )

                            ],
                            agents=platform1_agents)
        platform2 = Platform(name='platform2',
                             uuid="dbcb45b2-cae9-4629-93fc-ce5d4b6d4fae",
                             agents=[],
                             methods = lambda x: [],)

        self.available_platforms = [platform1, platform2]

#         self.available_platforms = {
#             platform1.uuid: platform1,
#             platform2.uuid: platform2
#         }

    def get_platform_list(self):
        result = []
        for x in self.available_platforms:
            result.append({"platform": x.name, "uuid": x.uuid})

        return result

    def _find_platform(self, uuid):
        for x in self.available_platforms:
            if x.uuid == uuid:
                return x
        return None

    def _find_agent(self, platform, uuid):
        for x in platform.agents:
            if x.uuid == uuid:
                return x
        return None

    def _find_method(self, agent, method_name):
        for x in agent.methods:
            if x.name == method_name:
                return x
        return None

    def call_method(self, platform_uuid, agent_uuid, method, args):
        # find the platform
        # find the agent on the platform
        # find the method on the agent
        # invoke the mettod with the args.
        platform = self._find_platform(platform_uuid)
        if agent_uuid:
            agent = self._find_agent(platform, agent_uuid)
        else:
            method = self._find_method(platform, method)

        result = method.invoke(args)

        return result

    def parse_method(self, arg):
        '''Parse the string for keys in finding what the user wants.
        '''
        fields = arg.split('.')
        platform = fields[2]
        agent = None
        method = None

        # method applies to the platform in this case
        if len(fields) <= 4:
            method = fields[3]
        # we know we are looking at an agent method
        if len(fields) > 4:
            agent = fields[6]
            method = fields[7]

        return (platform, agent, method)


    def dispatch (self, method, params, id):
        retvalue = {"jsonrpc": "2.0", "id":id}
        if method == 'listPlatforms':
            retvalue["result"] = self.get_platform_list()

        else:

            (platform_uuid, agent_uuid, method) = self.parse_method(method)

            # must have at least a platform and method in order for this
            # to work properly.
            if not platform_uuid or not method:
                retvalue['error'] = {'code': 404, 'message': 'Unknown method'}

            retvalue['result'] = self.call_method(platform_uuid, agent_uuid, method, params)
            print "Attempting to return: "
            print retvalue['result']
            #retvalue['error'] = {'code': 404, 'message': 'Unknown method'}

        return retvalue

#
#             {
#                 uuid: "0bcb45b2-cae9-4629-93fc-ce5d4b6d4fae",
#                 name: "platform1",
# #                 capabilities: {
# #                     hello: {args: {}}
# #                 }
#             },
#             {
#                 uuid: "5bcb45b2-cae9-4629-93fc-ce5d4b6d4fae",
#                 name: "platform2",
# #                 capabilities: {
# #                 }
#             },
#             {
#                 uuid: "8bcb45b2-cae9-4629-93fc-ce5d4b6d4fae",
#                 name: "platform3",
# #                 capabilities: {
# #                 }
#             },
#         }
        self.this_platform = os.environ.get('PLATFORM_UUID', "0bcb45b2-cae9-4629-93fc-ce5d4b6d4fae")

    def current_platforms(self):
        return self.available_platforms.copy()

    def connection_established(self, platform):
        self.available_platforms[platform.uuid] = platform

    def disconnect(self, uuid):
        del self.available_platforms[uuid]

    def get_connected_platforms(self):
        return self.available_platforms.keys().copy()

