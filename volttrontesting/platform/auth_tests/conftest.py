import os

from volttron.platform.agent.known_identities import PLATFORM, VOLTTRON_CENTRAL
from volttron.platform.keystore import KeyStore


def assert_auth_entries_same(e1, e2):
    for field in ['domain', 'address', 'user_id', 'credentials', 'comments',
                  'enabled']:
        assert e1[field] == e2[field]
    for field in ['roles', 'groups']:
        assert set(e1[field]) == set(e2[field])
    assert e1['capabilities'] == e2['capabilities']


def held_key(identity):
    """The public key the platform holds for a reserved identity, made the way
    main.py makes it. Reads VOLTTRON_HOME from the environment."""
    if identity == PLATFORM:
        return KeyStore().public
    return KeyStore(KeyStore.get_agent_keystore_path(identity)).public


def install_agent(vhome, identity, uuid="0123"):
    """Lays out an installed agent as the agent installer does, and returns
    its public key."""
    agent_dir = os.path.join(str(vhome), "agents", uuid)
    dist_info = os.path.join(agent_dir, "pkg", "pkg.dist-info")
    os.makedirs(dist_info)
    with open(os.path.join(agent_dir, "IDENTITY"), "w") as fil:
        fil.write(identity)
    return KeyStore(os.path.join(dist_info, "keystore.json")).public


def hold_volttron_central_key(vhome, monkeypatch):
    """Points VOLTTRON_HOME at vhome with volttron.central installed and
    returns the key the platform holds for it."""
    monkeypatch.setenv("VOLTTRON_HOME", str(vhome))
    return install_agent(vhome, VOLTTRON_CENTRAL)
