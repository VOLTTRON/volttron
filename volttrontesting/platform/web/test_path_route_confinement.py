"""Which directories an agent may register as static roots, and which files
platform_web serves from them."""
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock

import gevent
import pytest
import requests

from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import PLATFORM_WEB, VOLTTRON_CENTRAL
from volttron.platform.jsonrpc import RemoteError
from volttrontesting.platform.web.conftest import build_web_service, set_caller
from volttrontesting.utils.web_utils import get_test_web_env

OWNER = 'probe.owner'
OTHER = 'probe.other'
NAME = 'probeagent-0.1'
FORBIDDEN = (403, b'<h1>403 Forbidden</h1>')


def _agent_install(home, uuid, identity):
    """An installed agent's directory as the platform lays it out."""
    install = home / 'agents' / uuid
    package = install / NAME
    (package / f'{NAME}.dist-info').mkdir(parents=True)
    (package / f'{NAME}.dist-info' / 'keystore.json').write_text('KEYSTORE')
    (package / f'{NAME}.agent-data').mkdir()
    (package / f'{NAME}.agent-data' / 'f').write_text('AGENT-DATA')
    webroot = package / 'probeagent' / 'webroot'
    (webroot / 'probe').mkdir(parents=True)
    (webroot / 'probe' / 'index.html').write_text('OWNER-PAGE')
    (install / 'IDENTITY').write_text(identity)
    return install


@pytest.fixture()
def layout(tmp_path, monkeypatch):
    """A web service whose VOLTTRON_HOME holds OWNER's install and OTHER's.

    tmp_path is the one configured static root; the home is outside it.
    """
    home = tmp_path.with_name(tmp_path.name + '-home')
    owner = _agent_install(home, 'uuid-owner', OWNER)
    _agent_install(home, 'uuid-other', OTHER)
    service = build_web_service(tmp_path, monkeypatch, home=home)
    return service, home, owner


def _snapshot(service):
    return (list(service.registeredroutes),
            {k: list(v) for k, v in service.pathroutes.items()},
            dict(service._namespace_owners))


def _refused(service, identity, root, regex='^/probe/'):
    set_caller(service, identity)
    before = _snapshot(service)
    with pytest.raises(PermissionError):
        service.register_path_route(regex, str(root))
    assert _snapshot(service) == before


def _accepted(service, identity, root, regex='^/probe/'):
    set_caller(service, identity)
    service.register_path_route(regex, str(root))
    entry = service.registeredroutes[-2]
    assert (entry[1], entry.owner, entry[2]) == ('path', identity, os.path.realpath(root))


def _get(service, path):
    start_response = MagicMock()
    body = b''.join(service.app_routing(get_test_web_env(path), start_response))
    return int(start_response.call_args[0][0].split()[0]), body


def test_a_directory_in_the_callers_own_install_is_accepted_and_served(layout):
    service, _, owner = layout
    _accepted(service, OWNER, owner / NAME / 'probeagent' / 'webroot')
    assert _get(service, '/probe/index.html') == (200, b'OWNER-PAGE')


def test_another_agents_install_directory_is_refused(layout):
    service, _, owner = layout
    _refused(service, OTHER, owner / NAME / 'probeagent' / 'webroot')


@pytest.mark.parametrize('relative', [
    '.',
    NAME,
    f'{NAME}/{NAME}.dist-info',
    f'{NAME}/{NAME}.agent-data',
])
def test_the_install_directory_and_agent_files_are_refused_to_the_owner(layout, relative):
    service, _, owner = layout
    _refused(service, OWNER, owner / relative)


@pytest.mark.parametrize('relative', [
    '.',
    NAME,
    f'{NAME}/{NAME}.dist-info',
    f'{NAME}/{NAME}.agent-data',
])
def test_a_symlink_root_is_judged_by_its_target(layout, tmp_path, relative):
    service, _, owner = layout
    link = tmp_path / 'innocent'
    link.symlink_to(owner / relative)
    _refused(service, OWNER, link)


def test_a_directory_inside_agent_metadata_is_refused(layout, tmp_path):
    service, _, _ = layout
    nested = tmp_path / 'copy.dist-info' / 'inner'
    nested.mkdir(parents=True)
    _refused(service, OWNER, nested)


def test_a_symlinked_install_directory_is_not_the_callers(layout, tmp_path):
    service, home, _ = layout
    elsewhere = _agent_install(tmp_path / 'elsewhere', 'uuid-linked', 'probe.linked')
    (home / 'agents' / 'uuid-linked').symlink_to(elsewhere)
    service._static_roots = ()
    _refused(service, 'probe.linked', elsewhere / NAME / 'probeagent' / 'webroot')


@pytest.mark.parametrize('root', ['home', 'home-parent', 'certificates', 'keystores', 'filesystem-root'])
def test_volttron_home_and_its_contents_are_refused(tmp_path, monkeypatch, root):
    home = tmp_path / 'home'
    for name in ('certificates', 'keystores'):
        (home / name).mkdir(parents=True)
    paths = {'home': home, 'home-parent': tmp_path, 'certificates': home / 'certificates',
             'keystores': home / 'keystores', 'filesystem-root': '/'}
    service = build_web_service(tmp_path / 'www', monkeypatch, home=home,
                                static_roots=[str(paths[root])])
    _refused(service, OWNER, paths[root])


