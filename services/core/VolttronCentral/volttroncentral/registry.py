import logging
import uuid

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


class DuplicateUUIDError(Exception):
    pass


class RegistryEntry(object):
    def __init__(self, vip_address, serverkey, platform_uuid=None,
                 display_name=None, **kwargs):

        assert vip_address
        assert serverkey

        self._vip_address = vip_address
        if not platform_uuid:
            platform_uuid = uuid.uuid4()

        self._uuid = platform_uuid
        self._display_name = display_name
        self._serverkey = serverkey
        self._tags = {}

        # Pop off all extra tags for a platform.
        for k, v in kwargs:
            self._tag[k] = kwargs.pop(k)

    def add_update_tag(self, name, value):
        self._tag[name] = value

    def has_tag(self, name):
        return name in self._tags.keys()

    @property
    def vip_address(self):
        return self._vip_address

    @property
    def platform_uuid(self):
        return self._uuid

    @property
    def serverkey(self):
        return self._serverkey

    @property
    def tags(self):
        return self._tags


class PlatformRegistry:
    """ Container class holding registered platforms and services.
    
    The goal of this class is to allow a single point of knowlege of
    all of the platforms and services registered with the volttron
    central agent.
    """

    def __init__(self, stale=5*60):
        """ Initialize the PlatformRegistry.
        :param stale: Seconds that the information should be considered valid.
        :return:
        """
        # Registry entries by uuid
        self._platform_entries = {}
        self._vip_to_uuid = {}


    def get_vip_addresses(self):
        """ Return all of the different vip addresses available.

        :return:
        """

        return self._vip_to_uuid.keys()

    def get_platforms(self):
        """ Returns all of the registerd platforms dictionaries.

        """
        return self._platform_entries.values()

    def get_platform(self, platform_uuid):
        """Returns a platform associated with a specific uuid instance.
        """
        return self._platform_entries.get(platform_uuid, None)

    def update_agent_list(self, platform_uuid, agent_list):
        """ Update the agent list node for the platform uuid that is passed.
        """
        self._platform_entries[platform_uuid].add_update_tag(
            'agent_list', agent_list.get())

    def unregister(self, vip_address):
        if vip_address in self._platform_entries.keys():
            del self._vip_to_uuid[vip_address]
            toremove = []
            for k, v in self._platform_entries.iteritems():
                if v['vip_address'] == vip_address:
                    toremove.append(k)
            for x in toremove:
                del self._platform_entries[x]

    def register(self, entry):
        """ Registers a PlatformEntry with the registry.
        :param entry:
        :return:
        """

        if entry.platform_uuid in self._uuids.keys():
            raise DuplicateUUIDError()

        self._platform_entries[entry.platform_uuid] = entry
        self._vip_to_uuid[entry.vip_address] = entry.platform_uuid

    def package(self):
        return {'vip_addresses': self._vips,
                'uuids':self._uuids}

    def unpackage(self, data):
        self._vips = data['vip_addresses']
        self._uuids = data['uuids']

    # def register(self, vip_address, vip_identity, agentid, **kwargs):
    #     """ Registers a platform agent with the registry.
    #
    #     An agentid must be non-None or a ValueError is raised
    #
    #     Keyword arguments:
    #     vip_address -- the registering agent's address.
    #     agentid     -- a human readable agent description.
    #     kwargs      -- additional arguments that should be stored in a
    #                    platform agent's record.
    #
    #     returns     The registered platform node.
    #     """
    #     if vip_address not in self._vips.keys():
    #         self._vips[vip_address] = {}
    #
    #     node = self._vips[vip_address]
    #
    #     if agentid is None:
    #         raise ValueError('Invalid agentid specified')
    #
    #     platform_uuid = str(uuid.uuid4())
    #     node[vip_identity] = {'agentid': agentid,
    #                           'vip_address': vip_address,
    #                           'vip_identity': vip_identity,
    #                           'uuid': platform_uuid,
    #                           'other': kwargs
    #                           }
    #     self._uuids[platform_uuid] = node[vip_identity]
    #
    #     _log.debug('Added ({}, {}, {} to registry'.format(vip_address,
    #                                                       vip_identity,
    #                                                       agentid))
    #     return node[vip_identity]


