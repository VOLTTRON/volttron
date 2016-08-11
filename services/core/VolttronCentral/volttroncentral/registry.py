from collections import namedtuple
from copy import deepcopy
from datetime import datetime
import logging
import shelve
import uuid

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


class DuplicateUUIDError(Exception):
    pass

RegistryEntry = namedtuple(
    'RegistryEntry', ['vip_address', 'serverkey', 'discovery_address',
                      'is_local', 'platform_uuid', 'display_name', 'tags',
                      'vcp_publickey'])


class PlatformRegistry(object):
    """ Container class holding registered platforms and services.

    The goal of this class is to allow a single point of knowlege of
    all of the platforms and services registered with the volttron
    central agent.
    """

    def __init__(self, retrieve_fn, store_fn):
        """ Initialize the PlatformRegistry.
        :param stale: Seconds that the information should be considered valid.
        :return:
        """
        # Registry entries by uuid
        self._platform_entries = {}
        self._vip_to_uuid = {}

        # callbacks for storing and retrieving resource directory data
        self._retrievefn = retrieve_fn
        self._storefn = store_fn
        try:
            self._platform_entries = self._retrievefn('registered_platforms')
            for k, v in self._platform_entries.items():
                self._vip_to_uuid[v.vip_address] = k
        except KeyError:
            pass # Raised when there isn't a registerd_platform.

    def update_devices(self, platform_uuid, devices):
        self.add_update_tag(platform_uuid, 'devices', devices)

    def get_devices(self, platform_uuid):
        #_log.debug('Getting devices from')
        return self.get_tag(platform_uuid, 'devices')

    def update_performance(self, platform_uuid, performance):
        self.add_update_tag(platform_uuid, 'performance', performance)

    def get_performance(self, platform_uuid):
        return self.get_tag(platform_uuid, 'performance')

    def add_update_tag(self, platform_uuid, key, value):
        """ Add a tag to the specified platform's entry.

        :param platform_uuid:
        :param key:
        :param value:
        :return:
        """
        if platform_uuid not in self._platform_entries.keys():
            raise KeyError("{} not found".format(platform_uuid))
        if not key:
            raise ValueError("key cannot be null")
        self._platform_entries[platform_uuid].tags[key] = value

    def get_tag(self, platform_uuid, key):
        retValue = None
        if platform_uuid in self._platform_entries.keys():
            if key in self._platform_entries[platform_uuid].tags.keys():
                retValue = self._platform_entries[platform_uuid].tags[key]
            else:
                _log.error(
                    'Invalid tag ({}) specified for platform'.format(key))
        else:
            _log.error('Invalid platform ({}) specified for getting tag ({})'
                       .format(platform_uuid, key))
        return retValue

    def get_vip_addresses(self):
        """ Return all of the different vip addresses available.

        :return:
        """

        return self._vip_to_uuid.keys()

    def get_platform_by_address(self, vip_address):
        _log.debug('Getting address: {}'.format(vip_address))
        uuid = self._vip_to_uuid[vip_address]
        entry = self._platform_entries[uuid]
        return entry

    def get_platforms(self):
        """ Returns all of the registerd platforms dictionaries.

        """
        return self._platform_entries.values()

    def get_platform(self, platform_uuid):
        """Returns a platform associated with a specific uuid instance.
        """
        return self._platform_entries.get(platform_uuid)

    def get_agent_list(self, platform_uuid):
        return self.get_tag(platform_uuid, "agent_list")

    def update_agent_list(self, platform_uuid, agent_list):
        """ Update the agent list node for the platform uuid that is passed.
        """
        self.add_update_tag(platform_uuid, 'agent_list', agent_list)

    @staticmethod
    def build_entry(vip_address, serverkey, discovery_address,
                    display_name=None, is_local=False, vcp_publickey=None):
        if not is_local:
            if not vip_address:
                raise ValueError(
                    'vip_address cannot be null for non-local platforms')
            if not serverkey:
                raise ValueError(
                    'serverkey cannot be null for no-local platforms'
                )
        return RegistryEntry(
            vip_address=vip_address, serverkey=serverkey,
            display_name=display_name, discovery_address=discovery_address,
            is_local=is_local, platform_uuid=str(uuid.uuid4()),
            tags={
                'created': datetime.utcnow().isoformat(),
                'available': True
            }, vcp_publickey=vcp_publickey
        )

    def unregister(self, vip_address):
        if vip_address in self._vip_to_uuid.keys():
            del self._vip_to_uuid[vip_address]
            toremove = []
            for k, v in self._platform_entries.iteritems():
                if v.vip_address == vip_address:
                    toremove.append(k)
            for x in toremove:
                del self._platform_entries[x]

            self._storefn('registered_platforms', self._platform_entries)

    def register(self, entry):
        """ Registers a PlatformEntry with the registry.
        :param entry:
        :return:
        """

        if entry.platform_uuid in self._platform_entries.keys():
            raise DuplicateUUIDError()

        self._platform_entries[entry.platform_uuid] = entry
        self._vip_to_uuid[entry.vip_address] = entry.platform_uuid
        self._storefn('registered_platforms', self._platform_entries)

    def package(self):
        return {}
            # {'vip_addresses': self._vips,
            #     'uuids':self._uuids}

    def unpackage(self, data):
        pass
        # self._vips = data['vip_addresses']
        # self._uuids = data['uuids']

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


