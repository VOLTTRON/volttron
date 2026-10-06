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
from volttron.platform.web import platform_web_service, static_roots
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


def _refused(service, identity, root, regex='^/probe/', reason=''):
    set_caller(service, identity)
    before = _snapshot(service)
    with pytest.raises(PermissionError, match=reason):
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
    reason = 'is inside VOLTTRON_HOME' if root in ('certificates', 'keystores') else \
        'contains VOLTTRON_HOME'
    _refused(service, OWNER, paths[root], reason=reason)


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
    (tmp_path / 'relative').mkdir()
    monkeypatch.chdir(tmp_path)
    entries = {'/': '/', 'home': str(home), 'home-parent': str(tmp_path),
               'inside-home': str(home / 'inside'), 'relative': 'relative',
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


def test_a_symlink_root_is_stored_as_its_target(layout, tmp_path):
    service, _, _ = layout
    (tmp_path / 'first' / 'probe').mkdir(parents=True)
    (tmp_path / 'first' / 'probe' / 'page.html').write_text('FIRST')
    (tmp_path / 'second' / 'probe').mkdir(parents=True)
    (tmp_path / 'second' / 'probe' / 'page.html').write_text('SECOND')
    link = tmp_path / 'current'
    link.symlink_to(tmp_path / 'first')
    _accepted(service, OTHER, link)
    link.unlink()
    link.symlink_to(tmp_path / 'second')
    assert _get(service, '/probe/page.html') == (200, b'FIRST')


def test_a_configured_root_is_kept_resolved(tmp_path, monkeypatch):
    target = tmp_path / 'target'
    target.mkdir()
    (tmp_path / 'link').symlink_to(target)
    service = build_web_service(tmp_path / 'www', monkeypatch, home=tmp_path / 'home',
                                static_roots=[str(tmp_path / 'link')])
    assert service._static_roots == (str(target),)


@pytest.fixture()
def served(tmp_path, monkeypatch):
    """A registered root at tmp_path/www holding probe/index.html."""
    service = build_web_service(tmp_path, monkeypatch)
    root = tmp_path / 'www'
    (root / 'probe').mkdir(parents=True)
    (root / 'probe' / 'index.html').write_text('INDEX')
    set_caller(service, OWNER)
    service.register_path_route('^/probe/', str(root))
    return service, root


def test_a_file_in_the_root_is_served(served):
    service, _ = served
    assert _get(service, '/probe/index.html') == (200, b'INDEX')


def test_a_sibling_directory_sharing_the_roots_prefix_is_not_served(served, tmp_path):
    service, _ = served
    (tmp_path / 'www-secret').mkdir()
    (tmp_path / 'www-secret' / 'f').write_text('SIBLING')
    assert _get(service, '/probe/../../www-secret/f') == FORBIDDEN


@pytest.mark.parametrize('relative', [
    'x.dist-info/keystore.json',
    'y.agent-data/f',
    'keystore.json',
    'Z.DIST-INFO/f',
])
def test_agent_files_created_after_registration_are_not_served(served, relative):
    service, root = served
    target = root / 'probe' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('PRIVATE')
    assert _get(service, f'/probe/{relative}') == FORBIDDEN


def test_a_request_naming_agent_metadata_is_refused_even_if_it_resolves_elsewhere(served):
    service, root = served
    (root / 'probe' / 'x.dist-info').mkdir()
    assert _get(service, '/probe/x.dist-info/../index.html') == FORBIDDEN
    assert _get(service, '/probe/index.html') == (200, b'INDEX')


def test_an_innocent_name_resolving_into_agent_metadata_is_not_served(served):
    service, root = served
    (root / 'probe' / 'x.dist-info').mkdir()
    (root / 'probe' / 'x.dist-info' / 'data.txt').write_text('PRIVATE')
    (root / 'probe' / 'alias').symlink_to(root / 'probe' / 'x.dist-info')
    assert _get(service, '/probe/alias/data.txt') == FORBIDDEN


def test_a_symlink_out_of_the_root_is_not_served(served, tmp_path):
    service, root = served
    (tmp_path / 'outside.txt').write_text('OUTSIDE')
    (root / 'probe' / 'link.txt').symlink_to(tmp_path / 'outside.txt')
    assert _get(service, '/probe/link.txt') == FORBIDDEN


def test_a_root_replaced_by_a_symlink_after_registration_is_not_followed(served, tmp_path):
    service, root = served
    (tmp_path / 'elsewhere' / 'probe').mkdir(parents=True)
    (tmp_path / 'elsewhere' / 'probe' / 'secret.txt').write_text('ELSEWHERE')
    root.rename(tmp_path / 'www-old')
    root.symlink_to(tmp_path / 'elsewhere')
    assert _get(service, '/probe/secret.txt') == FORBIDDEN


def test_the_packaged_pages_are_served_from_their_resolved_directory(tmp_path, monkeypatch):
    package = os.path.dirname(platform_web_service.__file__)
    (tmp_path / 'linked-package').symlink_to(package)
    monkeypatch.setattr(platform_web_service, '__file__',
                        str(tmp_path / 'linked-package' / 'platform_web_service.py'))
    service = build_web_service(tmp_path, monkeypatch)
    pattern, kind, root = service.registeredroutes[-1]
    static = os.path.join(os.path.realpath(package), 'static')
    assert (pattern.pattern, kind, root) == ('^/.*$', 'path', static)
    with open(os.path.join(static, 'index.html'), 'rb') as page:
        expected = page.read()
    assert _get(service, '/index.html') == (200, expected)


def test_agent_files_are_not_served_from_the_packaged_route(web_service, tmp_path):
    pattern, kind, _ = web_service.registeredroutes[-1]
    static = tmp_path / 'static'
    (static / 'x.dist-info').mkdir(parents=True)
    (static / 'x.dist-info' / 'f').write_text('PRIVATE')
    (static / 'page.html').write_text('PAGE')
    web_service.registeredroutes[-1] = (pattern, kind, str(static))
    assert _get(web_service, '/x.dist-info/f') == FORBIDDEN
    assert _get(web_service, '/page.html') == (200, b'PAGE')


def _warnings_naming(caplog, text):
    return [r for r in caplog.records
            if r.levelno == logging.WARNING and text in r.getMessage()]


def _bad_identity(install, kind):
    install.mkdir(parents=True)
    identity = install / 'IDENTITY'
    if kind == 'not-utf-8':
        identity.write_bytes(b'\xff\xfeprobe.owner')
    elif kind == 'fifo':
        os.mkfifo(identity)
    else:
        identity.mkdir()


@pytest.mark.timeout(20)
@pytest.mark.parametrize('kind', ['not-utf-8', 'fifo', 'directory'])
def test_an_unreadable_identity_file_is_skipped_with_a_warning(layout, caplog, kind):
    service, home, owner = layout
    _bad_identity(home / 'agents' / 'uuid-bad', kind)
    with caplog.at_level(logging.WARNING):
        _accepted(service, OWNER, owner / NAME / 'probeagent' / 'webroot')
    assert len(_warnings_naming(caplog, "uuid-bad' skipped")) == 1


def test_a_symlinked_identity_file_does_not_make_an_owner(layout, caplog):
    service, home, owner = layout
    borrowed = _agent_install(home, 'uuid-borrowed', 'probe.unused')
    (borrowed / 'IDENTITY').unlink()
    (borrowed / 'IDENTITY').symlink_to(owner / 'IDENTITY')
    with caplog.at_level(logging.WARNING):
        _refused(service, OWNER, borrowed / NAME / 'probeagent' / 'webroot')
    assert len(_warnings_naming(caplog, "uuid-borrowed' skipped")) == 1


LONG = 'a' * 70


@pytest.mark.parametrize('caller, accepted', [
    (LONG, True),
    (LONG[:64], False),
    (LONG[:10], False),
])
def test_the_whole_identity_file_names_the_owner(layout, caller, accepted):
    service, home, _ = layout
    install = _agent_install(home, 'uuid-long', LONG)
    root = install / NAME / 'probeagent' / 'webroot'
    if accepted:
        _accepted(service, caller, root)
    else:
        _refused(service, caller, root)


@pytest.mark.parametrize('caller', ['probe', 'owner', 'robe.own'])
def test_a_part_of_an_identity_does_not_own_its_install(layout, caller):
    service, _, owner = layout
    _refused(service, caller, owner / NAME / 'probeagent' / 'webroot')


def test_an_unlistable_agents_directory_refuses_roots_in_volttron_home(layout, caplog):
    service, home, owner = layout
    agents = home / 'agents'
    agents.chmod(0o311)
    try:
        with caplog.at_level(logging.WARNING):
            _refused(service, OWNER, owner / NAME / 'probeagent' / 'webroot',
                     reason='cannot be read')
    finally:
        agents.chmod(0o755)
    assert len(_warnings_naming(caplog, 'register_path_route refused')) == 1


def test_a_root_with_a_nul_byte_is_refused_with_a_warning(layout, tmp_path, caplog):
    service, _, _ = layout
    with caplog.at_level(logging.WARNING):
        _refused(service, OWNER, f'{tmp_path}/www\x00x', reason='not a valid path')
    assert len(_warnings_naming(caplog, 'register_path_route refused')) == 1


def test_a_configured_root_with_a_nul_byte_is_dropped_and_logged(tmp_path, monkeypatch, caplog):
    good = tmp_path / 'good'
    good.mkdir()
    with caplog.at_level(logging.ERROR):
        service = build_web_service(tmp_path / 'www', monkeypatch, home=tmp_path / 'home',
                                    static_roots=[f'{good}\x00x', str(good)])
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and 'not a valid path' in errors[0]
    assert service._static_roots == (str(good),)


@pytest.mark.parametrize('kwarg', ['web_ssl_key', 'web_ssl_cert'])
def test_a_configured_root_holding_the_web_key_or_certificate_is_dropped(
        tmp_path, monkeypatch, caplog, kwarg):
    holding = tmp_path / 'holding'
    (holding / 'tls').mkdir(parents=True)
    (holding / 'tls' / 'file.pem').write_text('PEM')
    good = tmp_path / 'good'
    good.mkdir()
    with caplog.at_level(logging.ERROR):
        service = build_web_service(tmp_path / 'www', monkeypatch, home=tmp_path / 'home',
                                    static_roots=[str(holding), str(good)],
                                    **{kwarg: str(holding / 'tls' / 'file.pem')})
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and str(holding) in errors[0]
    assert service._static_roots == (str(good),)


def test_a_refused_request_logs_no_server_path(served, caplog):
    service, _ = served
    with caplog.at_level(logging.DEBUG):
        assert _get(service, '/probe/x.dist-info/f') == FORBIDDEN
    assert not [r for r in caplog.records if 'Serverpath' in r.getMessage()]


def _swap_after_check(monkeypatch, swap):
    check = platform_web_service.file_to_serve

    def checked_then_swapped(root, path_info):
        path = check(root, path_info)
        swap()
        return path

    monkeypatch.setattr(platform_web_service, 'file_to_serve', checked_then_swapped)


def test_a_file_swapped_for_a_symlink_after_the_check_is_not_served(served, tmp_path,
                                                                    monkeypatch):
    service, root = served
    (tmp_path / 'outside.txt').write_text('OUTSIDE')
    page = root / 'probe' / 'index.html'

    def swap():
        page.unlink()
        page.symlink_to(tmp_path / 'outside.txt')

    _swap_after_check(monkeypatch, swap)
    assert _get(service, '/probe/index.html') == FORBIDDEN


def _swap_directory(root, tmp_path):
    (tmp_path / 'outside').mkdir()
    (tmp_path / 'outside' / 'index.html').write_text('OUTSIDE')
    probe = root / 'probe'

    def swap():
        probe.rename(root / 'probe-kept')
        probe.symlink_to(tmp_path / 'outside')

    def restore():
        probe.unlink()
        (root / 'probe-kept').rename(probe)

    return swap, restore


def test_a_directory_swapped_for_a_symlink_after_the_check_is_not_served(served, tmp_path,
                                                                         monkeypatch):
    service, root = served
    swap, _ = _swap_directory(root, tmp_path)
    _swap_after_check(monkeypatch, swap)
    assert _get(service, '/probe/index.html') == FORBIDDEN


def test_a_file_opened_through_a_swapped_directory_is_not_served(served, tmp_path,
                                                                monkeypatch):
    service, root = served
    swap, restore = _swap_directory(root, tmp_path)
    _swap_after_check(monkeypatch, swap)

    class RestoreAfterOpen:
        def __getattr__(self, name):
            return getattr(os, name)

        @staticmethod
        def open(*args, **kwargs):
            fd = os.open(*args, **kwargs)
            restore()
            return fd

    monkeypatch.setattr(static_roots, 'os', RestoreAfterOpen())
    assert _get(service, '/probe/index.html') == FORBIDDEN


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
