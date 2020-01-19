import os

import pytest

from volttron.platform import keystore, jsonapi

host_pair1 = {'addr': 'tcp://127.0.0.1:1234', 'key': 'ABCDEFG'}
host_pair2 = {'addr': 'tcp://192.168.0.2:1234', 'key': '123456789'}


@pytest.fixture(scope="function")
def keystore_instance1(tmpdir_factory):
    path = str(tmpdir_factory.mktemp('keys').join('keys.json'))
    print('KEYSTORE PATH:', path)
    keys = keystore.KeyStore(path)
    keys.generate()
    return keys


@pytest.mark.keystore
def test_keystore_generated_when_created(tmpdir_factory):
    kspath = str(tmpdir_factory.mktemp('keys').join('keys.json'))
    ks = keystore.KeyStore(kspath)
    assert os.stat(kspath).st_mode & 0o777 == 0o600
    assert ks.secret
    assert ks.public


@pytest.mark.keystore
def test_generated_keys_length(keystore_instance1):
    '''The keys should be the len:gth of an encoded curve-key (43)'''
    assert len(keystore_instance1.public) == 43
    assert len(keystore_instance1.secret) == 43


@pytest.mark.keystore
def test_keystore_with_same_path(keystore_instance1):
    '''Reading from the same path should fetch the same keys'''
    path = keystore_instance1.filename
    keys = keystore.KeyStore(path)
    assert keystore_instance1.public == keys.public
    assert keystore_instance1.secret == keys.secret


@pytest.mark.keystore
def test_keystore_overwrite_keys(keystore_instance1):
    public = keystore_instance1.public
    secret = keystore_instance1.secret
    keystore_instance1.generate()
    assert keystore_instance1.public != public
    assert keystore_instance1.secret != secret


@pytest.fixture(scope="module")
def known_hosts_instance1(tmpdir_factory):
    path = str(tmpdir_factory.mktemp('known_hosts').join('hosts.json'))
    print('KNOWN HOSTS PATH:', path)
    store = keystore.KnownHostsStore(path)
    store.add(host_pair1['addr'], host_pair1['key'])
    store.add(host_pair2['addr'], host_pair2['key'])
    return store


@pytest.mark.keystore
def test_known_hosts_fetch(known_hosts_instance1):
    '''We should get what we put it'''
    host = known_hosts_instance1
    assert host.serverkey(host_pair1['addr']) == host_pair1['key']
    assert host.serverkey(host_pair2['addr']) == host_pair2['key']


@pytest.mark.keystore
def test_known_hosts_with_same_path(known_hosts_instance1):
    '''Reading from the same path should fetch the same keys'''
    key1 = known_hosts_instance1.serverkey(host_pair1['addr'])
    key2 = known_hosts_instance1.serverkey(host_pair2['addr'])

    host = keystore.KnownHostsStore(known_hosts_instance1.filename)
    assert host.serverkey(host_pair1['addr']) == key1
    assert host.serverkey(host_pair2['addr']) == key2


@pytest.mark.keystore
def test_known_hosts_update_entry(known_hosts_instance1):
    new_key = 'hijklmnop'
    old_key = known_hosts_instance1.serverkey(host_pair1['addr'])
    assert new_key != old_key

    known_hosts_instance1.add(host_pair1['addr'], new_key)
    assert known_hosts_instance1.serverkey(host_pair1['addr']) == new_key


@pytest.mark.keystore
def test_invalid_unicode_key(keystore_instance1):
    """
    Bypass KeyStore API and directly edit key to make it unicode.
    The keys should always be ASCII characters. This is a precaution
    against a corrupted key store.
    """
    with open(keystore_instance1.filename) as fp:
        keystore_json = jsonapi.load(fp)
    keystore_json['public'] = '\u0100'
    keystore_instance1.update(keystore_json)
    assert keystore_instance1.public is None
