import logging
import uuid

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

class PlatformRegistry:
    '''Container class holding registered vip platforms and services.
    
    The goal of this class is to allow a single point of knowlege of
    all of the platforms and services registered with the volttron
    central agent.    
    '''

    def __init__(self, stale=5*60):
        self._vips = {}
        self._uuids = {}
        self._external_addresses = None

    def get_vip_addresses(self):
        '''Returns all of the known vip addresses.
        '''
        return self._vips.keys()

    def get_platforms(self):
        '''Returns all of the registerd platforms dictionaries.
        '''
        return self._uuids.values()

    def get_platform(self, platform_uuid):
        '''Returns a platform associated with a specific uuid instance.
        '''
        return self._uuids.get(platform_uuid, None)

    def update_agent_list(self, platform_uuid, agent_list):
        '''Update the agent list node for the platform uuid that is passed.
        '''
        self._uuids[platform_uuid]['agent_list'] = agent_list.get()

    def unregister(self, vip_address):
        if vip_address in self._vips.keys():
            del self._vips[vip_address]
            toremove = []
            for k, v in self._uuids.iteritems():
                if v['vip_address'] == vip_address:
                    toremove.append(k)
            for x in toremove:
                del self._uuids[x]

    def register(self, vip_address, vip_identity, agentid, **kwargs):
        '''Registers a platform agent with the registry.

        An agentid must be non-None or a ValueError is raised

        Keyword arguments:
        vip_address -- the registering agent's address.
        agentid     -- a human readable agent description.
        kwargs      -- additional arguments that should be stored in a
                       platform agent's record.

        returns     The registered platform node.
        '''
        if vip_address not in self._vips.keys():
            self._vips[vip_address] = {}

        node = self._vips[vip_address]

        if agentid is None:
            raise ValueError('Invalid agentid specified')

        platform_uuid = str(uuid.uuid4())
        node[vip_identity] = {'agentid': agentid,
                              'vip_address': vip_address,
                              'vip_identity': vip_identity,
                              'uuid': platform_uuid,
                              'other': kwargs
                              }
        self._uuids[platform_uuid] = node[vip_identity]

        _log.debug('Added ({}, {}, {} to registry'.format(vip_address,
                                                          vip_identity,
                                                          agentid))
        return node[vip_identity]

    def package(self):
        return {'vip_addresses': self._vips,
                'uuids':self._uuids}

    def unpackage(self, data):
        self._vips = data['vip_addresses']
        self._uuids = data['uuids']
