import uuid
import os

from collections import namedtuple

class Manager:

    def __init__(self):
        '''
        Initialize the available platform with the current platform
        '''
        Platform = namedtuple('Platform', "name uuid")

        platform1 = Platform(name='platform1', uuid="0bcb45b2-cae9-4629-93fc-ce5d4b6d4fae")
        platform2 = Platform(name='platform2', uuid="dbcb45b2-cae9-4629-93fc-ce5d4b6d4fae")

        self.available_platforms = [platform1, platform2]

#         self.available_platforms = {
#             platform1.uuid: platform1,
#             platform2.uuid: platform2
#         }

    def list_platforms(self):
        result = []
        for x in self.available_platforms:
            result.append({"platform": x.name, "uuid": x.uuid})

        return result



    def dispatch (self, method, params, id):
        retvalue = {"jsonrpc": "2.0", "id":id}
        if method == 'listPlatforms':
            retvalue["result"] = self.list_platforms()

        else:
            retvalue['error'] = {'code': 404, 'message': 'Unknown method'}

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