def test_a_directory_in_a_configured_root_is_accepted(layout, tmp_path):
    service, _, _ = layout
    (tmp_path / 'site' / 'probe').mkdir(parents=True)
    (tmp_path / 'site' / 'probe' / 'page.html').write_text('SITE-PAGE')
    _accepted(service, OTHER, tmp_path / 'site')
    assert _get(service, '/probe/page.html') == (200, b'SITE-PAGE')


def test_a_directory_outside_every_allowed_root_is_refused(layout, tmp_path):
    service, _, _ = layout
    outside = tmp_path.with_name(tmp_path.name + '-outside')
    outside.mkdir()
    _refused(service, OWNER, outside)


@pytest.mark.parametrize('root', ['.', 'relative/dir', 'missing', 'a-file', 42])
def test_a_root_that_is_not_an_absolute_directory_is_refused(layout, tmp_path, monkeypatch, root):
    service, _, _ = layout
    (tmp_path / 'relative' / 'dir').mkdir(parents=True)
    (tmp_path / 'a-file').write_text('x')
    monkeypatch.chdir(tmp_path)
    if root in ('missing', 'a-file'):
        root = tmp_path / root
    set_caller(service, OWNER)
    before = _snapshot(service)
    with pytest.raises(PermissionError):
        service.register_path_route('^/probe/', root if root == 42 else str(root))
    assert _snapshot(service) == before


def test_a_refused_root_is_logged_as_a_warning(layout, caplog):
    service, home, _ = layout
    with caplog.at_level(logging.WARNING):
        _refused(service, OWNER, home)
    refusals = [r for r in caplog.records if r.levelno == logging.WARNING
                and 'register_path_route refused' in r.getMessage()]
    assert len(refusals) == 1


@pytest.mark.parametrize('entry', ['/', 'home', 'home-parent', 'inside-home', 'relative',
                                   'missing', 'a-file', 'metadata'])
def test_a_bad_configured_root_is_dropped_and_logged(tmp_path, monkeypatch, caplog, entry):
    home = tmp_path / 'home'
    (home / 'inside').mkdir(parents=True)
    (tmp_path / 'a-file').write_text('x')
    (tmp_path / 'x.dist-info').mkdir()
    entries = {'/': '/', 'home': str(home), 'home-parent': str(tmp_path),
               'inside-home': str(home / 'inside'), 'relative': 'www',
               'missing': str(tmp_path / 'missing'), 'a-file': str(tmp_path / 'a-file'),
               'metadata': str(tmp_path / 'x.dist-info')}
    good = tmp_path.with_name(tmp_path.name + '-good')
    good.mkdir()
    with caplog.at_level(logging.ERROR):
        service = build_web_service(tmp_path / 'www', monkeypatch, home=home,
                                    static_roots=[entries[entry], str(good)])
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and entries[entry] in errors[0]
    assert service._static_roots == (str(good),)


def test_a_configured_root_is_kept_resolved(tmp_path, monkeypatch):
    target = tmp_path / 'target'
    target.mkdir()
    (tmp_path / 'link').symlink_to(target)
    service = build_web_service(tmp_path / 'www', monkeypatch, home=tmp_path / 'home',
                                static_roots=[str(tmp_path / 'link')])
    assert service._static_roots == (str(target),)


@pytest.mark.web
def test_volttron_central_serves_its_pages(web_instance_with_static_root):
    instance = web_instance_with_static_root
    uuid = instance.install_agent(agent_dir=get_services_core('VolttronCentral'),
                                  config_file={'agentid': 'Volttron Central'},
                                  vip_identity=VOLTTRON_CENTRAL, startup_time=10)
    try:
        source = os.path.join(get_services_core('VolttronCentral'), 'volttroncentral', 'webroot')
        with open(os.path.join(source, 'vc', 'index.html'), 'rb') as page:
            expected = page.read()
        response = requests.get(instance.bind_web_address + '/vc/index.html', verify=False,
                                timeout=10)
        assert (response.status_code, response.content) == (200, expected)
    finally:
        instance.remove_agent(uuid)


@pytest.mark.web
def test_an_agent_is_refused_its_own_package_metadata(web_instance_with_static_root):
    instance = web_instance_with_static_root
    install = _agent_install(Path(instance.volttron_home), 'uuid-live-probe', 'probe.live.owner')
    agent = instance.build_agent(identity='probe.live.owner', enable_web=True,
                                 capabilities={'register_web_routes': None})
    try:
        for root in (install / NAME / f'{NAME}.dist-info', install / NAME, install):
            with pytest.raises(RemoteError) as refused:
                agent.vip.web.register_path('^/probe/', str(root))
            assert 'agent package metadata' in str(refused.value)
        response = requests.get(instance.bind_web_address + '/probe/index.html',
                                verify=False, timeout=10)
        assert response.status_code == 404
        agent.vip.web.register_path('^/probe/', str(install / NAME / 'probeagent' / 'webroot'))
        gevent.sleep(0.5)
        response = requests.get(instance.bind_web_address + '/probe/index.html', verify=False,
                                timeout=10)
        assert (response.status_code, response.text) == (200, 'OWNER-PAGE')
    finally:
        agent.vip.rpc.call(PLATFORM_WEB, 'unregister_all_agent_routes').get(timeout=10)
        agent.core.stop()
